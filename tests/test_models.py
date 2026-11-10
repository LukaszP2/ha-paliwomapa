"""Unit tests for models and normalization logic."""
from __future__ import annotations

import pytest

from custom_components.paliwomapa.models import (
    extract_favorite_station_ids,
    normalize_station_response,
    normalize_station_row,
    parse_station_ids,
    validate_station_id,
)


def test_validate_station_id():
    assert validate_station_id("12345") == "12345"
    assert validate_station_id("  9876543210  ") == "9876543210"

    with pytest.raises(ValueError, match="ID stacji musi składać się wyłącznie z cyfr"):
        validate_station_id("abc")

    with pytest.raises(ValueError, match="ID stacji musi składać się wyłącznie z cyfr"):
        validate_station_id("")

    with pytest.raises(ValueError, match="ID stacji musi składać się wyłącznie z cyfr"):
        validate_station_id("12-34")


def test_parse_station_ids():
    raw = """
        11111, 22222; 33333
        https://paliwomapa.pl/prices/44444
        https://paliwomapa.pl/station?id=55555
        11111
    """
    parsed = parse_station_ids(raw)
    assert parsed == ["11111", "22222", "33333", "44444", "55555"]


def test_normalize_station_row_full():
    row = {
        "doc_id": "161710",
        "data": {
            "stationName": "Orlen Warszawa",
            "stationAddr": "ul. Marszałkowska 1",
            "updated": "2026-11-06T08:00:00Z",
            "pb95": 6.55,
            "pb98": 7.15,
            "on": 6.69,
            "on_plus": 6.99,
            "lpg": 2.99,
            "ud_pb95": "2026-11-06T07:30:00Z",
        },
    }
    normalized = normalize_station_row(row)
    assert normalized["station_id"] == "161710"
    assert normalized["station_name"] == "Orlen Warszawa"
    assert normalized["station_address"] == "ul. Marszałkowska 1"
    assert normalized["prices"] == {
        "pb95": 6.55,
        "pb98": 7.15,
        "on": 6.69,
        "on_plus": 6.99,
        "lpg": 2.99,
    }
    assert normalized["price_updated"]["pb95"] == "2026-11-06T07:30:00Z"
    assert normalized["price_updated"]["pb98"] == "2026-11-06T08:00:00Z"


def test_normalize_station_row_empty_prices():
    # Stations without prices should not raise ValueError anymore (FIX-09)
    row = {
        "doc_id": "99999",
        "data": {
            "stationName": "Nowa Stacja",
            "stationAddr": "Kraków",
            "pb95": 0,
            "on": None,
        },
    }
    normalized = normalize_station_row(row)
    assert normalized["station_id"] == "99999"
    assert normalized["station_name"] == "Nowa Stacja"
    assert normalized["prices"] == {}


def test_normalize_station_row_invalid():
    with pytest.raises(TypeError):
        normalize_station_row("not a dict")

    with pytest.raises(ValueError):
        normalize_station_row({"doc_id": "invalid_id", "data": {}})

    with pytest.raises(TypeError):
        normalize_station_row({"doc_id": "12345", "data": "not a dict"})


def test_normalize_station_response():
    row = {
        "doc_id": "123",
        "data": {"stationName": "Shell", "pb95": 6.49},
    }
    result = normalize_station_response([row], "123")
    assert result["station_id"] == "123"
    assert result["prices"]["pb95"] == 6.49

    with pytest.raises(ValueError, match="Nie znaleziono stacji o ID 999"):
        normalize_station_response([], "999")

    with pytest.raises(ValueError, match="Nie znaleziono stacji o ID 123"):
        normalize_station_response([row, row], "123")


def test_extract_favorite_station_ids():
    payload = [
        {
            "path": "favorites/user_abc",
            "data": {
                "stations": ["1001", "1002", 1003, "invalid_id"],
            },
        },
        {
            "path": "favorites/user_abc",
            "data": {
                "favorite_station_id": "1004",
            },
        },
    ]
    extracted = extract_favorite_station_ids(payload)
    assert extracted == ["1001", "1002", "1003", "1004"]
