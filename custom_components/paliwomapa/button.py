"""Manual refresh button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PaliwoMapaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([RefreshPricesButton(entry.runtime_data)])


class RefreshPricesButton(CoordinatorEntity[PaliwoMapaCoordinator], ButtonEntity):
    """Refresh all configured stations on demand."""

    _attr_has_entity_name = True
    _attr_name = "Odśwież ceny"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: PaliwoMapaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "refresh_all_prices"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "paliwomapa_hub")},
            "name": "PaliwoMapa — podsumowanie",
            "manufacturer": "PaliwoMapa",
            "configuration_url": "https://paliwomapa.pl/",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
