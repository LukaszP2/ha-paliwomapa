"""PaliwoMapa integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

from .api import PaliwoMapaApi
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_STATION_IDS, CONF_STATION_LOCATIONS, PLATFORMS
from .coordinator import PaliwoMapaCoordinator

import logging

_LOGGER = logging.getLogger(__name__)
_CARD_URL = "/paliwomapa/paliwomapa-card.js"


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Serve the card and register it as a Lovelace resource when possible.

    Resource registration is automatic for storage-mode dashboards. YAML-mode
    dashboards intentionally remain user-managed, as Home Assistant does not
    expose a supported integration API to mutate their resource list.
    """
    card_dir = Path(__file__).parent / "www"
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL.rsplit("/", 1)[0], str(card_dir), False)]
        )
    except RuntimeError:
        # Static URL can already be registered after a config-entry reload.
        _LOGGER.debug("PaliwoMapa card static path is already registered")

    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None) if lovelace else None
    if lovelace is None or resources is None:
        _LOGGER.debug("Lovelace resource manager is not available; card is served at %s", _CARD_URL)
        return

    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
        existing = resources.async_items()
        if any(
            item.get("url", "").split("?", 1)[0].rstrip("/") == _CARD_URL
            for item in existing
        ):
            _LOGGER.debug("PaliwoMapa Lovelace resource already exists")
            return
        create_item = getattr(resources, "async_create_item", None)
        if create_item is None:
            _LOGGER.warning(
                "PaliwoMapa card is served at %s, but this Lovelace resource mode is YAML-managed; add it to lovelace.resources manually.",
                _CARD_URL,
            )
            return
        await create_item({"res_type": "module", "url": _CARD_URL})
        _LOGGER.info("Registered PaliwoMapa Lovelace card automatically")
    except Exception:  # noqa: BLE001 - don't break integration setup for UI resource issues
        _LOGGER.warning(
            "Could not register PaliwoMapa card automatically. Add %s as a JavaScript module resource in Lovelace settings.",
            _CARD_URL,
            exc_info=True,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = PaliwoMapaApi(
        async_get_clientsession(hass),
        entry.data.get(CONF_EMAIL), entry.data.get(CONF_PASSWORD),
    )
    # Backward compatibility with the first prototype, which stored a single
    # station under ``station_id`` instead of ``station_ids``.
    raw_station_ids = entry.data.get(CONF_STATION_IDS)
    if raw_station_ids is None:
        legacy_id = entry.data.get("station_id")
        raw_station_ids = [legacy_id] if legacy_id else []
    elif isinstance(raw_station_ids, str):
        raw_station_ids = [raw_station_ids]
    coordinator = PaliwoMapaCoordinator(hass, api, list(raw_station_ids), entry.data.get(CONF_STATION_LOCATIONS, {}))
    # Register a stable parent device so station and summary devices form a real hierarchy.
    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("paliwomapa", "paliwomapa_hub")},
        name="PaliwoMapa — podsumowanie",
        manufacturer="PaliwoMapa",
        configuration_url="https://paliwomapa.pl/",
    )
    coordinator.hub_device_id = hub_device.id
    await _async_register_frontend_card(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
