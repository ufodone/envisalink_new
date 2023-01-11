"""Config flow for Envisalink_new integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_TIMEOUT,
)

from .const import (
    CONF_ALARM_NAME,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_NUM_PARTITIONS,
    CONF_NUM_ZONES,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITIONS,
    CONF_PASS,
    CONF_USERNAME,
    CONF_YAML_OPTIONS,
    CONF_ZONEDUMP_INTERVAL,
    CONF_ZONES,
    DEFAULT_ALARM_NAME,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_EVL_VERSION,
    DEFAULT_KEEPALIVE,
    DEFAULT_NUM_PARTITIONS,
    DEFAULT_NUM_ZONES,
    DEFAULT_PANIC,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    DEFAULT_ZONETYPE,
    DOMAIN,
    EVL_MAX_PARTITIONS,
    EVL_MAX_ZONES,
    LOGGER,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
)

from .pyenvisalink import EnvisalinkAlarmPanel

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALARM_NAME, default=DEFAULT_ALARM_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASS): cv.string,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    panel = EnvisalinkAlarmPanel(
        data[CONF_HOST],
        userName=data[CONF_USERNAME],
        password=data[CONF_PASS])

    result = await panel.validate_device_connection()
    if result == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
        raise CannotConnect()
    if result == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
        raise InvalidAuth()

    data[CONF_PANEL_TYPE] = panel.panel_type
    data[CONF_EVL_VERSION] = panel.envisalink_version
    return {"title": data[CONF_ALARM_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envisalink_new."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception: %r", ex)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_NUM_ZONES,
                default=self.config_entry.options.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.SLIDER,
                        min=1,
                        max=EVL_MAX_ZONES,
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_NUM_PARTITIONS,
                default=self.config_entry.options.get(CONF_NUM_PARTITIONS, DEFAULT_NUM_PARTITIONS)
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.SLIDER,
                        min=1,
                        max=EVL_MAX_PARTITIONS,
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Optional(
                CONF_CODE,
                description={"suggested_value": self.config_entry.options.get(CONF_CODE)}
            ): cv.string,
            vol.Optional(
                CONF_PANIC,
                default=self.config_entry.options.get(CONF_PANIC, DEFAULT_PANIC)
            ): cv.string,
            vol.Optional(
                CONF_EVL_KEEPALIVE,
                default=self.config_entry.options.get(CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE)
            ): vol.All(
                vol.Coerce(int), vol.Range(min=15)
            ),
            vol.Optional(
                CONF_ZONEDUMP_INTERVAL,
                default=self.config_entry.options.get(CONF_ZONEDUMP_INTERVAL, DEFAULT_ZONEDUMP_INTERVAL)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_TIMEOUT,
                default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): vol.Coerce(int)
        }

        if self.config_entry.data.get(CONF_PANEL_TYPE) == PANEL_TYPE_DSC:
            # Zone bypass switches are only available on DSC panels
            options_schema[
                vol.Optional(
                    CONF_CREATE_ZONE_BYPASS_SWITCHES,
                    default=self.config_entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES)
                )] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options_schema),
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
