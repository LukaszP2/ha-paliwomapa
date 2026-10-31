"""Station price and cross-station comparison sensors."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FUEL_TYPES, DOMAIN, FUEL_LABELS


def _map_links(station: dict[str, Any]) -> dict[str, str]:
    """Build HTTPS map/navigation links that work across mobile platforms."""
    location = station.get("location", {}) or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    address = station.get("station_address") or ""
    name = station.get("station_name") or "Stacja paliw"
    if latitude is not None and longitude is not None:
        destination = f"{latitude},{longitude}"
        encoded_destination = quote(destination, safe=",")
        map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_destination}"
        navigation_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_destination}"
        apple_maps_url = f"https://maps.apple.com/?daddr={encoded_destination}"
        osm_url = f"https://www.openstreetmap.org/directions?to={encoded_destination}"
    else:
        query = quote(f"{name} {address}".strip())
        map_url = f"https://www.google.com/maps/search/?api=1&query={query}"
        navigation_url = f"https://www.google.com/maps/dir/?api=1&destination={query}"
        apple_maps_url = f"https://maps.apple.com/?daddr={query}"
        osm_url = f"https://www.openstreetmap.org/search?query={query}"
    return {
        "map_url": map_url,
        "navigation_url": navigation_url,
        "google_maps_url": navigation_url,
        "apple_maps_url": apple_maps_url,
        "openstreetmap_url": osm_url,
    }


def _station_device_name(station: dict[str, Any], station_id: str) -> str:
    """Build a useful, distinguishable device name for repeated fuel brands."""
    brand = str(station.get("station_name") or "Stacja").strip()
    address = str(station.get("station_address") or "").strip()
    if address:
        return f"{brand} — {address} [{station_id}]"
    return f"{brand} [{station_id}]"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    selected_fuels = entry.options.get(CONF_FUEL_TYPES, entry.data.get(CONF_FUEL_TYPES, list(FUEL_LABELS)))
    selected_fuels = [fuel for fuel in selected_fuels if fuel in FUEL_LABELS] or list(FUEL_LABELS)
    for fuel in selected_fuels:
        entities.append(CheapestFuelSensor(coordinator, fuel))
        entities.append(CheapestFuelStationSensor(coordinator, fuel))
    entities.append(LastRefreshSensor(coordinator))
    if coordinator.api.account_enabled:
        entities.append(AccountProfileSensor(coordinator))
    for station_id in coordinator.station_ids:
        for fuel, label in FUEL_LABELS.items():
            if fuel in selected_fuels:
                entities.append(StationFuelSensor(coordinator, station_id, fuel, label))
        entities.append(StationUpdatedSensor(coordinator, station_id))
    async_add_entities(entities)


class StationFuelSensor(CoordinatorEntity, SensorEntity):
    """Fuel price for one configured station."""

    _attr_native_unit_of_measurement = "PLN/L"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator, station_id: str, fuel: str, label: str) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._fuel = fuel
        self._attr_name = label
        self._attr_unique_id = f"{station_id}_{fuel}"

    @property
    def _station(self) -> dict[str, Any]:
        return self.coordinator.data.get("stations", {}).get(self._station_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._station)

    @property
    def native_value(self) -> float | None:
        return self._station.get("prices", {}).get(self._fuel)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        station = self._station
        return {
            "station_id": self._station_id,
            "station_address": station.get("station_address"),
            "price_updated": station.get("price_updated", {}).get(self._fuel),
            "station_updated": station.get("updated"),
            "distance_km": station.get("location", {}).get("distance_km"),
            "latitude": station.get("location", {}).get("latitude"),
            "longitude": station.get("location", {}).get("longitude"),
            **_map_links(station),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        station = self._station
        return {
            "identifiers": {(DOMAIN, self._station_id)},
            "name": _station_device_name(station, self._station_id),
            "manufacturer": "PaliwoMapa",
            "model": station.get("station_address") or f"ID {self._station_id}",
            "configuration_url": "https://paliwomapa.pl/",
            "via_device_id": self.coordinator.hub_device_id,
        }


class StationUpdatedSensor(CoordinatorEntity, SensorEntity):
    """Timestamp reported by PaliwoMapa for a station's prices."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, station_id: str) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_name = "Aktualizacja cen"
        self._attr_unique_id = f"{station_id}_updated"

    @property
    def native_value(self):
        station = self.coordinator.data.get("stations", {}).get(self._station_id, {})
        value = station.get("updated")
        if not value:
            return None
        from datetime import datetime
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        station = self.coordinator.data.get("stations", {}).get(self._station_id, {})
        return {"station_id": self._station_id, **_map_links(station)}

    @property
    def device_info(self) -> dict[str, Any]:
        station = self.coordinator.data.get("stations", {}).get(self._station_id, {})
        return {
            "identifiers": {(DOMAIN, self._station_id)},
            "name": _station_device_name(station, self._station_id),
            "manufacturer": "PaliwoMapa",
            "model": station.get("station_address") or f"ID {self._station_id}",
            "configuration_url": "https://paliwomapa.pl/",
            "via_device_id": self.coordinator.hub_device_id,
        }


