"""Pytest configuration and mocks for isolated test runs without full Home Assistant."""
from __future__ import annotations

import importlib.util
import sys
from unittest.mock import MagicMock


class HomeAssistantError(Exception):
    """Mock HomeAssistantError base exception."""


class ConfigEntryAuthFailed(HomeAssistantError):
    """Mock ConfigEntryAuthFailed."""


class UpdateFailed(HomeAssistantError):
    """Mock UpdateFailed."""


# If voluptuous is not installed, mock it so config_flow can be imported.
if "voluptuous" not in sys.modules and importlib.util.find_spec("voluptuous") is None:
    class MockMarker:
        def __init__(self, key, default=None):
            self.key = key
            self.default = default

        def __call__(self, val):
            return val

    class MockSchema:
        def __init__(self, schema):
            self.schema = schema

        def __call__(self, val):
            return val

    vol_mock = MagicMock()
    vol_mock.Schema = MockSchema
    vol_mock.Required = MockMarker
    vol_mock.Optional = MockMarker
    vol_mock.In = lambda container: (lambda val: val)
    vol_mock.All = lambda *validators: (lambda val: val)
    vol_mock.Coerce = lambda type_: (lambda val: type_(val))
    vol_mock.Range = lambda min=None, max=None: (lambda val: val)
    sys.modules["voluptuous"] = vol_mock

# If aiohttp is not installed, mock basic classes so modules can be imported.
if "aiohttp" not in sys.modules and importlib.util.find_spec("aiohttp") is None:
    class ClientError(Exception):
        pass

    class ClientResponseError(ClientError):
        def __init__(self, *args, status=None, message="", **kwargs):
            super().__init__(*args, **kwargs)
            self.status = status
            self.message = message

    class ClientTimeout:
        def __init__(self, total=None, **kwargs):
            self.total = total

    aiohttp_mock = MagicMock()
    aiohttp_mock.ClientError = ClientError
    aiohttp_mock.ClientResponseError = ClientResponseError
    aiohttp_mock.ClientTimeout = ClientTimeout
    aiohttp_mock.ClientSession = MagicMock
    sys.modules["aiohttp"] = aiohttp_mock


class MockBaseFlow:
    """Mock base class for Home Assistant ConfigFlow and OptionsFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def __init__(self, *args, **kwargs):
        self.hass = MagicMock()
        self.context = {}
        self.unique_id = None

    def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders,
        }

    async def async_set_unique_id(self, unique_id, raise_on_progress=True):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def async_create_entry(self, *, title, data, options=None):
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
            "options": options or {},
        }

    def async_update_reload_and_abort(self, entry, *, data=None, reason="reauth_successful"):
        return {
            "type": "abort",
            "reason": reason,
            "data": data,
        }


# If homeassistant is not installed in the test environment, provide lightweight mocks
# so modules that import HA symbols can be imported and tested.
MOCK_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.button",
    "homeassistant.components.diagnostics",
    "homeassistant.components.http",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.entity_registry",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.util.dt",
]

for mod_name in MOCK_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

for mod_name in MOCK_MODULES:
    if "." in mod_name:
        parent_name, _, child_name = mod_name.rpartition(".")
        if parent_name in sys.modules:
            setattr(sys.modules[parent_name], child_name, sys.modules[mod_name])

# Ensure homeassistant.exceptions has real Exception subclasses
if "homeassistant.exceptions" not in sys.modules or isinstance(sys.modules["homeassistant.exceptions"], MagicMock):
    exc_mock = MagicMock()
    exc_mock.HomeAssistantError = HomeAssistantError
    exc_mock.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    sys.modules["homeassistant.exceptions"] = exc_mock
    if "homeassistant" in sys.modules:
        sys.modules["homeassistant"].exceptions = exc_mock

if "homeassistant.helpers.update_coordinator" in sys.modules:
    sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = UpdateFailed

if "homeassistant.config_entries" in sys.modules:
    sys.modules["homeassistant.config_entries"].ConfigFlow = MockBaseFlow
    sys.modules["homeassistant.config_entries"].OptionsFlow = MockBaseFlow
    if "homeassistant" in sys.modules:
        sys.modules["homeassistant"].config_entries.ConfigFlow = MockBaseFlow
        sys.modules["homeassistant"].config_entries.OptionsFlow = MockBaseFlow

if "homeassistant.core" in sys.modules:
    sys.modules["homeassistant.core"].callback = lambda func: func
    if "homeassistant" in sys.modules:
        sys.modules["homeassistant"].core.callback = lambda func: func

if "homeassistant.helpers.config_validation" in sys.modules:
    sys.modules["homeassistant.helpers.config_validation"].multi_select = lambda options: (lambda val: val)

if "homeassistant.helpers.aiohttp_client" in sys.modules:
    sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = (
        lambda hass: getattr(hass, "client_session", MagicMock())
    )
