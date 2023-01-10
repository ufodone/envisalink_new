"""Constants for the Envisalink_new integration."""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_TIMEOUT,
)

DOMAIN = "envisalink_new"

LOGGER = logging.getLogger(__package__)

CONF_ALARM_NAME = "alarm_name"
CONF_NUM_ZONES = "num_zones"
CONF_NUM_PARTITIONS = "num_partitions"

CONF_EVL_KEEPALIVE = "keepalive_interval" # OPTION
CONF_EVL_PORT = "port"
CONF_EVL_VERSION = "evl_version"
CONF_PANEL_TYPE = "panel_type"
CONF_PANIC = "panic_type" # OPTION
CONF_PASS = "password"
CONF_USERNAME = "user_name"
CONF_ZONEDUMP_INTERVAL = "zonedump_interval" # OPTION
CONF_CREATE_ZONE_BYPASS_SWITCHES = "create_zone_bypass_switches" # OPTION


# Config items used only in the YAML config
CONF_ZONENAME = "name"
CONF_ZONES = "zones"
CONF_ZONETYPE = "type"
CONF_PARTITIONNAME = "name"
CONF_PARTITIONS = "partitions"

# Temporary config entry key used to store values from the YAML config that will transition
# into the ConfigEntry options
CONF_YAML_OPTIONS = "yaml_options"


PANEL_TYPE_DSC = "DSC"
PANEL_TYPE_HONEYWELL = "HONEYWELL"

DEFAULT_ALARM_NAME = "alarm"
DEFAULT_CREATE_ZONE_BYPASS_SWITCHES = False
DEFAULT_EVL_VERSION = 4
DEFAULT_KEEPALIVE = 60
DEFAULT_NUM_PARTITIONS = 1
DEFAULT_NUM_ZONES = 1
DEFAULT_PANIC = "Police"
DEFAULT_PORT = 4025
DEFAULT_TIMEOUT = 10
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = BinarySensorDeviceClass.OPENING

EVL_MAX_ZONES = 64
EVL_MAX_PARTITIONS = 8

STATE_UPDATE_TYPE_PARTITION = "partitions"
STATE_UPDATE_TYPE_ZONE = "zones"
STATE_UPDATE_TYPE_ZONE_BYPASS = "bypass"