class CheapestFuelSensor(CoordinatorEntity, SensorEntity):
    """Cheapest known price for a fuel across configured stations."""

    _attr_native_unit_of_measurement = "PLN/L"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-check"

    def __init__(self, coordinator, fuel: str) -> None:
        super().__init__(coordinator)
        self._fuel = fuel
        self._attr_name = f"Najtańsze {FUEL_LABELS[fuel]}"
        self._attr_unique_id = f"cheapest_{fuel}"

    def _candidates(self) -> list[tuple[float, dict[str, Any]]]:
        candidates = []
        for station in self.coordinator.data.get("stations", {}).values():
            price = station.get("prices", {}).get(self._fuel)
            if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
                candidates.append((float(price), station))
        return candidates

    @property
    def native_value(self) -> float | None:
        candidates = self._candidates()
        return min((price for price, _ in candidates), default=None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        candidates = self._candidates()
        if not candidates:
            return {"monitored_stations_with_price": 0}
        price, station = min(candidates, key=lambda item: item[0])
        return {
            "station_id": station.get("station_id"),
            "station_name": station.get("station_name"),
            "station_address": station.get("station_address"),
            "station_updated": station.get("updated"),
            "distance_km": station.get("location", {}).get("distance_km"),
            "latitude": station.get("location", {}).get("latitude"),
            "longitude": station.get("location", {}).get("longitude"),
            "monitored_stations_with_price": len(candidates),
            "last_refresh": self.coordinator.data.get("last_refresh"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "paliwomapa_hub")},
            "name": "PaliwoMapa — podsumowanie",
            "manufacturer": "PaliwoMapa",
            "configuration_url": "https://paliwomapa.pl/",
        }


class CheapestFuelStationSensor(CoordinatorEntity, SensorEntity):
    """Human-readable name/address of the station with the lowest price."""

    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator, fuel: str) -> None:
        super().__init__(coordinator)
        self._fuel = fuel
        self._attr_name = f"Stacja z najtańszym {FUEL_LABELS[fuel]}"
        self._attr_unique_id = f"cheapest_station_{fuel}"

    def _winner(self) -> dict[str, Any] | None:
        candidates = []
        for station in self.coordinator.data.get("stations", {}).values():
            price = station.get("prices", {}).get(self._fuel)
            if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
                candidates.append((float(price), station))
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    @property
    def native_value(self) -> str | None:
        station = self._winner()
        if not station:
            return None
        station_id = str(station.get("station_id") or "")
        name = str(station.get("station_name") or f"Stacja {station_id}").strip()
        address = str(station.get("station_address") or "").strip()
        # The state itself must distinguish stations with the same brand.
        # Keep this useful even when PaliwoMapa has no address for a station.
        if address:
            return f"{name} — {address} [{station_id}]"
        return f"{name} [{station_id}]"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        station = self._winner()
        if not station:
            return {"monitored_stations_with_price": 0}
        return {
            "station_id": station.get("station_id"),
            "station_name": station.get("station_name"),
            "station_address": station.get("station_address"),
            "price": station.get("prices", {}).get(self._fuel),
            "price_updated": station.get("price_updated", {}).get(self._fuel),
            "station_updated": station.get("updated"),
            "distance_km": station.get("location", {}).get("distance_km"),
            "latitude": station.get("location", {}).get("latitude"),
            "longitude": station.get("location", {}).get("longitude"),
            **_map_links(station),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "paliwomapa_hub")},
            "name": "PaliwoMapa — podsumowanie",
            "manufacturer": "PaliwoMapa",
            "configuration_url": "https://paliwomapa.pl/",
        }


class AccountProfileSensor(CoordinatorEntity, SensorEntity):
    """Small account summary, only created for account-authenticated setups."""

    _attr_name = "Profil konta"
    _attr_icon = "mdi:account-circle"
    _attr_entity_category = None

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "account_profile"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.api.account_enabled)

    @property
    def native_value(self) -> str | None:
        profile = self.coordinator.data.get("account_profile", {})
        return profile.get("nick") or profile.get("nickname")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile = self.coordinator.data.get("account_profile", {})
        return {key: profile[key] for key in ("points", "streak", "badges") if key in profile}

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "account")},
            "name": "Konto PaliwoMapa",
            "manufacturer": "PaliwoMapa",
            "configuration_url": "https://paliwomapa.pl/",
        }


class LastRefreshSensor(CoordinatorEntity, SensorEntity):
    """Time of the last successful integration refresh."""

    _attr_name = "Ostatnie odświeżenie"
    _attr_unique_id = "last_refresh"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    @property
    def native_value(self):
        return self.coordinator.data.get("last_refresh")

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "paliwomapa_hub")},
            "name": "PaliwoMapa — podsumowanie",
            "manufacturer": "PaliwoMapa",
            "configuration_url": "https://paliwomapa.pl/",
        }
