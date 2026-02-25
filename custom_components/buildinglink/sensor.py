"""Sensor platform for BuildingLink."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import BuildingLinkCoordinator, BuildingLinkData
from .entity import BuildingLinkEntity


@dataclass(frozen=True, kw_only=True)
class BuildingLinkSensorDescription(SensorEntityDescription):
    """Describe a BuildingLink sensor."""

    value_fn: Callable[[BuildingLinkData], int]
    attrs_fn: Callable[[BuildingLinkData], dict[str, Any]]


SENSOR_DESCRIPTIONS: list[BuildingLinkSensorDescription] = [
    BuildingLinkSensorDescription(
        key="packages",
        translation_key="packages",
        native_unit_of_measurement="packages",
        value_fn=lambda data: len(data.packages),
        attrs_fn=lambda data: {
            "packages": [
                {
                    "carrier": pkg.carrier,
                    "tracking_number": pkg.tracking_number,
                    "received": pkg.open_utc.isoformat() if pkg.open_utc else None,
                }
                for pkg in data.packages
            ]
        },
    ),
    BuildingLinkSensorDescription(
        key="maintenance_requests",
        translation_key="maintenance_requests",
        native_unit_of_measurement="requests",
        value_fn=lambda data: len(data.maintenance_requests),
        attrs_fn=lambda data: {
            "requests": [
                {
                    "subject": req.subject,
                    "status": req.status,
                    "category": req.category,
                    "created": req.created_date,
                }
                for req in data.maintenance_requests
            ]
        },
    ),
    BuildingLinkSensorDescription(
        key="announcements",
        translation_key="announcements",
        native_unit_of_measurement="announcements",
        value_fn=lambda data: len(data.announcements),
        attrs_fn=lambda data: {
            "announcements": [
                {
                    "title": ann.title,
                    "body": ann.body,
                    "start_date": ann.start_date,
                    "end_date": ann.end_date,
                }
                for ann in data.announcements
            ]
        },
    ),
    BuildingLinkSensorDescription(
        key="calendar_events",
        translation_key="calendar_events",
        native_unit_of_measurement="events",
        value_fn=lambda data: len(data.calendar_events),
        attrs_fn=lambda data: {
            "events": [
                {
                    "title": evt.title,
                    "start": evt.start_date_time,
                    "end": evt.end_date_time,
                    "location": evt.location,
                }
                for evt in data.calendar_events
            ]
        },
    ),
    BuildingLinkSensorDescription(
        key="amenity_reservations",
        translation_key="amenity_reservations",
        native_unit_of_measurement="reservations",
        value_fn=lambda data: len(data.amenity_reservations),
        attrs_fn=lambda data: {
            "reservations": [
                {
                    "amenity": res.amenity_name,
                    "start": res.start_date,
                    "end": res.end_date,
                }
                for res in data.amenity_reservations
            ]
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BuildingLink sensors."""
    coordinator: BuildingLinkCoordinator = entry.runtime_data
    async_add_entities(
        BuildingLinkSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BuildingLinkSensor(BuildingLinkEntity, SensorEntity):
    """A BuildingLink sensor."""

    entity_description: BuildingLinkSensorDescription

    def __init__(
        self,
        coordinator: BuildingLinkCoordinator,
        description: BuildingLinkSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return self.entity_description.attrs_fn(self.data)
