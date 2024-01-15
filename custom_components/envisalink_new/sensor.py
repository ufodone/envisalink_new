"""Support for Envisalink sensors (shows panel info)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PARTITION_SET,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    CONF_ZONE_SET,
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
    STATE_CHANGE_ZONE,
)

_attribute_sensor_info = {
    "partition": {
        "ac_present": {
            "name": "AC Present",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:power-plug",
        },
        "ready": {
            "name": "Ready",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:check",
        },
        "bat_trouble": {
            "name": "Battery Trouble",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:battery-alert",
        },
        "trouble": {
            "name": "Trouble",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:alert",
        },
        "fire": {
            "name": "Fire",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:fire",
        },
        "alarm": {
            "name": "Alarm",
            "panels": [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL],
            "icon": "mdi:alarm-light",
        },
    },
    "zone": {
        "low_battery": {
            "name": "Low Battery",
            "panels": [PANEL_TYPE_DSC],
            "icon": "mdi:battery-alert",
        },
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm keypad entity based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Setup partition sensors
    partition_spec: str = entry.data.get(CONF_PARTITION_SET, "")
    partition_set = parse_range_string(
        partition_spec, min_val=1, max_val=controller.controller.max_partitions
    )
    partition_info = entry.data.get(CONF_PARTITIONS)
    if partition_set is not None:
        for part_num in partition_set:
            part_entry = find_yaml_info(part_num, partition_info)

            entity = EnvisalinkKeypadSensor(
                hass,
                part_num,
                part_entry,
                controller,
            )
            entities.append(entity)

            # Create additional sensors to reflect attributes tracked by pyenvisalink
            for attr, info in _attribute_sensor_info["partition"].items():
                if controller.controller.panel_type in info["panels"]:
                    entity = EnvisalinkAttributeSensor(
                        hass,
                        "partition",
                        attr,
                        part_num,
                        part_entry,
                        controller,
                    )
                    entities.append(entity)

    # Setup zone sensors
    zone_spec: str = entry.data.get(CONF_ZONE_SET, "")
    zone_set = parse_range_string(
        zone_spec, min_val=1, max_val=controller.controller.max_zones
    )

    zone_info = entry.data.get(CONF_ZONES)
    if zone_set is not None:
        for zone_num in zone_set:
            zone_entry = find_yaml_info(zone_num, zone_info)

            for attr, info in _attribute_sensor_info["zone"].items():
                if controller.controller.panel_type in info["panels"]:
                    entity = EnvisalinkAttributeSensor(
                        hass,
                        "zone",
                        attr,
                        zone_num,
                        zone_entry,
                        controller,
                    )
                    entities.append(entity)

    if entities:
        async_add_entities(entities)


class EnvisalinkKeypadSensor(EnvisalinkDevice, SensorEntity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_number, partition_info, controller):
        """Initialize the sensor."""
        self._icon = "mdi:alarm-panel"
        self._partition_number = partition_number
        name = f"Partition {partition_number} Keypad"
        self._attr_unique_id = f"{controller.unique_id}_{name}"

        self._attr_has_entity_name = True
        if partition_info:
            # Override the name if there is info from the YAML configuration
            if CONF_PARTITIONNAME in partition_info:
                name = f"{partition_info[CONF_PARTITIONNAME]} Keypad"
                self._attr_has_entity_name = False

        LOGGER.debug("Setting up sensor for partition: %s", name)
        super().__init__(name, controller, STATE_CHANGE_PARTITION, partition_number)

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


class EnvisalinkAttributeSensor(EnvisalinkDevice, SensorEntity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, attr_type, evl_attr_name, index, extra_yaml_conf, controller):
        """Initialize the sensor."""

        sensor_info = _attribute_sensor_info[attr_type]

        self._icon = sensor_info[evl_attr_name]["icon"]
        self._evl_attr_type = attr_type
        self._evl_attr_name = evl_attr_name
        self._index = index

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

        LOGGER.debug("Setting up sensor: %s", name)
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
    def native_value(self):
        """Return the status field that represents the sensor state."""
        return self._info["status"].get(self._evl_attr_name, STATE_UNKNOWN)
