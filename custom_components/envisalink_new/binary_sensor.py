"""Support for Envisalink zone states- represented as binary sensors."""
from __future__ import annotations

import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LAST_TRIP_TIME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PARTITION_SET,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    CONF_WIRELESS_ZONE_SET,
    CONF_ZONE_SET,
    CONF_ZONENAME,
    CONF_ZONES,
    CONF_ZONETYPE,
    DEFAULT_ZONETYPE,
    DOMAIN,
    LOGGER,
)
from .helpers import (
    build_zone_to_partition_map,
    find_yaml_info,
    generate_entity_setup_info,
    parse_range_string,
)
from .models import EnvisalinkDevice
from .pyenvisalink.const import (
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
    PANEL_TYPE_UNO,
    STATE_CHANGE_PARTITION,
    STATE_CHANGE_ZONE,
)

_attribute_sensor_info = {
    "partition": {
        "ac_present": {
            "name": "AC Power",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO],
            "icon": "mdi:power-plug",
            "device_class": BinarySensorDeviceClass.POWER,
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "ready": {
            "name": "Ready",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO],
            "icon": "mdi:check",
            "device_class": None,
        },
        "bat_trouble": {
            "name": "Panel Battery",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO],
            "icon": "mdi:battery-alert",
            "device_class": BinarySensorDeviceClass.PROBLEM,
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "trouble": {
            "name": "Panel Health",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO],
            "icon": "mdi:alert",
            "device_class": BinarySensorDeviceClass.PROBLEM,
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "bell_trouble": {
            "name": "System Bell",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_UNO],
            "icon": "mdi:battery-alert",
            "device_class": BinarySensorDeviceClass.PROBLEM,
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "fire": {
            "name": "Fire",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:fire",
            "device_class": BinarySensorDeviceClass.SMOKE,
        },
        "alarm": {
            "name": "Alarm",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL, PANEL_TYPE_UNO],
            "icon": "mdi:alarm-light",
            "device_class": None,
        },
    },
    "zone": {
        "low_battery": {
            "name": "Wireless Sensor Battery",
            "panels": [PANEL_TYPE_DSC],
            "icon": "mdi:battery-alert",
            "device_class": BinarySensorDeviceClass.BATTERY,
            "zone_set": CONF_WIRELESS_ZONE_SET,
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "fault": {
            "name": "Fault",
            "panels": [PANEL_TYPE_DSC],
            "icon": "mdi:alarm-light",
            "device_class": None,
        },
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the zone binary sensors based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Setup zone sensors
    zone_spec: str = entry.data.get(CONF_ZONE_SET, "")
    zone_set = parse_range_string(
        zone_spec, min_val=1, max_val=controller.controller.max_zones
    )

    zone_to_partition_map = build_zone_to_partition_map(
        entry, controller.controller.max_zones, controller.controller.max_partitions
    )

    zone_info = entry.data.get(CONF_ZONES)
    if zone_set is not None:
        for zone_num in zone_set:
            zone_entry = find_yaml_info(zone_num, zone_info)

            partition = zone_to_partition_map[zone_num]
            entity = EnvisalinkBinarySensor(
                hass,
                zone_num,
                zone_entry,
                partition,
                controller,
            )
            entities.append(entity)

            for attr, info in _attribute_sensor_info["zone"].items():
                if controller.controller.panel_type in info["panels"]:
                    should_create = True
                    zone_set_option = info.get("zone_set")
                    if zone_set_option:
                        enable_spec: str = entry.options.get(zone_set_option, "")
                        enabled_zones = parse_range_string(
                            enable_spec, min_val=1, max_val=controller.controller.max_zones
                        )
                        should_create = enabled_zones and zone_num in enabled_zones

                    if should_create:
                        entity = EnvisalinkAttributeBinarySensor(
                            hass,
                            "zone",
                            attr,
                            zone_num,
                            zone_entry,
                            controller,
                            partition,
                        )
                        entities.append(entity)

    # Setup partition sensors
    partition_spec: str = entry.data.get(CONF_PARTITION_SET, "")
    partition_set = parse_range_string(
        partition_spec, min_val=1, max_val=controller.controller.max_partitions
    )
    partition_info = entry.data.get(CONF_PARTITIONS)
    if partition_set is not None:
        for part_num in partition_set:
            part_entry = find_yaml_info(part_num, partition_info)

            # Create sensors to reflect attributes tracked by pyenvisalink
            for attr, info in _attribute_sensor_info["partition"].items():
                if controller.controller.panel_type in info["panels"]:
                    entity = EnvisalinkAttributeBinarySensor(
                        hass,
                        "partition",
                        attr,
                        part_num,
                        part_entry,
                        controller,
                    )
                    entities.append(entity)

    async_add_entities(entities)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorEntity, RestoreEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, zone_conf, partition, controller):
        """Initialize the binary_sensor."""
        self._zone_number = zone_number
        self._partition = partition

        setup_info = generate_entity_setup_info(
            controller, "zone", zone_number, None, zone_conf
        )

        name = setup_info["name"]
        self._attr_unique_id = setup_info["unique_id"]
        self._zone_type = setup_info["zone_type"]
        self._attr_has_entity_name = setup_info["has_entity_name"]

        LOGGER.debug("Setting up zone: %s", name)
        super().__init__(name, controller, STATE_CHANGE_ZONE, zone_number)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        self.last_state = await self.async_get_last_state()

    @property
    def _info(self):
        return self._controller.controller.alarm_state["zone"][self._zone_number]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}

        last_fault = self._info["last_fault"]
        if not last_fault:
            # Since the EVL does not keep track of the last fault time, use the HA restored
            # value if no zone fault has been detected since HA was last restarted.
            if self.last_state:
                attr[ATTR_LAST_TRIP_TIME] = self.last_state.attributes.get(
                    ATTR_LAST_TRIP_TIME
                )
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
        else:
            attr[ATTR_LAST_TRIP_TIME] = datetime.datetime.fromtimestamp(
                last_fault
            ).isoformat()

        # Expose the zone and partition numbers as attributes to allow
        # for easier entity to zone mapping (e.g. to bypass
        # the zone).
        attr["zone"] = self._zone_number
        attr["partition"] = self._partition

        # Expose whether the zone is currently bypassed
        attr["bypassed"] = self._info["bypassed"]

        for key, value in self._info["status"].items():
            attr[key] = value

        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info["status"]["open"]

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type


