"""Geographic helpers for local fuel-station discovery."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres."""
    for value, low, high, label in (
        (lat1, -90, 90, "latitude"), (lat2, -90, 90, "latitude"),
        (lon1, -180, 180, "longitude"), (lon2, -180, 180, "longitude"),
    ):
        if not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(f"Invalid {label}")
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1.0, a)))


def build_overpass_query(latitude: float, longitude: float, radius_km: float) -> str:
    """Build an Overpass query; its `around` distance is expressed in metres."""
    if not 1 <= float(radius_km) <= 50:
        raise ValueError("Promień wyszukiwania musi mieścić się w zakresie 1–50 km.")
    radius_m = round(float(radius_km) * 1000)
    return (
        f'[out:json][timeout:25];('
        f'node["amenity"="fuel"](around:{radius_m},{float(latitude):.7f},{float(longitude):.7f});'
        f'way["amenity"="fuel"](around:{radius_m},{float(latitude):.7f},{float(longitude):.7f});'
        f'relation["amenity"="fuel"](around:{radius_m},{float(latitude):.7f},{float(longitude):.7f});'
        f');out center tags;'
    )


def parse_overpass_stations(payload: Any, origin_lat: float, origin_lon: float, radius_km: float) -> list[dict[str, Any]]:
    """Normalize Overpass fuel POIs and retain stations inside the requested radius."""
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise TypeError("Nieprawidłowa odpowiedź wyszukiwania stacji.")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload["elements"]:
        if not isinstance(item, dict) or item.get("type") not in ("node", "way", "relation"):
            continue
        station_id = str(item.get("id", ""))
        if not station_id.isdigit() or station_id in seen:
            continue
        raw_tags = item.get("tags")
        tags: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
        lat = item.get("lat")
        lon = item.get("lon")
        if (lat is None or lon is None) and isinstance(item.get("center"), dict):
            center = item["center"]
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            distance = haversine_km(origin_lat, origin_lon, lat_f, lon_f)
        except (TypeError, ValueError):
            continue
        if distance > radius_km:
            continue
        seen.add(station_id)
        osm_name = tags.get("name") or tags.get("brand") or tags.get("operator")
        addr_parts = [str(tags[k]) for k in ("addr:street", "addr:housenumber", "addr:city") if tags.get(k)]
        osm_address = ", ".join(addr_parts) or None
        results.append({
            "station_id": station_id,
            "latitude": lat_f,
            "longitude": lon_f,
            "distance_km": round(distance, 2),
            "osm_name": osm_name,
            "osm_address": osm_address,
        })
    return sorted(results, key=lambda row: row["distance_km"])
