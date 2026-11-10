"""Constants for PaliwoMapa."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "paliwomapa"
PLATFORMS: Final = ["sensor", "button"]
CONF_AUTH_MODE: Final = "auth_mode"
CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_STATION_IDS: Final = "station_ids"
CONF_FUEL_TYPES: Final = "fuel_types"
CONF_STATION_LOCATIONS: Final = "station_locations"
AUTH_NONE: Final = "none"
AUTH_ACCOUNT: Final = "account"
SUPABASE_URL: Final = "https://hcxxwweqkkjspytgyool.supabase.co"
# Supabase publishable/anon key observed in the web app. It is not a user secret.
SUPABASE_API_KEY: Final = "sb_publishable_HeTnHlo6wWxGZKk02pYO8w_UsYG0PuP"
REQUEST_TIMEOUT: Final = 20
OVERPASS_TIMEOUT: Final = 30
OVERPASS_URLS: Final = (
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
DEFAULT_UPDATE_INTERVAL_HOURS: Final = 2
FUEL_LABELS: Final = {
    "pb95": "PB95",
    "pb98": "PB98",
    "on": "ON",
    "on_plus": "ON premium",
    "lpg": "LPG",
}
