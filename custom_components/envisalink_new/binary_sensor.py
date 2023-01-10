"""Support for Envisalink zone states- represented as binary sensors."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .models import EnvisalinkDevice
from .const import (
    CONF_NUM_ZONES,
    CONF_ZONENAME,
    CONF_ZONES,
    CONF_ZONETYPE,
    DEFAULT_NUM_ZONES,
    DEFAULT_ZONETYPE,
    DOMAIN,
    LOGGER,
    STATE_UPDATE_TYPE_ZONE,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    controller = hass.data[DOMAIN][entry.entry_id]

    zone_info = entry.data.get(CONF_ZONES)
    entities = []
    for zone_num in range(1, entry.options.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES) + 1):
        zone_entry = None
        if zone_info and zone_num in zone_info:
            zone_entry = zone_info[zone_num]

        entity = EnvisalinkBinarySensor(
            hass,
            zone_num,
            zone_entry,
            controller,
        )
        entities.append(entity)

    async_add_entities(entities)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, zone_info, controller):
        """Initialize the binary_sensor."""
        self._zone_number = zone_number
        name_suffix = f"zone_{self._zone_number}"
        self._attr_unique_id = f"{controller.unique_id}_{name_suffix}"

        name = f"{controller.alarm_name}_{name_suffix}"
        self._zone_type = DEFAULT_ZONETYPE

        if zone_info:
            # Override the name and type if there is info from the YAML configuration
            self._zone_type = zone_info.get(CONF_ZONETYPE, DEFAULT_ZONETYPE)
            if CONF_ZONENAME in zone_info:
                name = zone_info[CONF_ZONENAME]

        LOGGER.debug("Setting up zone: %s", name)
        super().__init__(name, controller, STATE_UPDATE_TYPE_ZONE, zone_number)

    @property
    def _info(self):
        return self._controller.controller.alarm_state["zone"][self._zone_number]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}

        # The Envisalink library returns a "last_fault" value that's the
        # number of seconds since the last fault, up to a maximum of 327680
        # seconds (65536 5-second ticks).
        #
        # We don't want the HA event log to fill up with a bunch of no-op
        # "state changes" that are just that number ticking up once per poll
        # interval, so we subtract it from the current second-accurate time
        # unless it is already at the maximum value, in which case we set it
        # to None since we can't determine the actual value.

        seconds_ago = self._info["last_fault"]
        if seconds_ago < 65536 * 5:
            now = dt_util.now().replace(microsecond=0)
            delta = datetime.timedelta(seconds=seconds_ago)
            last_trip_time = (now - delta).isoformat()
        else:
            last_trip_time = None

        attr[ATTR_LAST_TRIP_TIME] = last_trip_time

        # Expose the zone number as an attribute to allow
        # for easier entity to zone mapping (e.g. to bypass
        # the zone).
        attr["zone"] = self._zone_number

        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info["status"]["open"]

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

