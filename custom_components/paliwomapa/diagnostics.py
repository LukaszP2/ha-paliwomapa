"""Safe diagnostics with credentials and profile data omitted."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import PaliwoMapaCoordinator

TO_REDACT = {"password", "email", "access_token", "refresh_token", "token", "apikey", "Authorization", "user_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator: PaliwoMapaCoordinator = entry.runtime_data
    stations = coordinator.data.get("stations", {}) if coordinator.data else {}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "configured_station_ids": list(coordinator.station_ids),
        "stations": {
            station_id: {
                "station_name": data.get("station_name"),
                "station_address": data.get("station_address"),
                "available_fuels": sorted(data.get("prices", {}).keys()),
                "has_updated_timestamp": bool(data.get("updated")),
            }
            for station_id, data in stations.items()
        },
        "station_errors": list(coordinator.data.get("errors", {}).keys()) if coordinator.data else [],
        "last_update_success": coordinator.last_update_success,
    }
