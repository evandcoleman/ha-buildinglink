"""Data models for BuildingLink API responses."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """OAuth2 token response."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    id_token: str | None = None


class EventType(BaseModel):
    """Event type for packages/deliveries."""

    id: str
    abbreviated_description: str = Field(alias="abbreviatedDescription", default="")
    event_background_color: str = Field(alias="eventBackgroundColor", default="")
    event_font_color: str = Field(alias="eventFontColor", default="")
    icon_url: str | None = Field(alias="iconUrl", default=None)

    model_config = {"populate_by_name": True}


class Package(BaseModel):
    """A package/delivery entry from the event log."""

    id: str
    counter: int = 0
    open_comment: str | None = Field(alias="openComment", default=None)
    open_utc: datetime | None = Field(alias="openUtc", default=None)
    event_type: EventType | None = Field(alias="eventType", default=None)

    model_config = {"populate_by_name": True}

    @property
    def carrier(self) -> str:
        """Return the carrier name."""
        return self.event_type.abbreviated_description if self.event_type else "Unknown"

    @property
    def tracking_number(self) -> str | None:
        """Return the tracking number."""
        return self.open_comment


class PackageResponse(BaseModel):
    """Response from the event log packages endpoint."""

    last_record_version: str | None = Field(alias="lastRecordVersion", default=None)
    entities: list[Package] = []

    model_config = {"populate_by_name": True}


class MaintenanceRequest(BaseModel):
    """A maintenance request."""

    id: int = 0
    subject: str = ""
    description: str = ""
    status: str = ""
    created_date: str = Field(alias="createdDate", default="")
    category: str = ""

    model_config = {"populate_by_name": True}


class MaintenanceResponse(BaseModel):
    """Response from the maintenance requests endpoint."""

    items: list[MaintenanceRequest] = []
    total_count: int = Field(alias="totalCount", default=0)

    model_config = {"populate_by_name": True}


class Announcement(BaseModel):
    """An active announcement."""

    id: int = 0
    title: str = ""
    body: str = ""
    start_date: str = Field(alias="startDate", default="")
    end_date: str = Field(alias="endDate", default="")

    model_config = {"populate_by_name": True}


class CalendarEvent(BaseModel):
    """A calendar event."""

    id: int = 0
    title: str = ""
    description: str = ""
    start_date_time: str = Field(alias="startDateTime", default="")
    end_date_time: str = Field(alias="endDateTime", default="")
    location: str = ""

    model_config = {"populate_by_name": True}


class Amenity(BaseModel):
    """An amenity."""

    id: int = Field(alias="Id", default=0)
    name: str = Field(alias="Name", default="")

    model_config = {"populate_by_name": True}


class AmenityReservation(BaseModel):
    """An amenity reservation."""

    id: int = 0
    amenity_name: str = Field(alias="amenityName", default="")
    start_date: str = Field(alias="startDate", default="")
    end_date: str = Field(alias="endDate", default="")

    model_config = {"populate_by_name": True}


class Contact(BaseModel):
    """A building contact."""

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""


class Property(BaseModel):
    """An authorized property."""

    id: str = ""
    name: str = ""
    address: str = ""
    legacy_id: int = Field(alias="legacyId", default=0)

    model_config = {"populate_by_name": True}


class UserProfile(BaseModel):
    """Authenticated user profile."""

    id: str = ""
    first_name: str = Field(alias="firstName", default="")
    last_name: str = Field(alias="lastName", default="")
    email: str = ""
    phone: str = ""

    model_config = {"populate_by_name": True}


class FrontDeskInstructionType(BaseModel):
    """A front desk instruction type."""

    id: str = ""
    name: str = ""

    model_config = {"populate_by_name": True}


class FrontDeskInstruction(BaseModel):
    """A front desk instruction."""

    id: str = ""
    instruction_type_id: str = Field(alias="instructionTypeId", default="")
    notes: str = ""

    model_config = {"populate_by_name": True}
