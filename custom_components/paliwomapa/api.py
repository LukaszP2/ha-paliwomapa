"""Small, defensive client for the PaliwoMapa web application's observed endpoints.

Only endpoints observed in the supplied HAR are implemented. This client intentionally
contains no guessed geographic-search endpoint.
"""
from __future__ import annotations

import logging
from typing import Any

from .geo import build_overpass_query, parse_overpass_stations

from aiohttp import ClientError, ClientResponseError, ClientSession
from homeassistant.exceptions import HomeAssistantError

from .const import OVERPASS_URLS, REQUEST_TIMEOUT, SUPABASE_API_KEY, SUPABASE_URL
from .models import extract_favorite_station_ids, normalize_station_response, normalize_station_row, validate_station_id

_LOGGER = logging.getLogger(__name__)


class PaliwoMapaApiError(HomeAssistantError):
    """Raised when the upstream service cannot provide valid data."""


class PaliwoMapaAuthError(PaliwoMapaApiError):
    """Raised when credentials are rejected or the session expires."""


class PaliwoMapaApi:
    """Async client for station prices and optional account data."""

    def __init__(self, session: ClientSession, email: str | None = None, password: str | None = None) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._user_id: str | None = None

    @staticmethod
    def validate_station_id(station_id: str) -> str:
        try:
            return validate_station_id(station_id)
        except ValueError as err:
            raise PaliwoMapaApiError(str(err)) from err

    @staticmethod
    def parse_station_response(payload: Any, requested_id: str) -> dict[str, Any]:
        try:
            return normalize_station_response(payload, requested_id)
        except ValueError as err:
            raise PaliwoMapaApiError(str(err)) from err

    async def _request_json(self, method: str, path: str, *, params: dict[str, str] | None = None,
                            json_body: dict[str, Any] | None = None, auth: bool = False) -> Any:
        headers = {"apikey": SUPABASE_API_KEY, "Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            await self.async_login()
            if self._access_token:
                headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            async with self._session.request(
                method, f"{SUPABASE_URL}{path}", params=params, json=json_body,
                headers=headers, timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    if path.startswith("/auth/"):
                        raise PaliwoMapaAuthError("Logowanie do PaliwoMapa nie powiodło się. Sprawdź dane konta.")
                    raise PaliwoMapaAuthError("PaliwoMapa odrzuciła dostęp. Sprawdź konto lub uprawnienia.")
                response.raise_for_status()
                try:
                    return await response.json(content_type=None)
                except (ValueError, TypeError) as err:
                    raise PaliwoMapaApiError("PaliwoMapa zwróciła nieprawidłowy JSON.") from err
        except PaliwoMapaApiError:
            raise
        except ClientResponseError as err:
            _LOGGER.debug("PaliwoMapa HTTP error: status=%s path=%s", err.status, path)
            raise PaliwoMapaApiError(f"Błąd HTTP {err.status} podczas pobierania danych PaliwoMapa.") from err
        except (ClientError, TimeoutError) as err:
            raise PaliwoMapaApiError("Nie można połączyć się z PaliwoMapa.") from err

    async def async_login(self) -> str:
        """Authenticate only when account mode was configured."""
        if self._access_token and self._user_id:
            return self._user_id
        if not self._email or not self._password:
            raise PaliwoMapaAuthError("Nie skonfigurowano danych konta PaliwoMapa.")
        payload = await self._request_json(
            "POST", "/auth/v1/token", params={"grant_type": "password"},
            json_body={"email": self._email, "password": self._password}, auth=False,
        )
        if not isinstance(payload, dict) or not payload.get("access_token") or not isinstance(payload.get("user"), dict):
            raise PaliwoMapaAuthError("Odpowiedź logowania nie zawiera wymaganych danych.")
        user_id = payload["user"].get("id")
        if not isinstance(user_id, str) or not user_id:
            raise PaliwoMapaAuthError("Odpowiedź logowania nie zawiera identyfikatora użytkownika.")
        self._access_token = payload["access_token"]
        self._user_id = user_id
        return user_id

    async def async_get_station(self, station_id: str) -> dict[str, Any]:
        station_id = self.validate_station_id(station_id)
        payload = await self._request_json(
            "GET", "/rest/v1/app_docs",
            params={"select": "path,doc_id,data", "path": f"eq.prices/{station_id}"},
            auth=bool(self._email and self._password),
        )
        return self.parse_station_response(payload, station_id)


    async def async_get_stations(self, station_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch many stations through the observed batch RPC in one request."""
        ids = list(dict.fromkeys(self.validate_station_id(item) for item in station_ids))
        if not ids:
            return {}
        payload = await self._request_json(
            "POST", "/rest/v1/rpc/get_prices_by_ids",
            json_body={"ids": ids}, auth=bool(self._email and self._password),
        )
        if not isinstance(payload, list):
            raise PaliwoMapaApiError("API zbiorcze zwróciło nieprawidłową odpowiedź.")
        result: dict[str, dict[str, Any]] = {}
        for row in payload:
            try:
                station = normalize_station_row(row)
            except ValueError as err:
                _LOGGER.debug("Skipping malformed station row in batch response: %s", err)
                continue
            if station["station_id"] in ids:
                result[station["station_id"]] = station
        missing = sorted(set(ids) - set(result))
        if missing:
            _LOGGER.debug("PaliwoMapa batch response omitted station IDs: %s", missing)
        if not result:
            raise PaliwoMapaApiError("API nie zwróciło danych żadnej z wybranych stacji.")
        return result

    async def async_search_nearby_stations(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[dict[str, Any]]:
        """Find local fuel POIs via OpenStreetMap, then attach PaliwoMapa prices.

        This is an explicit user-triggered search, not background polling. OSM
        element IDs are used as station IDs because the map's observed data
        uses the same ID namespace. Results without PaliwoMapa price records
        are omitted.
        """
        try:
            query = build_overpass_query(latitude, longitude, radius_km)
        except ValueError as err:
            raise PaliwoMapaApiError(str(err)) from err
        overpass_payload = None
        failures: list[str] = []
        # Public Overpass instances can rate-limit or temporarily fail. Try
        # several mirrors before reporting a user-facing error.
        for endpoint in OVERPASS_URLS:
            try:
                async with self._session.post(
                    endpoint,
                    data={"data": query},
                    headers={"Accept": "application/json", "User-Agent": "HomeAssistant-PaliwoMapa/0.3.3"},
                    timeout=35,
                ) as response:
                    if response.status >= 400:
                        body = (await response.text())[:240].replace("\n", " ")
                        failures.append(f"{endpoint}: HTTP {response.status} {body}")
                        continue
                    candidate_payload = await response.json(content_type=None)
                    if not isinstance(candidate_payload, dict) or not isinstance(candidate_payload.get("elements"), list):
                        failures.append(f"{endpoint}: invalid JSON structure")
                        continue
                    overpass_payload = candidate_payload
                    break
            except (ClientError, TimeoutError, ValueError) as err:
                failures.append(f"{endpoint}: {type(err).__name__}: {err}")

        if overpass_payload is None:
            # Keep useful diagnostics without logging credentials (none are sent
            # to Overpass). URLs are fixed public endpoints.
            _LOGGER.warning("Nearby station discovery failed on all Overpass endpoints: %s", " | ".join(failures))
            raise PaliwoMapaApiError(
                "Nie udało się wyszukać stacji w OpenStreetMap (niedostępne serwery wyszukiwania). "
                "Spróbuj ponownie później."
            )

        try:
            candidates = parse_overpass_stations(overpass_payload, latitude, longitude, float(radius_km))
        except ValueError as err:
            raise PaliwoMapaApiError(str(err)) from err
        if not candidates:
            _LOGGER.info("Nearby search returned no OSM fuel stations within %.1f km", radius_km)
            return []

        _LOGGER.debug("Nearby search found %d OSM fuel candidates within %.1f km", len(candidates), radius_km)

        # Keep requests small and avoid a single very large RPC payload.
        # The PaliwoMapa RPC was observed accepting batches of 80 IDs.
        candidates = candidates[:240]
        by_id: dict[str, dict[str, Any]] = {}
        for start in range(0, len(candidates), 80):
            chunk = candidates[start:start + 80]
            try:
                prices = await self.async_get_stations([row["station_id"] for row in chunk])
            except PaliwoMapaApiError as err:
                _LOGGER.debug("No price records for nearby-station batch: %s", err)
                continue
            for station in chunk:
                station_id = station["station_id"]
                price_data = prices.get(station_id)
                if price_data:
                    by_id[station_id] = {
                        **price_data,
                        "latitude": station["latitude"],
                        "longitude": station["longitude"],
                        "distance_km": station["distance_km"],
                        "osm_name": station.get("osm_name"),
                        "osm_address": station.get("osm_address"),
                    }
        if not by_id:
            _LOGGER.warning(
                "Nearby search found %d OSM fuel stations within %.1f km, but PaliwoMapa returned no matching price records",
                len(candidates), radius_km,
            )
        else:
            _LOGGER.info("Nearby search matched %d/%d stations to PaliwoMapa prices", len(by_id), len(candidates))
        return sorted(by_id.values(), key=lambda item: item["distance_km"])

    @property
    def account_enabled(self) -> bool:
        return bool(self._email and self._password)

    async def async_get_account_profile(self) -> dict[str, Any]:
        """Return a limited profile summary, never the auth token."""
        user_id = await self.async_login()
        payload = await self._request_json(
            "GET", "/rest/v1/profiles", params={"id": f"eq.{user_id}"}, auth=True,
        )
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            return {}
        profile = payload[0]
        # Only a conservative allow-list of useful, non-secret fields.
        return {key: profile[key] for key in ("nick", "nickname", "points", "streak", "badges") if key in profile}

    async def async_get_favorite_station_ids(self) -> list[str]:
        """Read saved station IDs from the exact favorites document used by the app."""
        user_id = await self.async_login()
        payload = await self._request_json(
            "GET", "/rest/v1/app_docs",
            params={"select": "path,doc_id,data", "path": f"eq.favorites/{user_id}"},
            auth=True,
        )
        station_ids = extract_favorite_station_ids(payload)
        if station_ids:
            _LOGGER.debug("Imported %d favorite station IDs from PaliwoMapa account", len(station_ids))
        else:
            _LOGGER.warning(
                "PaliwoMapa favorites document was returned but contained no recognized station IDs; "
                "check the response shape (payload content is intentionally not logged)"
            )
        return station_ids