class EnvisalinkAttributeBinarySensor(EnvisalinkDevice, BinarySensorEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(
        self,
        hass,
        attr_type,
        evl_attr_name,
        index,
        extra_yaml_conf,
        controller,
        partition=None,
    ):
        """Initialize the sensor."""

        sensor_info = _attribute_sensor_info[attr_type]

        self._icon = sensor_info[evl_attr_name]["icon"]
        self._attr_device_class = sensor_info[evl_attr_name]["device_class"]
        if "entity_category" in sensor_info[evl_attr_name]:
            self._attr_entity_category = sensor_info[evl_attr_name]["entity_category"]
        self._evl_attr_type = attr_type
        self._evl_attr_name = evl_attr_name
        self._index = index
        if partition:
            self._partition = partition

        setup_info = generate_entity_setup_info(
            controller,
            attr_type,
            index,
            sensor_info[evl_attr_name]["name"],
            extra_yaml_conf,
        )
        name = setup_info["name"]
        self._attr_unique_id = setup_info["unique_id"]
        self._attr_has_entity_name = setup_info["has_entity_name"]

        LOGGER.debug("Setting up binary_sensor: %s", name)
        super().__init__(
            name,
            controller,
            STATE_CHANGE_PARTITION if attr_type == "partition" else STATE_CHANGE_ZONE,
            index,
        )

    @property
    def _info(self):
        return self._controller.controller.alarm_state[self._evl_attr_type][self._index]

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info["status"].get(self._evl_attr_name)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}

        if self._evl_attr_type == "zone":
            attr["zone"] = self._index
            attr["partition"] = self._partition
        return attr
