"""Configuration and options flows for PaliwoMapa."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PaliwoMapaApi
from .const import (
    AUTH_ACCOUNT, AUTH_NONE, CONF_AUTH_MODE, CONF_EMAIL, CONF_PASSWORD,
    CONF_STATION_IDS, CONF_STATION_LOCATIONS, CONF_FUEL_TYPES, DOMAIN, FUEL_LABELS,
)
from .models import parse_station_ids

_LOGGER = logging.getLogger(__name__)


def _nearby_label(station: dict) -> str:
    name = station.get("station_name") or station.get("osm_name") or f"Stacja {station['station_id']}"
    address = station.get("station_address") or station.get("osm_address") or "adres nieznany"
    distance = station.get("distance_km", 0)
    prices = station.get("prices", {})
    price_bits = [f"{fuel} {prices[key]:.2f} zł/l" for key, fuel in (("pb95", "PB95"), ("on", "ON"), ("lpg", "LPG")) if key in prices]
    price_text = " · ".join(price_bits) if price_bits else "brak cen"
    return f"{name} — {address} · {distance:.1f} km · {price_text}"


def _location_data(station: dict) -> dict:
    return {
        "latitude": station["latitude"],
        "longitude": station["longitude"],
        "distance_km": station["distance_km"],
    }


class PaliwoMapaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one PaliwoMapa entry with optional account authentication."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_mode = AUTH_NONE
        self._credentials: dict[str, str] = {}
        self._nearby_results: dict[str, dict] = {}
        self._pending_data: dict = {}
        self._pending_stations: dict = {}
        self._pending_title: str = "PaliwoMapa"

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._auth_mode = user_input[CONF_AUTH_MODE]
            if self._auth_mode == AUTH_ACCOUNT:
                return await self.async_step_account()
            return await self.async_step_stations()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_AUTH_MODE, default=AUTH_NONE): vol.In({
                    AUTH_NONE: "Bez konta PaliwoMapa",
                    AUTH_ACCOUNT: "Z kontem PaliwoMapa",
                }),
            }),
        )

    async def async_step_account(self, user_input=None):
        errors = {}
        if user_input is not None:
            credentials = {
                CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                api = PaliwoMapaApi(
                    async_get_clientsession(self.hass),
                    credentials[CONF_EMAIL], credentials[CONF_PASSWORD],
                )
                await api.async_login()
            except HomeAssistantError:
                errors["base"] = "invalid_auth"
            else:
                self._credentials = credentials
                return await self.async_step_stations()
        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_stations(self, user_input=None):
        errors = {}
        if user_input is not None:
            source = user_input.get("source", "manual")
            if source == "nearby":
                try:
                    if self.hass.config.latitude == 0 and self.hass.config.longitude == 0:
                        errors["base"] = "home_location_missing"
                        raise HomeAssistantError("Nie skonfigurowano lokalizacji domu Home Assistant.")
                    api = self._api()
                    self._nearby_results = {
                        item["station_id"]: item
                        for item in await api.async_search_nearby_stations(
                            self.hass.config.latitude, self.hass.config.longitude,
                            float(user_input.get("radius_km", 10)),
                        )
                    }
                    if not self._nearby_results:
                        errors["base"] = "no_nearby_stations"
                    else:
                        return await self.async_step_select_nearby()
                except HomeAssistantError:
                    if not errors.get("base"):
                        errors["base"] = "nearby_search_failed"
            else:
                try:
                    manual_ids = parse_station_ids(user_input.get(CONF_STATION_IDS, ""))
                    data = {CONF_AUTH_MODE: self._auth_mode, CONF_STATION_IDS: manual_ids, **self._credentials}
                    api = self._api(data)
                    station_ids = list(manual_ids)
                    if api.account_enabled:
                        try:
                            favorites = await api.async_get_favorite_station_ids()
                        except HomeAssistantError as err:
                            _LOGGER.warning("Nie udało się pobrać ulubionych stacji PaliwoMapa: %s", err)
                            favorites = []
                        station_ids = list(dict.fromkeys([*favorites, *manual_ids]))
                    if station_ids:
                        stations = await api.async_get_stations(station_ids)
                        missing = set(station_ids) - set(stations)
                        if missing:
                            errors["base"] = "some_stations_unavailable"
                        else:
                            return await self._create_entry(station_ids, data, stations)
                    else:
                        return await self._create_entry([], data)
                except ValueError:
                    errors["base"] = "invalid_station_ids"
                except HomeAssistantError:
                    errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="stations",
            data_schema=vol.Schema({
                vol.Required("source", default="manual"): vol.In({
                    "manual": "Dodaj konkretne stacje po linku/ID",
                    "nearby": "Wyszukaj stacje w promieniu od lokalizacji domu HA",
                }),
                vol.Optional(CONF_STATION_IDS, default=""): str,
                vol.Optional("radius_km", default=10): vol.All(vol.Coerce(float), vol.Range(min=1, max=50)),
            }),
            errors=errors,
        )

    async def async_step_select_nearby(self, user_input=None):
        errors = {}
        if user_input is not None:
            selected = user_input.get("station_ids", [])
            if not selected:
                errors["base"] = "select_at_least_one_station"
            else:
                try:
                    data = {CONF_AUTH_MODE: self._auth_mode, **self._credentials}
                    station_ids = list(dict.fromkeys(selected))
                    data[CONF_STATION_IDS] = station_ids
                    data[CONF_STATION_LOCATIONS] = {
                        station_id: _location_data(self._nearby_results[station_id])
                        for station_id in station_ids if station_id in self._nearby_results
                    }
                    selected_stations = {sid: self._nearby_results[sid] for sid in station_ids}
                    return await self._create_entry(station_ids, data, selected_stations)
                except HomeAssistantError:
                    errors["base"] = "cannot_connect"
        options = {sid: _nearby_label(station) for sid, station in self._nearby_results.items()}
        return self.async_show_form(
            step_id="select_nearby",
            data_schema=vol.Schema({vol.Required("station_ids", default=[]): cv.multi_select(options)}),
            errors=errors,
            description_placeholders={"count": str(len(options))},
        )

    def _api(self, data: dict | None = None) -> PaliwoMapaApi:
        data = data or self._credentials
        return PaliwoMapaApi(
            async_get_clientsession(self.hass), data.get(CONF_EMAIL), data.get(CONF_PASSWORD),
        )

    async def _create_entry(self, station_ids: list[str], data: dict, stations: dict | None = None):
        if station_ids:
            if stations is None:
                stations = await self._api(data).async_get_stations(station_ids)
            missing = set(station_ids) - set(stations)
            if missing:
                raise HomeAssistantError("Nie udało się pobrać danych części wybranych stacji.")
            names = [s.get("station_name") for s in stations.values() if s.get("station_name")]
        else:
            names = []
        await self.async_set_unique_id("paliwomapa_instance")
        self._abort_if_unique_id_configured()
        self._pending_data = dict(data)
        self._pending_stations = dict(stations or {})
        self._pending_title = f"PaliwoMapa — {names[0]}" if len(names) == 1 else f"PaliwoMapa — {len(station_ids)} stacji" if names else "PaliwoMapa"
        return await self.async_step_fuels()

    async def async_step_fuels(self, user_input=None):
        """Choose which fuel types should have entities created."""
        errors = {}
        if user_input is not None:
            selected = list(dict.fromkeys(user_input.get(CONF_FUEL_TYPES, [])))
            if not selected:
                errors["base"] = "select_at_least_one_fuel"
            else:
                self._pending_data[CONF_FUEL_TYPES] = selected
                return self.async_create_entry(title=self._pending_title, data=self._pending_data)
        return self.async_show_form(
            step_id="fuels",
            data_schema=vol.Schema({
                vol.Required(CONF_FUEL_TYPES, default=list(FUEL_LABELS)): cv.multi_select({key: label for key, label in FUEL_LABELS.items()}),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PaliwoMapaOptionsFlow(config_entry)


class PaliwoMapaOptionsFlow(config_entries.OptionsFlow):
    """Manage stations additively and search around the configured HA home."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry
        self._nearby_results: dict[str, dict] = {}
        self._selected_fuel_types = list(config_entry.options.get(CONF_FUEL_TYPES, config_entry.data.get(CONF_FUEL_TYPES, list(FUEL_LABELS))))

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                action = user_input["action"]
                self._selected_fuel_types = list(dict.fromkeys(user_input.get(CONF_FUEL_TYPES, list(FUEL_LABELS))))
                if not self._selected_fuel_types:
                    errors["base"] = "select_at_least_one_fuel"
                    raise HomeAssistantError("Wybierz co najmniej jeden rodzaj paliwa.")
                supplied_ids = parse_station_ids(user_input.get(CONF_STATION_IDS, ""))
                current = self._current_ids()
                if action == "save_fuels":
                    return await self._save(current)
                if action == "search_nearby":
                    if self.hass.config.latitude == 0 and self.hass.config.longitude == 0:
                        errors["base"] = "home_location_missing"
                        raise HomeAssistantError("Nie skonfigurowano lokalizacji domu Home Assistant.")
                    api = self._api()
                    self._nearby_results = {
                        item["station_id"]: item
                        for item in await api.async_search_nearby_stations(
                            self.hass.config.latitude, self.hass.config.longitude,
                            float(user_input.get("radius_km", 10)),
                        )
                    }
                    if not self._nearby_results:
                        errors["base"] = "no_nearby_stations"
                    else:
                        return await self.async_step_select_nearby()
                elif action == "import_favorites":
                    api = self._api()
                    if not api.account_enabled:
                        errors["base"] = "account_required_for_favorites"
                    else:
                        favorites = await api.async_get_favorite_station_ids()
                        if not favorites:
                            errors["base"] = "favorites_not_found"
                        else:
                            new_ids = [sid for sid in favorites if sid not in current]
                            if new_ids:
                                stations = await api.async_get_stations(new_ids)
                                new_ids = [sid for sid in new_ids if sid in stations]
                            if not new_ids:
                                errors["base"] = "favorites_already_monitored"
                            else:
                                return await self._save(list(dict.fromkeys([*current, *new_ids])))
                elif action in ("add", "replace") and supplied_ids:
                    api = self._api()
                    stations = await api.async_get_stations(supplied_ids)
                    missing = set(supplied_ids) - set(stations)
                    if missing:
                        errors["base"] = "some_stations_unavailable"
                    else:
                        updated = list(dict.fromkeys([*(current if action == "add" else []), *supplied_ids]))
                        return await self._save(updated)
                elif action == "remove":
                    if not supplied_ids:
                        errors["base"] = "select_station_to_remove"
                    else:
                        updated = [sid for sid in current if sid not in set(supplied_ids)]
                        return await self._save(updated)
                elif action == "replace":
                    return await self._save([])
                elif action == "add":
                    errors["base"] = "enter_station_ids"
            except ValueError:
                errors["base"] = "invalid_station_ids"
            except HomeAssistantError:
                if not errors.get("base"):
                    errors["base"] = "cannot_connect"
        current = self._current_ids()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="save_fuels"): vol.In({
                    "search_nearby": "Wyszukaj stacje w promieniu od domu HA",
                    "add": "Dodaj stacje po linku lub ID",
                    "remove": "Usuń wskazane stacje po linku lub ID",
                    "replace": "Zastąp całą listę stacji",
                    "import_favorites": "Importuj ulubione z konta PaliwoMapa",
                    "save_fuels": "Zapisz wybór paliw",
                }),
                vol.Required(CONF_FUEL_TYPES, default=self._selected_fuel_types): cv.multi_select({key: label for key, label in FUEL_LABELS.items()}),
                vol.Optional("radius_km", default=10): vol.All(vol.Coerce(float), vol.Range(min=1, max=50)),
                vol.Optional(CONF_STATION_IDS, default=""): str,
            }),
            errors=errors,
            description_placeholders={
                "current_stations": ", ".join(current) if current else "Brak monitorowanych stacji",
                "hint": "Wyszukiwanie używa współrzędnych domu skonfigurowanych w Home Assistant. Promień 1–50 km. Dodawanie nie usuwa istniejących stacji.",
            },
        )

    async def async_step_select_nearby(self, user_input=None):
        errors = {}
        if user_input is not None:
            selected = user_input.get("station_ids", [])
            if not selected:
                errors["base"] = "select_at_least_one_station"
            else:
                current = self._current_ids()
                updated = list(dict.fromkeys([*current, *selected]))
                locations = dict(self._entry.data.get(CONF_STATION_LOCATIONS, {}))
                for station_id in selected:
                    if station_id in self._nearby_results:
                        locations[station_id] = _location_data(self._nearby_results[station_id])
                return await self._save(updated, locations)
        current = set(self._current_ids())
        options = {}
        for sid, station in self._nearby_results.items():
            label = _nearby_label(station)
            if sid in current:
                label = f"✓ Monitorowana · {label}"
            options[sid] = label
        return self.async_show_form(
            step_id="select_nearby",
            data_schema=vol.Schema({vol.Required("station_ids", default=[]): cv.multi_select(options)}),
            errors=errors,
            description_placeholders={"count": str(len(options))},
        )

    def _current_ids(self) -> list[str]:
        raw = self._entry.data.get(CONF_STATION_IDS)
        if raw is None:
            raw = self._entry.data.get("station_id", [])
        if isinstance(raw, str):
            raw = [raw]
        try:
            return parse_station_ids(",".join(str(item) for item in raw or []))
        except ValueError:
            return []

    def _api(self) -> PaliwoMapaApi:
        return PaliwoMapaApi(
            async_get_clientsession(self.hass),
            self._entry.data.get(CONF_EMAIL), self._entry.data.get(CONF_PASSWORD),
        )

    async def _save(self, station_ids: list[str], locations: dict | None = None):
        old_locations = dict(self._entry.data.get(CONF_STATION_LOCATIONS, {}))
        if locations is not None:
            old_locations.update(locations)
        kept_locations = {sid: val for sid, val in old_locations.items() if sid in station_ids}
        new_data = {**self._entry.data, CONF_STATION_IDS: station_ids, CONF_STATION_LOCATIONS: kept_locations}
        new_data.pop("station_id", None)
        new_options = {**self._entry.options, CONF_FUEL_TYPES: self._selected_fuel_types}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data, options=new_options)
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(title="", data={})
