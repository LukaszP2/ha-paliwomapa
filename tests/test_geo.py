"""Unit tests for geographic calculations and Overpass query parser."""
from __future__ import annotations

import pytest

from custom_components.paliwomapa.geo import (
    build_overpass_query,
    haversine_km,
    parse_overpass_stations,
)


def test_haversine_km():
    # Distance between Warsaw (52.2297, 21.0122) and Poznan (52.4064, 16.9252) is ~278.5 km
    dist = haversine_km(52.2297, 21.0122, 52.4064, 16.9252)
    assert 275.0 < dist < 282.0

    # Distance to self is 0
    assert haversine_km(52.0, 21.0, 52.0, 21.0) == 0.0

    with pytest.raises(ValueError, match="Invalid latitude"):
        haversine_km(95.0, 0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="Invalid longitude"):
        haversine_km(0.0, -190.0, 0.0, 0.0)


def test_build_overpass_query():
    query = build_overpass_query(52.2297, 21.0122, 10.0)
    assert "around:10000,52.2297000,21.0122000" in query
    assert 'node["amenity"="fuel"]' in query
    assert 'way["amenity"="fuel"]' in query
    assert 'relation["amenity"="fuel"]' in query

    with pytest.raises(ValueError, match="Promień wyszukiwania musi mieścić się w zakresie 1–50 km"):
        build_overpass_query(52.0, 21.0, 0.5)

    with pytest.raises(ValueError, match="Promień wyszukiwania musi mieścić się w zakresie 1–50 km"):
        build_overpass_query(52.0, 21.0, 60.0)


def test_parse_overpass_stations():
    origin_lat, origin_lon = 52.2297, 21.0122

    payload = {
        "elements": [
            {
                "type": "node",
                "id": 1001,
                "lat": 52.2300,
                "lon": 21.0130,
                "tags": {
                    "name": "Orlen Centrum",
                    "addr:street": "Marszałkowska",
                    "addr:housenumber": "10",
                    "addr:city": "Warszawa",
                },
            },
            {
                "type": "way",
                "id": 2002,
                "center": {"lat": 52.2400, "lon": 21.0200},
                "tags": {"brand": "Shell"},
            },
            {
                "type": "node",
                "id": 3003,
                "lat": 54.0000,  # Far away (~200 km)
                "lon": 21.0000,
                "tags": {"name": "BP Daleko"},
            },
        ]
    }

    stations = parse_overpass_stations(payload, origin_lat, origin_lon, radius_km=10.0)
    assert len(stations) == 2
    assert stations[0]["station_id"] == "1001"
    assert stations[0]["osm_name"] == "Orlen Centrum"
    assert "Marszałkowska" in stations[0]["osm_address"]
    assert stations[1]["station_id"] == "2002"
    assert stations[1]["osm_name"] == "Shell"
    assert stations[0]["distance_km"] <= stations[1]["distance_km"]


def test_parse_overpass_stations_invalid_payload():
    with pytest.raises(TypeError):
        parse_overpass_stations("invalid", 52.0, 21.0, 10.0)

    with pytest.raises(TypeError):
        parse_overpass_stations({"elements": "not a list"}, 52.0, 21.0, 10.0)
