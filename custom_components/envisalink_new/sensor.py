"""Support for Envisalink sensors (shows panel info)."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    LOGGER,
    CONF_NUM_PARTITIONS,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
)

from .models import EnvisalinkDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    controller = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for part_num in range(1, entry.data[CONF_NUM_PARTITIONS] + 1):
        entity = EnvisalinkSensor(
            hass,
            part_num,
            controller,
        )
        entities.append(entity)

    async_add_entities(entities)




class EnvisalinkSensor(EnvisalinkDevice, SensorEntity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_number, controller):
        """Initialize the sensor."""
        self._icon = "mdi:alarm"
        self._partition_number = partition_number
        name_suffix = f"partition_{partition_number}_keypad"
        self._attr_unique_id = f"{controller.unique_id}_{name_suffix}"

        LOGGER.debug("Setting up sensor for partition: %s", name_suffix)
        super().__init__(name_suffix, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_KEYPAD_UPDATE, self.async_update_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PARTITION_UPDATE, self.async_update_callback
            )
        )

    @property
    def _info(self):
        return self._controller.controller.alarm_state["partition"][self._partition_number]

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def native_value(self):
        """Return the overall state."""
        return self._info["status"]["alpha"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._info["status"]

    @callback
    def async_update_callback(self, partition):
        """Update the partition state in HA, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_write_ha_state()
