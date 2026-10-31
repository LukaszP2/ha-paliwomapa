"""Pure parsing and normalization helpers (no Home Assistant dependency)."""
from __future__ import annotations

import re
from typing import Any

_STATION_ID_RE = re.compile(r"^\d{1,20}$")
_URL_STATION_ID_RE = re.compile(r"(?:prices/|station(?:/|=)|station_id=|stationId=|station_id/|[?&]id=)(\d{1,20})(?:\D|$)", re.I)


def validate_station_id(station_id: str) -> str:
    station_id = str(station_id).strip()
    if not _STATION_ID_RE.fullmatch(station_id):
        raise ValueError("ID stacji musi składać się wyłącznie z cyfr.")
    return station_id


def parse_station_ids(raw: str) -> list[str]:
    ids: list[str] = []
    for item in re.split(r"[,\n;]+", raw):
        value = item.strip()
        if not value:
            continue
        match = _URL_STATION_ID_RE.search(value)
        if match:
            value = match.group(1)
        value = validate_station_id(value)
        if value not in ids:
            ids.append(value)
    # Empty selection is allowed: users can finish setup and add stations later.
    return ids


def normalize_station_row(row: Any, requested_id: str | None = None) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("API zwróciło nieprawidłowy rekord stacji.")
    station_id = str(requested_id or row.get("doc_id") or "")
    try:
        station_id = validate_station_id(station_id)
    except ValueError as err:
        raise ValueError("API zwróciło rekord bez poprawnego ID stacji.") from err
    data = row.get("data")
    if not isinstance(data, dict):
        raise ValueError("API zwróciło nieprawidłowe dane stacji.")
    prices: dict[str, float] = {}
    price_updated: dict[str, Any] = {}
    for key in ("pb95", "pb98", "on", "on_plus", "lpg"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            prices[key] = float(value)
            price_updated[key] = data.get(f"ud_{key}") or data.get("updated")
    if not prices:
        raise ValueError(f"Stacja {station_id} nie zawiera rozpoznanych cen paliw.")
    return {
        "station_id": station_id,
        "station_name": str(data.get("stationName") or f"Stacja {station_id}"),
        "station_address": data.get("stationAddr"),
        "updated": data.get("updated") or row.get("updated_at"),
        "prices": prices,
        "price_updated": price_updated,
    }


def normalize_station_response(payload: Any, requested_id: str) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"Nie znaleziono stacji o ID {requested_id}.")
    return normalize_station_row(payload[0], requested_id)


def extract_favorite_station_ids(payload: Any) -> list[str]:
    """Extract station IDs from the favorites document shape used by PaliwoMapa.

    Observed shape:
    [{"path": "favorites/<user_id>", "data": {
        "stations": ["1617103390", ...]
    }}]
    """
    found: list[str] = []
    id_keys = {
        "station_id", "stationId", "stationID", "station_id_str",
        "favorite_station_id", "favoriteStationId", "station_doc_id",
    }
    list_keys = {
        "stations", "station_ids", "stationIds", "favoriteStationIds",
        "favorite_station_ids", "ids", "favorites",
    }

    def add(candidate: Any) -> None:
        if isinstance(candidate, (str, int)) and not isinstance(candidate, bool):
            try:
                station_id = validate_station_id(str(candidate))
            except ValueError:
                return
            if station_id not in found:
                found.append(station_id)

    def walk(value: Any, in_favorites: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in id_keys:
                    add(child)
                elif key in list_keys and isinstance(child, (list, dict)):
                    walk(child, True)
                elif in_favorites and str(key).isdigit():
                    add(key)
                    walk(child, True)
                else:
                    walk(child, in_favorites)
        elif isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    if in_favorites and str(row.get("doc_id", "")).isdigit():
                        add(row["doc_id"])
                    walk(row, in_favorites)
                elif in_favorites:
                    add(row)

    walk(payload)
    return found
