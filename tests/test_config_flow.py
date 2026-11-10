"""Unit tests for PaliwoMapa config flow and options flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.paliwomapa.config_flow import (
    PaliwoMapaConfigFlow,
    PaliwoMapaOptionsFlow,
)
from custom_components.paliwomapa.const import (
    AUTH_ACCOUNT,
    AUTH_NONE,
    CONF_AUTH_MODE,
    CONF_EMAIL,
    CONF_FUEL_TYPES,
    CONF_PASSWORD,
    CONF_STATION_IDS,
    CONF_STATION_LOCATIONS,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.config.latitude = 52.2297
    hass.config.longitude = 21.0122
    hass.client_session = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_step_user_shows_form(mock_hass):
    """Test initial user step displays auth mode form."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_anonymous_mode_success(mock_hass):
    """Test end-to-end anonymous setup with manual stations."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass

    # Step 1: User selects anonymous mode
    result_user = await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})
    assert result_user["type"] == "form"
    assert result_user["step_id"] == "stations"

    # Step 2: User provides station ID manually
    mock_station = {
        "123": {
            "station_id": "123",
            "station_name": "Orlen Warszawa",
            "prices": {"pb95": 6.50},
        }
    }
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_station),
    ):
        result_stations = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "123"}
        )

    assert result_stations["type"] == "form"
    assert result_stations["step_id"] == "fuels"
    assert flow.unique_id == "paliwomapa_instance"
    assert flow._pending_title == "PaliwoMapa — Orlen Warszawa"

    # Step 3: User confirms fuel selection
    result_fuels = await flow.async_step_fuels(
        user_input={CONF_FUEL_TYPES: ["pb95", "on"]}
    )
    assert result_fuels["type"] == "create_entry"
    assert result_fuels["title"] == "PaliwoMapa — Orlen Warszawa"
    assert result_fuels["data"][CONF_AUTH_MODE] == AUTH_NONE
    assert result_fuels["data"][CONF_STATION_IDS] == ["123"]
    assert result_fuels["data"][CONF_FUEL_TYPES] == ["pb95", "on"]


@pytest.mark.asyncio
async def test_anonymous_mode_empty_stations(mock_hass):
    """Test anonymous setup without any stations entered."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass

    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    result_stations = await flow.async_step_stations(
        user_input={"source": "manual", CONF_STATION_IDS: ""}
    )
    assert result_stations["type"] == "form"
    assert result_stations["step_id"] == "fuels"
    assert flow._pending_title == "PaliwoMapa"

    result_fuels = await flow.async_step_fuels(
        user_input={CONF_FUEL_TYPES: ["pb95"]}
    )
    assert result_fuels["type"] == "create_entry"
    assert result_fuels["data"][CONF_STATION_IDS] == []


@pytest.mark.asyncio
async def test_account_mode_login_and_favorites(mock_hass):
    """Test account mode with login and automatic favorites import."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass

    # Step 1: User selects account mode
    result_user = await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_ACCOUNT})
    assert result_user["type"] == "form"
    assert result_user["step_id"] == "account"

    # Step 2: Account credentials entered
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(return_value={"access_token": "token123"}),
    ):
        result_account = await flow.async_step_account(
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret_password"}
        )
    assert result_account["type"] == "form"
    assert result_account["step_id"] == "stations"

    # Step 3: Stations step with favorites fetched
    mock_stations = {
        "101": {"station_id": "101", "station_name": "BP Central"},
        "102": {"station_id": "102", "station_name": "Shell West"},
    }
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_favorite_station_ids",
        new=AsyncMock(return_value=["101", "102"]),
    ), patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_stations),
    ):
        result_stations = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "101, 102"}
        )

    assert result_stations["type"] == "form"
    assert result_stations["step_id"] == "fuels"
    assert flow.unique_id == "paliwomapa_user@example.com"
    assert flow._pending_title == "PaliwoMapa — 2 stacji"

    # Step 4: Complete fuels step
    result_fuels = await flow.async_step_fuels(
        user_input={CONF_FUEL_TYPES: ["pb95", "lpg"]}
    )
    assert result_fuels["type"] == "create_entry"
    assert result_fuels["data"][CONF_EMAIL] == "user@example.com"
    assert result_fuels["data"][CONF_STATION_IDS] == ["101", "102"]


@pytest.mark.asyncio
async def test_account_mode_login_failure(mock_hass):
    """Test account mode with invalid credentials displays error."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass

    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_ACCOUNT})

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(side_effect=HomeAssistantError("Login failed")),
    ):
        result = await flow.async_step_account(
            user_input={CONF_EMAIL: "wrong@example.com", CONF_PASSWORD: "wrong"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "account"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_stations_invalid_ids_format(mock_hass):
    """Test handling of invalid station format string."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    with patch(
        "custom_components.paliwomapa.config_flow.parse_station_ids",
        side_effect=ValueError("Invalid station ID format"),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "abc###"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "invalid_station_ids"}


@pytest.mark.asyncio
async def test_stations_some_unavailable(mock_hass):
    """Test error when some requested stations cannot be found."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    # User requested 101 and 102, but API only returned 101
    mock_found = {"101": {"station_id": "101", "station_name": "Orlen"}}
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_found),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "101, 102"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "some_stations_unavailable"}


