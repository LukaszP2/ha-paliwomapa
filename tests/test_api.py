"""Unit tests for PaliwoMapaApi client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.paliwomapa.api import (
    PaliwoMapaApi,
    PaliwoMapaApiError,
    PaliwoMapaAuthError,
)


def test_api_validate_station_id():
    api = PaliwoMapaApi(MagicMock())
    assert api.validate_station_id("12345") == "12345"

    with pytest.raises(PaliwoMapaApiError):
        api.validate_station_id("invalid")


def test_api_parse_station_response():
    api = PaliwoMapaApi(MagicMock())
    raw_payload = [
        {
            "doc_id": "100",
            "data": {
                "stationName": "Orlen",
                "pb95": 6.50,
            },
        }
    ]
    parsed = api.parse_station_response(raw_payload, "100")
    assert parsed["station_id"] == "100"
    assert parsed["station_name"] == "Orlen"
    assert parsed["prices"]["pb95"] == 6.50

    with pytest.raises(PaliwoMapaApiError):
        api.parse_station_response([], "100")


@pytest.mark.asyncio
async def test_api_relogin_on_401():
    """Verify that when token expires (401), api clears token and logs in again."""
    session = MagicMock()
    api = PaliwoMapaApi(session, email="test@example.com", password="secret_password")
    api._access_token = "expired_token"
    api._user_id = "user_123"

    # Mock response objects
    # 1st call: GET /rest/v1/app_docs with expired token returns 401
    resp_401 = MagicMock()
    resp_401.status = 401

    # 2nd call: POST /auth/v1/token returns new token
    resp_login = MagicMock()
    resp_login.status = 200
    resp_login.raise_for_status = MagicMock()
    resp_login.json = AsyncMock(return_value={
        "access_token": "new_token_456",
        "refresh_token": "refresh_789",
        "user": {"id": "user_123"},
    })

    # 3rd call: retried GET /rest/v1/app_docs returns 200 with data
    resp_success = MagicMock()
    resp_success.status = 200
    resp_success.raise_for_status = MagicMock()
    resp_success.json = AsyncMock(return_value=[
        {
            "doc_id": "100",
            "data": {"stationName": "Orlen", "pb95": 6.50},
        }
    ])

    # Context managers
    cm_401 = MagicMock()
    cm_401.__aenter__ = AsyncMock(return_value=resp_401)
    cm_401.__aexit__ = AsyncMock(return_value=None)

    cm_login = MagicMock()
    cm_login.__aenter__ = AsyncMock(return_value=resp_login)
    cm_login.__aexit__ = AsyncMock(return_value=None)

    cm_success = MagicMock()
    cm_success.__aenter__ = AsyncMock(return_value=resp_success)
    cm_success.__aexit__ = AsyncMock(return_value=None)

    session.request = MagicMock(side_effect=[cm_401, cm_login, cm_success])

    station = await api.async_get_station("100")
    assert station["station_id"] == "100"
    assert api._access_token == "new_token_456"
    assert session.request.call_count == 3


@pytest.mark.asyncio
async def test_api_login_missing_credentials():
    session = MagicMock()
    api = PaliwoMapaApi(session)
    with pytest.raises(PaliwoMapaAuthError, match="Nie skonfigurowano danych konta"):
        await api.async_login()


@pytest.mark.asyncio
async def test_api_search_nearby_stations_fallback():
    session = MagicMock()
    api = PaliwoMapaApi(session)

    # 1st Overpass call: HTTP 502
    resp_502 = MagicMock()
    resp_502.status = 502
    resp_502.text = AsyncMock(return_value="Gateway Timeout")

    # 2nd Overpass call: HTTP 200 with elements
    resp_ok = MagicMock()
    resp_ok.status = 200
    resp_ok.json = AsyncMock(return_value={
        "elements": [
            {
                "type": "node",
                "id": 1001,
                "lat": 52.23,
                "lon": 21.01,
                "tags": {"name": "Orlen"},
            }
        ]
    })

    cm_502 = MagicMock()
    cm_502.__aenter__ = AsyncMock(return_value=resp_502)
    cm_502.__aexit__ = AsyncMock(return_value=None)

    cm_ok = MagicMock()
    cm_ok.__aenter__ = AsyncMock(return_value=resp_ok)
    cm_ok.__aexit__ = AsyncMock(return_value=None)

    session.post = MagicMock(side_effect=[cm_502, cm_ok])

    # Mock async_get_stations for prices
    api.async_get_stations = AsyncMock(return_value={
        "1001": {
            "station_id": "1001",
            "station_name": "Orlen",
            "prices": {"pb95": 6.50},
            "updated_at": "2026-11-07T00:00:00Z",
        }
    })

    results = await api.async_search_nearby_stations(52.2297, 21.0122, 10.0)
    assert len(results) == 1
    assert results[0]["station_id"] == "1001"
    assert results[0]["station_name"] == "Orlen"
    assert session.post.call_count == 2


@pytest.mark.asyncio
async def test_api_get_stations_skips_malformed_rows():
    """Verify that malformed rows raising TypeError or ValueError are skipped gracefully."""
    session = MagicMock()
    api = PaliwoMapaApi(session)

    resp_ok = MagicMock()
    resp_ok.status = 200
    resp_ok.raise_for_status = MagicMock()
    # Batch response containing:
    # 1. Valid station "100"
    # 2. Malformed row raising TypeError (data is string instead of dict)
    # 3. Malformed row raising TypeError (row is string instead of dict)
    # 4. Malformed row raising ValueError (invalid station id)
    # 5. Valid station "200"
    resp_ok.json = AsyncMock(return_value=[
        {"doc_id": "100", "data": {"stationName": "Orlen", "pb95": 6.50}},
        {"doc_id": "101", "data": "not_a_dict"},
        "not_even_a_dict",
        {"doc_id": "invalid_id_###", "data": {"stationName": "Bad", "pb95": 6.00}},
        {"doc_id": "200", "data": {"stationName": "BP", "pb95": 6.60}},
    ])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp_ok)
    cm.__aexit__ = AsyncMock(return_value=None)
    session.request = MagicMock(return_value=cm)

    stations = await api.async_get_stations(["100", "101", "200"])
    assert "100" in stations
    assert "200" in stations
    assert "101" not in stations
    assert stations["100"]["station_name"] == "Orlen"
    assert stations["200"]["station_name"] == "BP"


