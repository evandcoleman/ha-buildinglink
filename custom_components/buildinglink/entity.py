"""Base entity for BuildingLink."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BuildingLinkCoordinator, BuildingLinkData


class BuildingLinkEntity(CoordinatorEntity[BuildingLinkCoordinator]):
    """Base entity for BuildingLink."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BuildingLinkCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.device_id)},
            name="BuildingLink",
            manufacturer="BuildingLink",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def data(self) -> BuildingLinkData:
        """Return coordinator data."""
        return self.coordinator.data