@pytest.mark.asyncio
async def test_stations_cannot_connect(mock_hass):
    """Test connection error handling during stations fetch."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(side_effect=HomeAssistantError("Connection timed out")),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "101"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_nearby_search_missing_home_location(mock_hass):
    """Test error when home coordinates are not set in HA."""
    mock_hass.config.latitude = 0
    mock_hass.config.longitude = 0

    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    result = await flow.async_step_stations(
        user_input={"source": "nearby", "radius_km": 15}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "home_location_missing"}


@pytest.mark.asyncio
async def test_nearby_search_no_stations(mock_hass):
    """Test handling when no stations are found in radius."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_search_nearby_stations",
        new=AsyncMock(return_value=[]),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "nearby", "radius_km": 10}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "no_nearby_stations"}


@pytest.mark.asyncio
async def test_nearby_search_connection_error(mock_hass):
    """Test handling when nearby search fails due to API error."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_search_nearby_stations",
        new=AsyncMock(side_effect=HomeAssistantError("Search error")),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "nearby", "radius_km": 10}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "stations"
    assert result["errors"] == {"base": "nearby_search_failed"}


@pytest.mark.asyncio
async def test_nearby_search_and_select_flow(mock_hass):
    """Test successful nearby search and selection of stations."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_NONE})

    mock_nearby = [
        {
            "station_id": "201",
            "station_name": "Shell Bliska",
            "station_address": "ul. Prosta 1",
            "latitude": 52.23,
            "longitude": 21.02,
            "distance_km": 1.5,
            "prices": {"pb95": 6.45},
        }
    ]

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_search_nearby_stations",
        new=AsyncMock(return_value=mock_nearby),
    ):
        result_search = await flow.async_step_stations(
            user_input={"source": "nearby", "radius_km": 10}
        )

    assert result_search["type"] == "form"
    assert result_search["step_id"] == "select_nearby"

    # Test submitting with empty selection
    result_empty = await flow.async_step_select_nearby(user_input={"station_ids": []})
    assert result_empty["type"] == "form"
    assert result_empty["errors"] == {"base": "select_at_least_one_station"}

    # Test selecting the nearby station
    result_selected = await flow.async_step_select_nearby(
        user_input={"station_ids": ["201"]}
    )
    assert result_selected["type"] == "form"
    assert result_selected["step_id"] == "fuels"
    assert flow._pending_data[CONF_STATION_LOCATIONS]["201"]["distance_km"] == 1.5

    result_fuels = await flow.async_step_fuels(user_input={CONF_FUEL_TYPES: ["pb95"]})
    assert result_fuels["type"] == "create_entry"
    assert result_fuels["data"][CONF_STATION_IDS] == ["201"]


