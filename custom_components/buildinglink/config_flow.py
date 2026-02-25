"""Config flow for BuildingLink integration."""

from __future__ import annotations

import uuid
from typing import Any

import aiohttp
import voluptuous as vol

from pybuildinglink import BuildingLinkClient
from pybuildinglink.exceptions import AuthenticationError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DEVICE_ID, CONF_REFRESH_TOKEN, DOMAIN


class BuildingLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BuildingLink."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN]
            device_id = str(uuid.uuid4())

            try:
                async with aiohttp.ClientSession() as session:
                    client = BuildingLinkClient(
                        refresh_token=refresh_token,
                        device_id=device_id,
                        session=session,
                    )
                    # Validate by refreshing the token
                    await client.auth.async_refresh_token(session)
                    new_refresh_token = client.refresh_token

                    # Try to get user profile for a friendly title
                    try:
                        profile = await client.async_get_user_profile()
                        title = f"BuildingLink ({profile.first_name} {profile.last_name})"
                    except Exception:
                        title = "BuildingLink"

            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_REFRESH_TOKEN: new_refresh_token,
                        CONF_DEVICE_ID: device_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
        )
