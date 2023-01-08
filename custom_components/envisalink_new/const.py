"""Constants for the Envisalink_new integration."""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

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
CONF_PARTITIONNAME = "name"
CONF_PARTITIONS = "partitions"
CONF_PASS = "password"
CONF_USERNAME = "user_name"
CONF_ZONEDUMP_INTERVAL = "zonedump_interval" # OPTION
CONF_ZONENAME = "name"
CONF_ZONES = "zones"
CONF_ZONETYPE = "type"
CONF_CREATE_ZONE_BYPASS_SWITCHES = "create_zone_bypass_switches" # OPTION

PANEL_TYPE_DSC = "DSC"
PANEL_TYPE_HONEYWELL = "HONEYWELL"

DEFAULT_ALARM_NAME = "Home Alarm"
DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 4
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = "opening"
DEFAULT_PANIC = "Police"
DEFAULT_TIMEOUT = 10
DEFAULT_CREATE_ZONE_BYPASS_SWITCHES = False

EVL_MAX_ZONES = 64
EVL_MAX_PARTITIONS = 8

SIGNAL_ZONE_UPDATE = "dscalarm.zones_updated"
SIGNAL_PARTITION_UPDATE = "dscalarm.partition_updated"
SIGNAL_KEYPAD_UPDATE = "dscalarm.keypad_updated"
SIGNAL_ZONE_BYPASS_UPDATE = "dscalarm.zone_bypass_updated"

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONENAME): cv.string,
        vol.Optional(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): cv.string,
    }
)

PARTITION_SCHEMA = vol.Schema({vol.Required(CONF_PARTITIONNAME): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PANEL_TYPE): vol.All(
                    cv.string, vol.In([PANEL_TYPE_HONEYWELL, PANEL_TYPE_DSC])
                ),
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASS): cv.string,
                vol.Optional(CONF_CODE): cv.string,
                vol.Optional(CONF_PANIC, default=DEFAULT_PANIC): cv.string,
                vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_PARTITIONS): {vol.Coerce(int): PARTITION_SCHEMA},
                vol.Optional(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_EVL_VERSION, default=DEFAULT_EVL_VERSION): vol.All(
                    vol.Coerce(int), vol.Range(min=3, max=4)
                ),
                vol.Optional(CONF_EVL_KEEPALIVE, default=DEFAULT_KEEPALIVE): vol.All(
                    vol.Coerce(int), vol.Range(min=15)
                ),
                vol.Optional(
                    CONF_ZONEDUMP_INTERVAL, default=DEFAULT_ZONEDUMP_INTERVAL
                ): vol.Coerce(int),
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
                vol.Optional(CONF_CREATE_ZONE_BYPASS_SWITCHES, default=DEFAULT_CREATE_ZONE_BYPASS_SWITCHES): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_PARTITION = "partition"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        vol.Required(ATTR_PARTITION): cv.string,
    }
)