@pytest.mark.asyncio
async def test_fuels_empty_selection_validation(mock_hass):
    """Test validation when no fuel types are selected."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    flow._pending_data = {CONF_AUTH_MODE: AUTH_NONE, CONF_STATION_IDS: []}

    result = await flow.async_step_fuels(user_input={CONF_FUEL_TYPES: []})
    assert result["type"] == "form"
    assert result["step_id"] == "fuels"
    assert result["errors"] == {"base": "select_at_least_one_fuel"}


@pytest.mark.asyncio
async def test_reauth_successful(mock_hass):
    """Test successful reauthorization with updated password."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "entry_123"}

    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_AUTH_MODE: AUTH_ACCOUNT,
        CONF_EMAIL: "existing@example.com",
        CONF_PASSWORD: "old_password",
    }
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    result_init = await flow.async_step_reauth(entry_data=mock_entry.data)
    assert result_init["type"] == "form"
    assert result_init["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(return_value={"access_token": "new_token"}),
    ):
        result_confirm = await flow.async_step_reauth_confirm(
            user_input={CONF_PASSWORD: "new_secret_password"}
        )

    assert result_confirm["type"] == "abort"
    assert result_confirm["reason"] == "reauth_successful"
    assert result_confirm["data"][CONF_PASSWORD] == "new_secret_password"


@pytest.mark.asyncio
async def test_reauth_invalid_credentials(mock_hass):
    """Test reauthorization failure when invalid password is provided."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "entry_123"}

    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_AUTH_MODE: AUTH_ACCOUNT,
        CONF_EMAIL: "existing@example.com",
        CONF_PASSWORD: "old_password",
    }
    mock_hass.config_entries.async_get_entry.return_value = mock_entry
    await flow.async_step_reauth(entry_data=mock_entry.data)

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(side_effect=HomeAssistantError("Invalid credentials")),
    ):
        result = await flow.async_step_reauth_confirm(
            user_input={CONF_PASSWORD: "bad_password"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_options_flow_save_fuels(mock_hass):
    """Test options flow saving updated fuel selection."""
    mock_entry = MagicMock()
    mock_entry.options = {CONF_FUEL_TYPES: ["pb95"]}
    mock_entry.data = {CONF_STATION_IDS: ["101"]}

    options_flow = PaliwoMapaConfigFlow.async_get_options_flow(mock_entry)
    options_flow.hass = mock_hass

    result = await options_flow.async_step_init(
        user_input={"action": "save_fuels", CONF_FUEL_TYPES: ["pb95", "on"]}
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_FUEL_TYPES] == ["pb95", "on"]
    assert result["data"][CONF_STATION_IDS] == ["101"]


@pytest.mark.asyncio
async def test_options_flow_add_station(mock_hass):
    """Test options flow adding a new station."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {CONF_STATION_IDS: ["101"]}

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    mock_station = {"102": {"station_id": "102", "station_name": "Orlen Nowy"}}
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_station),
    ):
        result = await options_flow.async_step_init(
            user_input={
                "action": "add",
                CONF_STATION_IDS: "102",
                CONF_FUEL_TYPES: ["pb95"],
            }
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_STATION_IDS] == ["101", "102"]


@pytest.mark.asyncio
async def test_options_flow_remove_station(mock_hass):
    """Test options flow removing an existing station."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {CONF_STATION_IDS: ["101", "102"]}

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    result = await options_flow.async_step_init(
        user_input={
            "action": "remove",
            CONF_STATION_IDS: "101",
            CONF_FUEL_TYPES: ["pb95"],
        }
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_STATION_IDS] == ["102"]


@pytest.mark.asyncio
async def test_reconfigure_success(mock_hass):
    """Test reconfiguring integration credentials."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "entry_456"}

    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_AUTH_MODE: AUTH_ACCOUNT,
        CONF_EMAIL: "old@example.com",
        CONF_PASSWORD: "old_password",
    }
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    result_form = await flow.async_step_reconfigure(user_input=None)
    assert result_form["type"] == "form"
    assert result_form["step_id"] == "reconfigure"

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(return_value={"access_token": "reconf_token"}),
    ):
        result = await flow.async_step_reconfigure(
            user_input={
                CONF_EMAIL: "new@example.com",
                CONF_PASSWORD: "new_password",
            }
        )

    assert result["type"] == "abort"
    assert result["data"][CONF_EMAIL] == "new@example.com"
    assert result["data"][CONF_PASSWORD] == "new_password"


