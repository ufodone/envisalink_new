"""Support for Envisalink zone bypass switches."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .models import EnvisalinkDevice
from .const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_NUM_ZONES,
    DOMAIN,
    LOGGER,
    SIGNAL_ZONE_BYPASS_UPDATE,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    controller = hass.data[DOMAIN][entry.entry_id]

    create_bypass_switches = entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES)
    if create_bypass_switches:
        entities = []
        for zone_num in range(1, entry.data[CONF_NUM_ZONES] + 1):
            entity = EnvisalinkSwitch(
                hass,
                zone_num,
                controller,
            )
            entities.append(entity)

        async_add_entities(entities)


class EnvisalinkSwitch(EnvisalinkDevice, SwitchEntity):
    """Representation of an Envisalink switch."""

    def __init__(self, hass, zone_number, controller):
        """Initialize the switch."""
        self._zone_number = zone_number
        name_suffix = f"zone_{self._zone_number}_bypass"
        self._attr_unique_id = f"{controller.unique_id}_{name_suffix}"

        LOGGER.debug("Setting up zone: %s", name_suffix)
        super().__init__(name_suffix, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_BYPASS_UPDATE, self.async_update_callback
            )
        )

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

    @callback
    def async_update_callback(self, bypass_map):
        """Update the zone bypass state in HA, if needed."""
        if bypass_map is None or self._zone_number in bypass_map:
            LOGGER.debug("Bypass state changed for zone %d", self._zone_number)
            self.async_write_ha_state()
