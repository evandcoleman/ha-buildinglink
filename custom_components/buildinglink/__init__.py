"""BuildingLink integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID, CONF_REFRESH_TOKEN, DOMAIN, PLATFORMS
from .coordinator import BuildingLinkCoordinator


type BuildingLinkConfigEntry = ConfigEntry[BuildingLinkCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BuildingLinkConfigEntry
) -> bool:
    """Set up BuildingLink from a config entry."""
    coordinator = BuildingLinkCoordinator(
        hass,
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        device_id=entry.data.get(CONF_DEVICE_ID),
    )

    await coordinator.async_config_entry_first_refresh()

    # Store updated refresh token back to config entry
    if coordinator.client.refresh_token != entry.data[CONF_REFRESH_TOKEN]:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_REFRESH_TOKEN: coordinator.client.refresh_token,
            },
        )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BuildingLinkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
