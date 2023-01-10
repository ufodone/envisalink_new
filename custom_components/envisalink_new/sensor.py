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
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    DEFAULT_NUM_PARTITIONS,
    STATE_UPDATE_TYPE_PARTITION,
)

from .models import EnvisalinkDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    controller = hass.data[DOMAIN][entry.entry_id]

    partition_info = entry.data.get(CONF_PARTITIONS)
    entities = []
    for part_num in range(1, entry.options.get(CONF_NUM_PARTITIONS, DEFAULT_NUM_PARTITIONS) + 1):
        part_entry = None
        if partition_info and part_num in partition_info:
            part_entry = partition_info[part_num]

        entity = EnvisalinkSensor(
            hass,
            part_num,
            part_entry,
            controller,
        )
        entities.append(entity)

    async_add_entities(entities)




class EnvisalinkSensor(EnvisalinkDevice, SensorEntity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_number, partition_info, controller):
        """Initialize the sensor."""
        self._icon = "mdi:alarm"
        self._partition_number = partition_number
        name_suffix = f"partition_{partition_number}_keypad"
        self._attr_unique_id = f"{controller.unique_id}_{name_suffix}"

        name = f"{controller.alarm_name}_{name_suffix}"
        if partition_info:
            # Override the name if there is info from the YAML configuration
            if CONF_PARTITIONNAME in partition_info:
                name = f"{partition_info[CONF_PARTITIONNAME]} Keypad"

        LOGGER.debug("Setting up sensor for partition: %s", name)
        super().__init__(name, controller, STATE_UPDATE_TYPE_PARTITION, partition_number)

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

