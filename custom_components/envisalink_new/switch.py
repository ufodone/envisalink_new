"""Support for Envisalink zone bypass switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_PANEL_TYPE,
    CONF_ZONE_SET,
    CONF_ZONENAME,
    CONF_ZONES,
    DOMAIN,
    LOGGER,
)
from .helpers import find_yaml_info, generate_entity_setup_info, parse_range_string
from .models import EnvisalinkDevice
from .pyenvisalink.const import (
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
    STATE_CHANGE_PARTITION,
    STATE_CHANGE_ZONE_BYPASS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]
    code = entry.data.get(CONF_CODE)
    entities = []

    # Only create the chime switch if the alarm code is provided for a Honeywell panel
    # or it is a DSC panel (which does not require a code to toggle the chime).
    panel_type = entry.data.get(CONF_PANEL_TYPE)
    if (panel_type == PANEL_TYPE_DSC) or (panel_type == PANEL_TYPE_HONEYWELL and code):
        entities.append(EnvisalinkChimeSwitch(hass, 1, code, controller))

    create_bypass_switches = entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES)
    if create_bypass_switches:
        zone_spec: str = entry.data.get(CONF_ZONE_SET, "")
        zone_set = parse_range_string(
            zone_spec, min_val=1, max_val=controller.controller.max_zones
        )
        zone_info = entry.data.get(CONF_ZONES)
        if zone_set is not None:
            for zone_num in zone_set:
                zone_entry = find_yaml_info(zone_num, zone_info)

                entity = EnvisalinkBypassSwitch(
                    hass,
                    zone_num,
                    zone_entry,
                    controller,
                )
                entities.append(entity)

    async_add_entities(entities)


class EnvisalinkBypassSwitch(EnvisalinkDevice, SwitchEntity):
    """Representation of an Envisalink bypass switch."""

    def __init__(self, hass, zone_number, zone_conf, controller):
        """Initialize the switch."""
        self._zone_number = zone_number

        setup_info = generate_entity_setup_info(
            controller, "zone", zone_number, "Bypass", zone_conf
        )

        name = setup_info["name"]
        self._attr_unique_id = setup_info["unique_id"]
        self._zone_type = setup_info["zone_type"]
        self._attr_has_entity_name = setup_info["has_entity_name"]

        LOGGER.debug("Setting up zone bypass switch: %s", name)
        super().__init__(name, controller, STATE_CHANGE_ZONE_BYPASS, zone_number)

    @property
    def _info(self):
        return self._controller.controller.alarm_state["zone"][self._zone_number]

    @property
    def is_on(self):
        """Return the boolean response if the zone is bypassed."""
        return self._info["bypassed"]

    async def async_turn_on(self, **kwargs):
        """Send the bypass keypress sequence to toggle the zone bypass."""
        await self._controller.controller.toggle_zone_bypass(self._zone_number)

    async def async_turn_off(self, **kwargs):
        """Send the bypass keypress sequence to toggle the zone bypass."""
        await self._controller.controller.toggle_zone_bypass(self._zone_number)


class EnvisalinkChimeSwitch(EnvisalinkDevice, SwitchEntity, RestoreEntity):
    """Representation of an Envisalink chime switch."""

    def __init__(self, hass, partition_number, code, controller):
        """Initialize the switch."""
        name = "Panel Chime"
        self._attr_unique_id = f"{controller.unique_id}_{name}"
        self._attr_has_entity_name = True
        self._partition_number = partition_number
        self._code = code

        super().__init__(name, controller, STATE_CHANGE_PARTITION, partition_number)

    @property
    def _info(self):
        return self._controller.controller.alarm_state["partition"][self._partition_number]

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart to avoid blocking startup."""
        await super().async_added_to_hass()
        self.last_state = await self.async_get_last_state()

    @property
    def _chime_status(self):
        """Returns the chime status as pyenvisalink knows. May be out of sync on DSC panels"""
        status = self._info["status"]
        if status:
            return status.get("chime", None)
        return None

    @property
    def is_on(self):
        """Return the boolean response if the chime is enabled."""
        chime_status = self._chime_status
        if chime_status is not None:
            return chime_status
        # No status from the panel yet so use HA's last saved state
        return self.last_state.state == STATE_ON if self.last_state else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the keypress sequence to toggle the chime."""
        if self._chime_status != True:
            await self._controller.controller.toggle_chime(self._code)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the keypress sequence to toggle the chime."""
        if self._chime_status != False:
            await self._controller.controller.toggle_chime(self._code)
