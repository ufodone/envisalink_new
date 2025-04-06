"""Support for Envisalink-based alarm control panels (Honeywell/DSC)."""
from __future__ import annotations

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    CONF_PANIC,
    CONF_PARTITION_SET,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    CONF_SHOW_KEYPAD,
    DEFAULT_CODE_ARM_REQUIRED,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DEFAULT_PANIC,
    DEFAULT_PARTITION_SET,
    DEFAULT_SHOW_KEYPAD,
    DOMAIN,
    HONEYWELL_ARM_MODE_INSTANT_VALUE,
    LOGGER,
    SHOW_KEYPAD_ALWAYS_VALUE,
    SHOW_KEYPAD_DISARM_VALUE,
    SHOW_KEYPAD_NEVER_VALUE,
)
from .helpers import find_yaml_info, generate_entity_setup_info, parse_range_string
from .models import EnvisalinkDevice
from .pyenvisalink.const import (
    PANEL_TYPE_HONEYWELL,
    PANEL_TYPE_UNO,
    STATE_CHANGE_PARTITION,
)

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_CODE = "code"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        vol.Optional(ATTR_CODE): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm panel based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]
    code = entry.data.get(CONF_CODE)
    panic_type = entry.options.get(CONF_PANIC, DEFAULT_PANIC)
    show_keypad = entry.options.get(CONF_SHOW_KEYPAD, DEFAULT_SHOW_KEYPAD)
    code_arm_required = entry.options.get(
        CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED[controller.controller.panel_type]
    )
    partition_info = entry.data.get(CONF_PARTITIONS)
    partition_spec: str = entry.data.get(CONF_PARTITION_SET, DEFAULT_PARTITION_SET)
    partition_set = parse_range_string(
        partition_spec, min_val=1, max_val=controller.controller.max_partitions
    )

    arm_night_mode = None
    if controller.controller.panel_type == PANEL_TYPE_HONEYWELL:
        arm_night_mode = entry.options.get(
            CONF_HONEYWELL_ARM_NIGHT_MODE, DEFAULT_HONEYWELL_ARM_NIGHT_MODE
        )

    if partition_set is not None:
        entities = []
        for part_num in partition_set:
            part_entry = find_yaml_info(part_num, partition_info)
            entity = EnvisalinkAlarm(
                hass,
                part_num,
                part_entry,
                code,
                panic_type,
                arm_night_mode,
                show_keypad,
                code_arm_required,
                controller,
            )
            entities.append(entity)

        async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_ALARM_KEYPRESS,
        {
            vol.Required(ATTR_KEYPRESS): cv.string,
        },
        "alarm_keypress",
    )

    platform.async_register_entity_service(
        SERVICE_CUSTOM_FUNCTION,
        {
            vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
            vol.Optional(ATTR_CODE): cv.string,
        },
        "invoke_custom_function",
    )


class EnvisalinkAlarm(EnvisalinkDevice, AlarmControlPanelEntity):
    """Representation of an Envisalink-based alarm panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(
        self,
        hass,
        partition_number,
        extra_yaml_conf,
        code,
        panic_type,
        arm_night_mode,
        show_keypad,
        code_arm_required,
        controller,
    ):
        """Initialize the alarm panel."""
        self._partition_number = partition_number
        self._code = code
        self._panic_type = panic_type
        self._arm_night_mode = arm_night_mode
        self._attr_code_arm_required = code_arm_required
        self._show_keypad = show_keypad

        setup_info = generate_entity_setup_info(
            controller, "partition", partition_number, None, extra_yaml_conf
        )

        name = setup_info["name"]
        self._attr_unique_id = setup_info["unique_id"]
        self._attr_has_entity_name = setup_info["has_entity_name"]

        LOGGER.debug("Setting up alarm: %s", name)
        super().__init__(name, controller, STATE_CHANGE_PARTITION, partition_number)

        if self._controller.controller.panel_type is not PANEL_TYPE_UNO:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_NIGHT

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._fixup_default_code()

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        super().async_registry_entry_updated()

        self._fixup_default_code()

    def _fixup_default_code(self):
        """Reconcile alarm control panel default code with the one configured in this integration"""
        if self._code:
            if not self._alarm_control_panel_option_default_code:
                LOGGER.warn(
                    "No default code set for AlarmControlPanel so using %s one. Please remove the %s code and set it on the AlarmControlPanel entity instead.",
                    DOMAIN,
                    DOMAIN,
                )
                self._alarm_control_panel_option_default_code = self._code
            elif self._code:
                LOGGER.warn(
                    "Both the AlarmControlPanel and %s have a default code set. The AlarmControlPanel one will be used. Please remove the 'code' value from your %s configuration to remove this warning.",
                    DOMAIN,
                    DOMAIN,
                )  # noqa: E501

        # Store the code in the controller so other entities have easy access to it.
        if self._partition_number == 1:
            self._controller.default_code = self._alarm_control_panel_option_default_code

    @property
    def code_format(self) -> CodeFormat | None:
        """Regex for code format or None if no code is required."""

        if self._show_keypad == SHOW_KEYPAD_DISARM_VALUE:
            return (
                None
                if self.alarm_state == AlarmControlPanelState.DISARMED
                else CodeFormat.NUMBER
            )

        if self._show_keypad == SHOW_KEYPAD_NEVER_VALUE:
            return None

        if self._show_keypad == SHOW_KEYPAD_ALWAYS_VALUE:
            return CodeFormat.NUMBER
        return CodeFormat.NUMBER

        if self._alarm_control_panel_option_default_code:
            return None
        return CodeFormat.NUMBER

    @property
    def _info(self):
        return self._controller.controller.alarm_state["partition"][self._partition_number]

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        state = None

        if self._info["status"]["alarm"]:
            state = AlarmControlPanelState.TRIGGERED
        elif self._is_night_mode():
            state = AlarmControlPanelState.ARMED_NIGHT
        elif self._info["status"]["armed_away"]:
            state = AlarmControlPanelState.ARMED_AWAY
        elif self._info["status"]["armed_stay"]:
            state = AlarmControlPanelState.ARMED_HOME
        elif self._info["status"]["exit_delay"]:
            state = AlarmControlPanelState.ARMING
        elif self._info["status"]["entry_delay"]:
            state = AlarmControlPanelState.PENDING
        elif self._info["status"]["alpha"]:
            state = AlarmControlPanelState.DISARMED
        return state

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._controller.controller.disarm_partition(
            str(code), self._partition_number
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._controller.controller.arm_stay_partition(
            str(code), self._partition_number
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._controller.controller.arm_away_partition(
            str(code), self._partition_number
        )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        await self._controller.controller.panic_alarm(self._panic_type)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._controller.controller.arm_night_partition(
            str(code),
            self._partition_number,
            self._arm_night_mode,
        )

    async def alarm_keypress(self, keypress=None):
        """Send custom keypress."""
        if keypress:
            await self._controller.controller.keypresses_to_partition(
                self._partition_number, keypress
            )

    async def invoke_custom_function(self, pgm, code=None):
        """Send custom/PGM to EVL."""
        await self._controller.controller.command_output(
            self.code_or_default_code(code), self._partition_number, pgm
        )

    def _is_night_mode(self) -> bool:
        if self._controller.controller.panel_type == PANEL_TYPE_HONEYWELL:
            if self._arm_night_mode == HONEYWELL_ARM_MODE_INSTANT_VALUE:
                return self._info["status"]["armed_zero_entry_delay"]

        return self._info["status"]["armed_night"]
