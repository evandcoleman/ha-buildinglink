"""DataUpdateCoordinator for BuildingLink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from .pybuildinglink import (
    AmenityReservation,
    Announcement,
    BuildingLinkClient,
    CalendarEvent,
    MaintenanceRequest,
    Package,
)
from .pybuildinglink.exceptions import BuildingLinkError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class BuildingLinkData:
    """Data from BuildingLink API."""

    packages: list[Package] = field(default_factory=list)
    maintenance_requests: list[MaintenanceRequest] = field(default_factory=list)
    announcements: list[Announcement] = field(default_factory=list)
    calendar_events: list[CalendarEvent] = field(default_factory=list)
    amenity_reservations: list[AmenityReservation] = field(default_factory=list)


class BuildingLinkCoordinator(DataUpdateCoordinator[BuildingLinkData]):
    """Coordinator to manage fetching BuildingLink data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = BuildingLinkClient(
            username=username,
            password=password,
            refresh_token=refresh_token,
            device_id=device_id,
        )

    async def _async_update_data(self) -> BuildingLinkData:
        """Fetch data from BuildingLink."""
        try:
            packages = await self.client.async_get_packages()
            maintenance = await self.client.async_get_maintenance_requests()
            announcements = await self.client.async_get_announcements()
            events = await self.client.async_get_calendar_events()
            reservations = await self.client.async_get_amenity_reservations()
        except BuildingLinkError as err:
            raise UpdateFailed(f"Error fetching BuildingLink data: {err}") from err

        return BuildingLinkData(
            packages=packages,
            maintenance_requests=maintenance,
            announcements=announcements,
            calendar_events=events,
            amenity_reservations=reservations,
        )
