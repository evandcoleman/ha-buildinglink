"""BuildingLink API client."""

from __future__ import annotations

import uuid
from typing import Any

import aiohttp

from .auth import BuildingLinkAuth
from .const import (
    API_HOST,
    EVENTLOG_HOST,
    FRONT_DESK_HOST,
    LEGACY_HOST,
    MAINTENANCE_HOST,
    USER_AGENT,
    USERS_HOST,
)
from .exceptions import APIError
from .models import (
    Amenity,
    AmenityReservation,
    Announcement,
    CalendarEvent,
    Contact,
    FrontDeskInstruction,
    FrontDeskInstructionType,
    MaintenanceRequest,
    MaintenanceResponse,
    Package,
    PackageResponse,
    Property,
    UserProfile,
)


class BuildingLinkClient:
    """Async client for the BuildingLink API."""

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
        device_id: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            username: BuildingLink username (email). Preferred auth method.
            password: BuildingLink password.
            refresh_token: OAuth2 refresh token (legacy fallback).
            device_id: Device UUID. Generated if not provided.
            session: Optional aiohttp session. Created internally if not provided.
        """
        self._auth = BuildingLinkAuth(
            username=username,
            password=password,
            refresh_token=refresh_token,
        )
        self._device_id = device_id or str(uuid.uuid4())
        self._session = session
        self._owns_session = session is None
        self._property_id: str | None = None
        self._property_legacy_id: int | None = None
        self._user_id: str | None = None

    @property
    def auth(self) -> BuildingLinkAuth:
        """Return the auth manager."""
        return self._auth

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self._device_id

    @property
    def refresh_token(self) -> str:
        """Return the current refresh token."""
        return self._auth.refresh_token

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: Any = None,
    ) -> Any:
        """Make an authenticated API request."""
        session = await self._get_session()
        access_token = await self._auth.async_get_access_token(session)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "X-Correlation-Id": str(uuid.uuid4()),
        }

        if params is None:
            params = {}
        params["device-id"] = self._device_id

        async with session.request(
            method, url, headers=headers, params=params, json=json, data=data
        ) as resp:
            if resp.status == 401:
                # Token may have expired between check and use; retry once
                access_token = await self._auth.async_get_access_token(session)
                headers["Authorization"] = f"Bearer {access_token}"
                async with session.request(
                    method, url, headers=headers, params=params, json=json, data=data
                ) as retry_resp:
                    if retry_resp.status >= 400:
                        text = await retry_resp.text()
                        raise APIError(retry_resp.status, text)
                    return await retry_resp.json()
            if resp.status >= 400:
                text = await resp.text()
                raise APIError(resp.status, text)
            return await resp.json()

    async def async_get_properties(self) -> list[Property]:
        """Get authorized properties."""
        url = f"{API_HOST}/Properties/AuthenticatedUser/v1/property/authorized-properties"
        result = await self._request("GET", url, params={"TypeNodeFilter": "/5/"})
        properties: list[Property] = []
        if isinstance(result, dict):
            for prop_data in result.get("properties", [result]):
                try:
                    properties.append(Property.model_validate(prop_data))
                except Exception:
                    pass
        elif isinstance(result, list):
            for item in result:
                try:
                    properties.append(Property.model_validate(item))
                except Exception:
                    pass
        return properties

    async def async_set_property(
        self, property_id: str, legacy_id: int, user_id: str | None = None
    ) -> None:
        """Set the active property context for subsequent calls."""
        self._property_id = property_id
        self._property_legacy_id = legacy_id
        self._user_id = user_id

    async def async_get_packages(self) -> list[Package]:
        """Get open packages/deliveries."""
        url = f"{EVENTLOG_HOST}/event-log/integrations/resident-all"
        params = {
            "$expand": "Location,Type,Authorizations",
            "$filter": "IsOpen eq true and Type/IsShownOnTenantHomePage eq true",
        }
        result = await self._request("GET", url, params=params)
        response = PackageResponse.model_validate(result)
        return response.entities

    async def async_get_maintenance_requests(self) -> list[MaintenanceRequest]:
        """Get open maintenance requests."""
        url = f"{MAINTENANCE_HOST}/requests/get-all"
        params = {"extended": "true", "isBoardMemberSection": "false"}
        body = {
            "filterBy": {
                "onHoldUntil": True,
                "onHoldIndefinitely": True,
                "includeClosedRequests": False,
                "includeDeactivatedUnits": False,
            },
            "current": 1,
            "size": 10000,
        }
        result = await self._request("POST", url, params=params, json=body)
        response = MaintenanceResponse.model_validate(result)
        return response.items

    async def async_get_announcements(self) -> list[Announcement]:
        """Get active announcements."""
        url = f"{API_HOST}/ContentCreator/Resident/v1/announcements/active"
        result = await self._request("GET", url)
        if isinstance(result, list):
            return [Announcement.model_validate(a) for a in result]
        return []

    async def async_get_calendar_events(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[CalendarEvent]:
        """Get calendar events with optional date range."""
        url = f"{API_HOST}/Calendar/Resident/v2/resident/events/filteredeventsrsvp"
        params: dict[str, Any] = {}
        if from_date:
            params["fromDateTime"] = from_date
        if to_date:
            params["toDateTime"] = to_date
        result = await self._request("GET", url, params=params)
        if isinstance(result, list):
            return [CalendarEvent.model_validate(e) for e in result]
        return []

    async def async_get_amenities(self) -> list[Amenity]:
        """Get available amenities."""
        url = f"{API_HOST}/AmenityReservation/Resident/v1/GetAmenities()"
        result = await self._request("GET", url, params={"$skip": "0"})
        values = result.get("value", []) if isinstance(result, dict) else result
        return [Amenity.model_validate(a) for a in values]

    async def async_get_amenity_reservations(self) -> list[AmenityReservation]:
        """Get amenity reservations."""
        url = f"{API_HOST}/AmenityReservation/Resident/v1/GetReservations()"
        result = await self._request("GET", url)
        values = result.get("value", []) if isinstance(result, dict) else result
        return [AmenityReservation.model_validate(r) for r in values]

    async def async_get_contacts(self) -> list[Contact]:
        """Get building contacts. Requires property_id and user_id to be set."""
        if not self._property_id or not self._user_id:
            return []
        url = (
            f"{LEGACY_HOST}/services/MobileLinkResident1_7.svc/rest/"
            f"Buildings/{self._property_id}/V2/Contacts"
        )
        params = {"format": "json", "t": "1", "l": self._user_id}
        result = await self._request("GET", url, params=params)
        if isinstance(result, list):
            return [Contact.model_validate(c) for c in result]
        return []

    async def async_get_user_profile(self) -> UserProfile:
        """Get the authenticated user's profile."""
        url = f"{USERS_HOST}/users/authenticated"
        result = await self._request("GET", url)
        return UserProfile.model_validate(result)

    async def async_get_front_desk_instruction_types(
        self,
    ) -> list[FrontDeskInstructionType]:
        """Get front desk instruction types."""
        url = f"{FRONT_DESK_HOST}/instruction-type/sync"
        params = {"excludeReplacedExpired": "true"}
        result = await self._request("GET", url, params=params)
        if isinstance(result, list):
            return [FrontDeskInstructionType.model_validate(t) for t in result]
        return []

    async def async_get_front_desk_instructions(self) -> list[FrontDeskInstruction]:
        """Get active front desk instructions."""
        url = f"{FRONT_DESK_HOST}/instruction/sync"
        params = {"excludeReplacedExpired": "true"}
        result = await self._request("GET", url, params=params)
        if isinstance(result, list):
            return [FrontDeskInstruction.model_validate(i) for i in result]
        return []

    async def async_close(self) -> None:
        """Close the client session."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> BuildingLinkClient:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        await self.async_close()
