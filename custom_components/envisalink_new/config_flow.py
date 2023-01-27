"""Config flow for Envisalink_new integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult, AbortFlow
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
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITIONS,
    CONF_PARTITION_SET,
    CONF_PASS,
    CONF_USERNAME,
    CONF_YAML_OPTIONS,
    CONF_ZONEDUMP_INTERVAL,
    CONF_ZONES,
    CONF_ZONE_SET,
    DEFAULT_ALARM_NAME,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_EVL_VERSION,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DEFAULT_KEEPALIVE,
    DEFAULT_PANIC,
    DEFAULT_PARTITION_SET,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    DEFAULT_ZONETYPE,
    DEFAULT_ZONE_SET,
    DOMAIN,
    HONEYWELL_ARM_MODE_INSTANT_LABEL,
    HONEYWELL_ARM_MODE_INSTANT_VALUE,
    HONEYWELL_ARM_MODE_NIGHT_LABEL,
    HONEYWELL_ARM_MODE_NIGHT_VALUE,
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
            title = await self.validate_input(self.hass, user_input)
        except HomeAssistantError as err:
            errors["base"] = err.reason
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception: %r", ex)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=title, data=user_input)

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

    async def validate_input(self, hass: HomeAssistant, data: dict[str, Any]) -> str:
        """Validate the user input allows us to connect."""

        panel = await check_connection(hass, data)

        unique_id = panel.mac_address
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        data[CONF_PANEL_TYPE] = panel.panel_type
        data[CONF_EVL_VERSION] = panel.envisalink_version
        title = data[CONF_ALARM_NAME]
        data.pop(CONF_ALARM_NAME)
        return title

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        config_defaults = {
            CONF_HOST: self.config_entry.data[CONF_HOST],
            CONF_PASS: self.config_entry.data[CONF_PASS],
            CONF_USERNAME: self.config_entry.data[CONF_USERNAME],
        }
        zone_set = self.config_entry.options.get(CONF_ZONE_SET, DEFAULT_ZONE_SET)
        partition_set = self.config_entry.options.get(CONF_PARTITION_SET, DEFAULT_PARTITION_SET)

        if user_input is not None:
            evl_version = self.config_entry.options.get(CONF_EVL_VERSION, DEFAULT_EVL_VERSION)
            max_zones = EnvisalinkAlarmPanel.get_max_zones_by_version(evl_version)

            zone_set = user_input.get(CONF_ZONE_SET)
            partition_set = user_input.get(CONF_PARTITION_SET)
            if not parse_range_string(zone_set, 1, max_zones):
                errors["base"] = "invalid_zone_spec"
            elif not parse_range_string(partition_set, 1, EnvisalinkAlarmPanel.get_max_partitions()):
                errors["base"] = "invalid_partition_spec"
            else:
                # Pull the host, user and password out of the options and store them in
                # the main config entry
                data = dict(self.config_entry.data)
                for key in [ CONF_HOST, CONF_USERNAME, CONF_PASS ]:
                    value = user_input[key]
                    data[key] = value
                    config_defaults[key]  = value
                    user_input.pop(key)
                
                # Validate that the new connection settings are valid
                try:
                    panel = await check_connection(self.hass, data)
                except HomeAssistantError as err:
                    errors["base"] = err.reason
                except Exception as ex:  # pylint: disable=broad-except
                    LOGGER.exception("Unexpected exception: %r", ex)
                    errors["base"] = "unknown"
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=data)

                    return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_HOST,
                default=config_defaults[CONF_HOST],
            ): cv.string,
            vol.Required(
                CONF_USERNAME,
                default=config_defaults[CONF_USERNAME],
            ): cv.string,
            vol.Required(
                CONF_PASS,
                default=config_defaults[CONF_PASS],
            ): cv.string,
            vol.Optional(
                CONF_ZONE_SET,
                default=zone_set
            ): cv.string,
            vol.Optional(
                CONF_PARTITION_SET,
                default=partition_set
            ): cv.string,
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

        # Add DSC-only options
        if self.config_entry.data.get(CONF_PANEL_TYPE) == PANEL_TYPE_DSC:
            # Zone bypass switches are only available on DSC panels
            options_schema[
                vol.Optional(
                    CONF_CREATE_ZONE_BYPASS_SWITCHES,
                    default=self.config_entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES)
                )] = selector.BooleanSelector()

        # Add Honeywell-only options
        if self.config_entry.data.get(CONF_PANEL_TYPE) == PANEL_TYPE_HONEYWELL:
            # Allow selection of which keypress to use for Arm Night mode
            ARM_MODES = [
                selector.SelectOptionDict(value=HONEYWELL_ARM_MODE_NIGHT_VALUE, label=HONEYWELL_ARM_MODE_NIGHT_LABEL),
                selector.SelectOptionDict(value=HONEYWELL_ARM_MODE_INSTANT_VALUE, label=HONEYWELL_ARM_MODE_INSTANT_LABEL),
            ]
            options_schema[
                vol.Optional(
                    CONF_HONEYWELL_ARM_NIGHT_MODE,
                    default=self.config_entry.options.get(CONF_HONEYWELL_ARM_NIGHT_MODE, DEFAULT_HONEYWELL_ARM_NIGHT_MODE)
                )] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ARM_MODES)
                )


        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options_schema),
            errors=errors,
        )

class DiscoveryError(HomeAssistantError):
    """Error to indicate we cannot connect."""
    def __init__(self, result):
        if result == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
            self.reason = "cannot_connect"
        elif result == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
            self.reason = "invalid_auth"
        else:
            LOGGER.error("Unexpected error: %s", result)
            self.reason = "unknown"

def find_yaml_zone_info(zone_num: int, zone_info: map) -> map:
    if zone_info is None:
        return None

    for key, entry in zone_info.items():
        if int(key) == zone_num:
            return entry
    return None

def find_yaml_partition_info(part_num: int, part_info: map) -> map:
    if part_info is None:
        return None

    for key, entry in part_info.items():
        if int(key) == part_num:
            return entry
    return None


def parse_range_string(sequence: str, min_val: int, max_val: int) -> set:
    # Empty strings are not valid
    if sequence is None or len(sequence) == 0:
        return None

    # Make sure there are only valid characters
    valid_chars = '1234567890,- '
    v = sequence.strip(valid_chars)
    if len(v) != 0:
        return None

    # Strip whitespace
    sequence = sequence.strip(' ')

    r = []
    for seg in sequence.split(","):
        nums = seg.split("-")
        for v in nums:
            if len(v) == 0:
                return None
            v = int(v)
            if v < min_val or v > max_val:
                return None
        if len(nums) == 1:
            r.append(int(nums[0]))
        elif len(nums) == 2:
            for i in range(int(nums[0]), int(nums[1]) + 1):
                r.append(i)
        else:
            return None

    if len(r) == 0:
        return None

    return sorted(set(r))

def generate_range_string(seq: set) -> str:
    if len(seq) == 0:
        return None
    l = list(seq)
    if len(seq) == 1:
        return str(l[0])

    result = ""
    l.sort()
    end = start = l[0]
    for i in l[1:]:
        if i == (end + 1):
            end = i
        else:
            if start == end:
                result += f"{start},"
            else:
                result += f"{start}-{end},"
            start = end = i

    if start == end:
        result += f"{start}"
    else:
        result += f"{start}-{end}"
    start = end = i
    return result

async def check_connection(hass: HomeAssistant, data: dict[str, Any]) -> EnvisalinkAlarmPanel:
    """Check that we're able to successfully connect and auth with the envisalink"""

    panel = EnvisalinkAlarmPanel(
        data[CONF_HOST],
        userName=data[CONF_USERNAME],
        password=data[CONF_PASS])

    result = await panel.discover()
    if result != EnvisalinkAlarmPanel.ConnectionResult.SUCCESS:
        raise DiscoveryError(result)

    return panel

