"""Config flow for Envisalink integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_TIMEOUT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_ALARM_NAME,
    CONF_CODE_ARM_REQUIRED,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_DISCOVERY_PORT,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITION_ASSIGNMENTS,
    CONF_PARTITION_SET,
    CONF_PASS,
    CONF_SHOW_KEYPAD,
    CONF_USERNAME,
    CONF_WIRELESS_ZONE_SET,
    CONF_ZONE_SET,
    DEFAULT_ALARM_NAME,
    DEFAULT_CODE_ARM_REQUIRED,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_EVL_VERSION,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DEFAULT_KEEPALIVE,
    DEFAULT_PANIC,
    DEFAULT_PARTITION_SET,
    DEFAULT_PORT,
    DEFAULT_SHOW_KEYPAD,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    DOMAIN,
    HONEYWELL_ARM_MODE_INSTANT_VALUE,
    HONEYWELL_ARM_MODE_NIGHT_VALUE,
    LOGGER,
    SHOW_KEYPAD_ALWAYS_VALUE,
    SHOW_KEYPAD_DISARM_VALUE,
    SHOW_KEYPAD_NEVER_VALUE,
)
from .helpers import extract_discovery_endpoint, parse_range_string
from .pyenvisalink.alarm_panel import EnvisalinkAlarmPanel
from .pyenvisalink.const import PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envisalink."""

    VERSION = 1
    MINOR_VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        config_defaults = _get_user_data_defaults()

        if user_input is not None:
            try:
                panel = await _validate_input(self.hass, user_input, is_creation=True)

                unique_id = format_mac(panel.mac_address)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = user_input[CONF_ALARM_NAME]
                user_input.pop(CONF_ALARM_NAME)
            except HomeAssistantError as err:
                errors["base"] = str(err)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception: %r", ex)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=title, data=user_input)

            # Validation errors so update the form defaults with what the user
            # has entered.
            config_keys = config_defaults.keys()
            for key in config_keys:
                if key in user_input:
                    config_defaults[key] = user_input[key]

        user_data_schema = _get_user_data_schema(config_defaults, is_creation=True)

        return self.async_show_form(
            step_id="user", data_schema=user_data_schema, errors=errors
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
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Envisalink options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""

        return self.async_show_menu(
            step_id="init",
            menu_options=["basic", "advanced", "partition_assignments"],
        )

    async def async_step_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        config_defaults = _get_user_data_defaults(self.config_entry.data)

        if user_input is not None:
            # This flow is for the main config items so update the config_entry with the
            # values that have been set
            data = dict(self.config_entry.data)
            for key, value in user_input.items():
                data[key] = value
                config_defaults[key] = value

            try:
                # Validate that the new settings are okay
                await _validate_input(self.hass, data)
            except HomeAssistantError as err:
                errors["base"] = str(err)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception: %r", ex)
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)

                return self.async_create_entry(title="", data=self.config_entry.options)

        user_data_schema = _get_user_data_schema(config_defaults)

        return self.async_show_form(
            step_id="basic",
            data_schema=user_data_schema,
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        default_wireless_zones = self.config_entry.options.get(CONF_WIRELESS_ZONE_SET)

        if user_input is not None:
            # Make sure all the options are here
            try:
                if CONF_PARTITION_ASSIGNMENTS in self.config_entry.options:
                    user_input[CONF_PARTITION_ASSIGNMENTS] = self.config_entry.options.get(
                        CONF_PARTITION_ASSIGNMENTS
                    )
                # Validate that the new settings are okay
                self._validate_advanced_options(user_input)
                return self.async_create_entry(title="", data=user_input)
            except HomeAssistantError as err:
                errors["base"] = str(err)
            default_wireless_zones = user_input.get(CONF_WIRELESS_ZONE_SET)

        options_schema = {
            vol.Optional(
                CONF_PANIC,
                default=self.config_entry.options.get(CONF_PANIC, DEFAULT_PANIC),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["Fire", "Ambulance", "Police"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="panic_type",
                ),
            ),
            vol.Optional(
                CONF_EVL_KEEPALIVE,
                default=self.config_entry.options.get(
                    CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                CONF_TIMEOUT,
                default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): vol.Coerce(int),
        }

        # Zone bypass switches are available only for DSC and Uno systems
        if self.config_entry.data.get(CONF_PANEL_TYPE) in [PANEL_TYPE_DSC, PANEL_TYPE_UNO]:
            # Zone bypass switches are only available on DSC panels
            options_schema[
                vol.Optional(
                    CONF_CREATE_ZONE_BYPASS_SWITCHES,
                    default=self.config_entry.options.get(
                        CONF_CREATE_ZONE_BYPASS_SWITCHES,
                        DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
                    ),
                )
            ] = selector.BooleanSelector()

        # Add DSC-only options
        if self.config_entry.data.get(CONF_PANEL_TYPE) == PANEL_TYPE_DSC:
            options_schema[
                vol.Optional(
                    CONF_CODE_ARM_REQUIRED,
                    default=self.config_entry.options.get(
                        CONF_CODE_ARM_REQUIRED,
                        DEFAULT_CODE_ARM_REQUIRED[PANEL_TYPE_DSC],
                    ),
                )
            ] = selector.BooleanSelector()
            options_schema[
                vol.Optional(
                    CONF_WIRELESS_ZONE_SET,
                    description={"suggested_value": default_wireless_zones},
                    default="",
                )
            ] = cv.string

        # Add Honeywell-only options
        if self.config_entry.data.get(CONF_PANEL_TYPE) == PANEL_TYPE_HONEYWELL:
            # Allow selection of which keypress to use for Arm Night mode
            options_schema[
                vol.Optional(
                    CONF_HONEYWELL_ARM_NIGHT_MODE,
                    default=self.config_entry.options.get(
                        CONF_HONEYWELL_ARM_NIGHT_MODE, DEFAULT_HONEYWELL_ARM_NIGHT_MODE
                    ),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        HONEYWELL_ARM_MODE_NIGHT_VALUE,
                        HONEYWELL_ARM_MODE_INSTANT_VALUE,
                    ],
                    translation_key=CONF_HONEYWELL_ARM_NIGHT_MODE,
                )
            )

        # Selection options for when the keypad should be displayed
        options_schema[
            vol.Optional(
                CONF_SHOW_KEYPAD,
                default=self.config_entry.options.get(
                    CONF_SHOW_KEYPAD, DEFAULT_SHOW_KEYPAD
                ),
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    SHOW_KEYPAD_NEVER_VALUE,
                    SHOW_KEYPAD_DISARM_VALUE,
                    SHOW_KEYPAD_ALWAYS_VALUE,
                ],
                translation_key=CONF_SHOW_KEYPAD,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        return self.async_show_form(
            step_id="advanced",
            data_schema=vol.Schema(options_schema),
            errors=errors,
        )

    async def async_step_partition_assignments(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the partition assignments."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Make sure all the options are here
            try:
                new_options = dict(self.config_entry.options)
                new_options[CONF_PARTITION_ASSIGNMENTS] = user_input
                # Validate that the new settings are okay
                self._validate_advanced_options(new_options)
                return self.async_create_entry(title="", data=new_options)
            except HomeAssistantError as err:
                errors["base"] = str(err)

        # Create schema for partition assignments
        partition_assignments = self.config_entry.options.get(
            CONF_PARTITION_ASSIGNMENTS, {}
        )
        partition_spec: str = self.config_entry.data.get(CONF_PARTITION_SET, "")
        partition_set = parse_range_string(
            partition_spec, 1, EnvisalinkAlarmPanel.get_max_partitions()
        )
        if not partition_set:
            raise PanelError("invalid_partition_spec")

        partition_mapping_schema = {}
        for partition in partition_set:
            partition_mapping_schema[
                vol.Optional(
                    f"{partition}",
                    description={
                        "suggested_value": partition_assignments.get(str(partition), "")
                    },
                    default="",
                )
            ] = cv.string

        return self.async_show_form(
            step_id="partition_assignments",
            data_schema=vol.Schema(partition_mapping_schema),
            errors=errors,
        )

    def _validate_advanced_options(self, user_input):
        """Ensure that the wireless zones specified are present in the main zone list."""
        max_zones = EnvisalinkAlarmPanel.get_max_zones_by_version(
            self.config_entry.options.get(CONF_EVL_VERSION, DEFAULT_EVL_VERSION)
        )

        zone_set: str = self.config_entry.data.get(CONF_ZONE_SET, "")
        zones = parse_range_string(zone_set, 1, max_zones)

        wireless_zone_set: str = user_input.get(CONF_WIRELESS_ZONE_SET, "")
        if wireless_zone_set:
            wireless_zones = parse_range_string(wireless_zone_set, 1, max_zones)
            if not wireless_zones:
                raise PanelError("invalid_zone_spec")

            for zone in wireless_zones:
                if zone not in zones:
                    raise PanelError("bad_wireless_zone")

        zones_mapped = set()
        partition_assignments: str = user_input.get(CONF_PARTITION_ASSIGNMENTS, "")
        if partition_assignments:
            for partition, zone_set in partition_assignments.items():
                if zone_set:
                    zone_list = parse_range_string(zone_set, 1, max_zones)
                    if not zone_list:
                        raise PanelError("invalid_zone_spec")
                    for z in zone_list:
                        if z not in zones:
                            raise PanelError("unknown_zones")
                        if z in zones_mapped:
                            raise PanelError("zone_already_in_partition")
                        zones_mapped.add(z)


class DiscoveryError(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, result):
        """Initialize the exception with the provided reason."""
        msg = "unknown"
        if result == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
            msg = "cannot_connect"
        elif result == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
            msg = "invalid_auth"
        else:
            LOGGER.error("Unexpected error: %s", result)
        super().__init__(msg)


class PanelError(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, reason):
        """Initialize the exception with the provided reason."""
        super().__init__(reason)


async def _validate_input(
    hass: HomeAssistant, data: dict[str, Any], is_creation: bool = False
) -> EnvisalinkAlarmPanel:
    """Validate the user input allows us to connect."""

    # Check that we're able to successfully connect and auth with the envisalink
    hostAndPort = extract_discovery_endpoint(
        data.get(CONF_EVL_DISCOVERY_PORT, DEFAULT_DISCOVERY_PORT)
    )

    panel = EnvisalinkAlarmPanel(
        data[CONF_HOST],
        port=data.get(CONF_EVL_PORT, DEFAULT_PORT),
        userName=data[CONF_USERNAME],
        password=data[CONF_PASS],
        httpHost=hostAndPort[0],
        httpPort=hostAndPort[1],
    )

    result = await panel.discover()
    if result != EnvisalinkAlarmPanel.ConnectionResult.SUCCESS:
        raise DiscoveryError(result)

    # Update version and panel from from the discovery information if it's not already
    # present.  The presence check is to account for the possibility that the config
    # had previously been imported from configuration.yaml
    if CONF_EVL_VERSION not in data:
        data[CONF_EVL_VERSION] = panel.envisalink_version
    if CONF_PANEL_TYPE not in data:
        if is_creation:
            # Only try this during initial setup of the device as it will fail if this
            # is # called from the options flow because the EVL only allows a single
            # concurrent connection.
            await panel.discover_panel_type()
        data[CONF_PANEL_TYPE] = panel.panel_type

    max_zones = EnvisalinkAlarmPanel.get_max_zones_by_version(panel.envisalink_version)

    zone_set: str = data.get(CONF_ZONE_SET, "")
    partition_set: str = data.get(CONF_PARTITION_SET, "")
    if not parse_range_string(zone_set, 1, max_zones):
        raise PanelError("invalid_zone_spec")
    if not parse_range_string(partition_set, 1, EnvisalinkAlarmPanel.get_max_partitions()):
        raise PanelError("invalid_partition_spec")

    return panel


def _get_user_data_schema(defaults: dict[str, Any], is_creation: bool = False):
    schema = {}
    if is_creation:
        schema = {
            vol.Required(CONF_ALARM_NAME, default=defaults[CONF_ALARM_NAME]): cv.string,
        }

    schema = schema | {
        vol.Required(CONF_HOST, default=defaults[CONF_HOST]): cv.string,
        vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): cv.string,
        vol.Required(CONF_PASS, default=defaults[CONF_PASS]): cv.string,
        vol.Required(CONF_PARTITION_SET, default=defaults[CONF_PARTITION_SET]): cv.string,
        vol.Required(CONF_ZONE_SET, default=defaults[CONF_ZONE_SET]): cv.string,
        vol.Optional(
            CONF_CODE, description={"suggested_value": defaults[CONF_CODE]}, default=""
        ): cv.string,
        vol.Required(CONF_EVL_PORT, default=defaults[CONF_EVL_PORT]): cv.port,
        vol.Required(
            CONF_EVL_DISCOVERY_PORT, default=defaults[CONF_EVL_DISCOVERY_PORT]
        ): cv.string,
    }
    return vol.Schema(schema)


def _get_user_data_defaults(data=None):
    if not data:
        data = {}

    config_defaults = {
        CONF_ALARM_NAME: data.get(CONF_ALARM_NAME, DEFAULT_ALARM_NAME),
        CONF_HOST: data.get(CONF_HOST, ""),
        CONF_USERNAME: data.get(CONF_USERNAME, DEFAULT_USERNAME),
        CONF_PASS: data.get(CONF_PASS, ""),
        CONF_ZONE_SET: data.get(CONF_ZONE_SET, ""),
        CONF_PARTITION_SET: data.get(CONF_PARTITION_SET, DEFAULT_PARTITION_SET),
        CONF_CODE: data.get(CONF_CODE, ""),
        CONF_EVL_PORT: data.get(CONF_EVL_PORT, DEFAULT_PORT),
        CONF_EVL_DISCOVERY_PORT: data.get(CONF_EVL_DISCOVERY_PORT, DEFAULT_DISCOVERY_PORT),
    }
    return config_defaults