@pytest.mark.asyncio
async def test_reconfigure_invalid_credentials(mock_hass):
    """Test reconfigure error on invalid credentials."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "entry_456"}

    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_AUTH_MODE: AUTH_ACCOUNT,
        CONF_EMAIL: "old@example.com",
        CONF_PASSWORD: "old_password",
    }
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(side_effect=HomeAssistantError("Login failed")),
    ):
        result = await flow.async_step_reconfigure(
            user_input={
                CONF_EMAIL: "wrong@example.com",
                CONF_PASSWORD: "wrong_password",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_account_mode_favorites_error_graceful(mock_hass):
    """Test account mode continues gracefully if favorites API call fails."""
    flow = PaliwoMapaConfigFlow()
    flow.hass = mock_hass
    await flow.async_step_user(user_input={CONF_AUTH_MODE: AUTH_ACCOUNT})

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_login",
        new=AsyncMock(return_value={"access_token": "tok"}),
    ):
        await flow.async_step_account(
            user_input={CONF_EMAIL: "u@example.com", CONF_PASSWORD: "pass"}
        )

    mock_stations = {"101": {"station_id": "101", "station_name": "Orlen 101"}}
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_favorite_station_ids",
        new=AsyncMock(side_effect=HomeAssistantError("Favorites error")),
    ), patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_stations),
    ):
        result = await flow.async_step_stations(
            user_input={"source": "manual", CONF_STATION_IDS: "101"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "fuels"
    assert flow.unique_id == "paliwomapa_u@example.com"


@pytest.mark.asyncio
async def test_options_flow_import_favorites_success(mock_hass):
    """Test importing favorites in options flow."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret_password",
        CONF_STATION_IDS: ["101"],
    }

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    mock_new_stations = {"102": {"station_id": "102", "station_name": "Lotos 102"}}
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_favorite_station_ids",
        new=AsyncMock(return_value=["101", "102"]),
    ), patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_new_stations),
    ):
        result = await options_flow.async_step_init(
            user_input={"action": "import_favorites", CONF_FUEL_TYPES: ["pb95"]}
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_STATION_IDS] == ["101", "102"]


@pytest.mark.asyncio
async def test_options_flow_import_favorites_without_account(mock_hass):
    """Test importing favorites without account credentials returns error."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {CONF_AUTH_MODE: AUTH_NONE, CONF_STATION_IDS: ["101"]}

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    result = await options_flow.async_step_init(
        user_input={"action": "import_favorites", CONF_FUEL_TYPES: ["pb95"]}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "account_required_for_favorites"}


@pytest.mark.asyncio
async def test_options_flow_replace_stations(mock_hass):
    """Test replacing all stations in options flow."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {CONF_STATION_IDS: ["101", "102"]}

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    mock_station = {"201": {"station_id": "201", "station_name": "Shell 201"}}
    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_get_stations",
        new=AsyncMock(return_value=mock_station),
    ):
        result = await options_flow.async_step_init(
            user_input={
                "action": "replace",
                CONF_STATION_IDS: "201",
                CONF_FUEL_TYPES: ["pb95"],
            }
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_STATION_IDS] == ["201"]


@pytest.mark.asyncio
async def test_options_flow_nearby_search_and_select(mock_hass):
    """Test searching and adding nearby stations from options flow."""
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {CONF_STATION_IDS: ["101"]}

    options_flow = PaliwoMapaOptionsFlow(mock_entry)
    options_flow.hass = mock_hass

    mock_nearby = [
        {
            "station_id": "301",
            "station_name": "Moya 301",
            "latitude": 52.25,
            "longitude": 21.05,
            "distance_km": 2.1,
            "prices": {"pb95": 6.39},
        }
    ]

    with patch(
        "custom_components.paliwomapa.config_flow.PaliwoMapaApi.async_search_nearby_stations",
        new=AsyncMock(return_value=mock_nearby),
    ):
        result_search = await options_flow.async_step_init(
            user_input={
                "action": "search_nearby",
                "radius_km": 10,
                CONF_FUEL_TYPES: ["pb95"],
            }
        )

    assert result_search["type"] == "form"
    assert result_search["step_id"] == "select_nearby"

    result_select = await options_flow.async_step_select_nearby(
        user_input={"station_ids": ["301"]}
    )

    assert result_select["type"] == "create_entry"
    assert result_select["data"][CONF_STATION_IDS] == ["101", "301"]
    assert "301" in result_select["data"][CONF_STATION_LOCATIONS]

