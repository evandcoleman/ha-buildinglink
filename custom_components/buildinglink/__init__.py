"""BuildingLink integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_USERNAME, DOMAIN, PLATFORMS
from .coordinator import BuildingLinkCoordinator


type BuildingLinkConfigEntry = ConfigEntry[BuildingLinkCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BuildingLinkConfigEntry
) -> bool:
    """Set up BuildingLink from a config entry."""
    # Support both new (username/password) and legacy (refresh_token) configs
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

    coordinator = BuildingLinkCoordinator(
        hass,
        username=username,
        password=password,
        refresh_token=refresh_token,
        device_id=entry.data.get(CONF_DEVICE_ID),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BuildingLinkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
