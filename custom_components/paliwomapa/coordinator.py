"""Coordinator fetching the configured station set in a single refresh cycle."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import PaliwoMapaApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PaliwoMapaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate manual refreshes for multiple monitored stations."""

    def __init__(self, hass: HomeAssistant, api: PaliwoMapaApi, station_ids: list[str], station_locations: dict[str, dict] | None = None) -> None:
        self.api = api
        self.station_ids = station_ids
        self.station_locations = station_locations or {}
        self.hub_device_id: str | None = None
        super().__init__(
            hass, logger=_LOGGER, name=DOMAIN,
            # Deliberately no automatic polling in this private prototype.
            update_interval=None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        stations: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        try:
            stations = await self.api.async_get_stations(self.station_ids)
        except Exception as err:
            errors = {station_id: str(err) for station_id in self.station_ids}
        missing_ids = set(self.station_ids) - set(stations)
        for station_id in missing_ids:
            errors.setdefault(station_id, "API nie zwróciło danych tej stacji.")
        if not stations and self.station_ids:
            # Do not erase the previous good data if all station requests failed.
            from homeassistant.helpers.update_coordinator import UpdateFailed
            raise UpdateFailed("Nie udało się pobrać danych żadnej monitorowanej stacji.")
        for station_id, station in stations.items():
            location = self.station_locations.get(station_id)
            if location:
                station["location"] = location
        previous = self.data.get("stations", {}) if self.data else {}
        # Keep last-known-good station data during a partial outage instead of making
        # healthy entities disappear. The station remains listed in the errors map.
        for station_id, old_data in previous.items():
            if station_id not in stations and station_id in errors:
                stations[station_id] = old_data
                location = self.station_locations.get(station_id)
                if location:
                    stations[station_id]["location"] = location
        account_profile: dict[str, Any] = {}
        if self.api.account_enabled:
            try:
                account_profile = await self.api.async_get_account_profile()
            except Exception as err:  # Account metadata must not break station-price updates.
                _LOGGER.debug("Could not refresh PaliwoMapa account profile: %s", err)
                account_profile = self.data.get("account_profile", {}) if self.data else {}
        return {"stations": stations, "errors": errors, "account_profile": account_profile, "last_refresh": datetime.now(timezone.utc)}
