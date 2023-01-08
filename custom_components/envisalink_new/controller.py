"""Support for Envisalink devices."""
import asyncio
import logging
from typing import Any

from .pyenvisalink import EnvisalinkAlarmPanel

from homeassistant.const import (
    CONF_HOST,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
#from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALARM_NAME,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PASS,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_ZONEDUMP_INTERVAL,
    CONF_ZONEDUMP_INTERVAL,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_KEEPALIVE,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    DOMAIN,
    LOGGER,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SIGNAL_ZONE_BYPASS_UPDATE,
    SIGNAL_ZONE_UPDATE,
)

#class EnvisalinkController(DataUpdateCoordinator[EnvisalinkAlarmPanel]):
class EnvisalinkController:

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        LOGGER.error(f"# EnvisalinkController: entry={entry}")

#        super().__init__(
#            hass,
#            LOGGER,
#            name=DOMAIN,
#        )

        # Config
        self.alarm_name = entry.data.get(CONF_ALARM_NAME)
        self.host = entry.data.get(CONF_HOST)
        self.port = entry.data.get(CONF_EVL_PORT)
        self.panel_type = entry.data.get(CONF_PANEL_TYPE)
        self.version = entry.data.get(CONF_EVL_VERSION)
        self.user = entry.data.get(CONF_USERNAME)
        self.password = entry.data.get(CONF_PASS)

        # Options 
        self.keep_alive = entry.options.get(CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE)
        self.zone_dump = entry.options.get(CONF_ZONEDUMP_INTERVAL, DEFAULT_ZONEDUMP_INTERVAL)
        self.create_zone_bypass_switches = entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES)
        self.connection_timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        self.hass = hass
        self.sync_connect: asyncio.Future[bool] = asyncio.Future()

        self.controller = EnvisalinkAlarmPanel(
            self.host,
            self.port,
            self.panel_type,
            self.version,
            self.user,
            self.password,
            self.zone_dump,
            self.keep_alive,
            hass.loop,
            self.connection_timeout,
            self.create_zone_bypass_switches,
        )

        self.controller.callback_zone_timer_dump = self.async_zones_updated_callback
        self.controller.callback_zone_state_change = self.async_zones_updated_callback
        self.controller.callback_partition_state_change = self.async_partition_updated_callback
        self.controller.callback_keypad_update = self.async_alarm_data_updated_callback
        self.controller.callback_login_failure = self.async_login_fail_callback
        self.controller.callback_login_timeout = self.async_connection_fail_callback
        self.controller.callback_login_success = self.async_connection_success_callback
        self.controller.callback_zone_bypass_update = self.async_zone_bypass_update

    @property
    def unique_id(self):
        id = self.controller.mac_address
        if not id:
            # TODO MAC address not available from the EVL so use the config entry instead
            raise ValueException("No unque ID available")
        return id

    async def start(self) -> bool:
        LOGGER.info("Start envisalink")
        await self.controller.start()

        if not await self.sync_connect:
            return False

# TODO
#        hass.services.async_register(
#            DOMAIN, SERVICE_CUSTOM_FUNCTION, handle_custom_function, schema=SERVICE_SCHEMA
#        )

        return True

    async def stop(self):
        if self.controller:
            await self.controller.stop()


    @callback
    def async_login_fail_callback(self, data):
        """Handle when the evl rejects our login."""
        LOGGER.error("The Envisalink rejected your credentials")
        if not self.sync_connect.done():
            self.sync_connect.set_result(False)

    @callback
    def async_connection_fail_callback(self, data):
        """Network failure callback."""
        LOGGER.error("Could not establish a connection with the Envisalink- retrying")
        if not self.sync_connect.done():
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_envisalink)
            self.sync_connect.set_result(True)

    @callback
    def async_connection_success_callback(self, data):
        """Handle a successful connection."""
        LOGGER.info("Established a connection with the Envisalink")
        if not self.sync_connect.done():
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_envisalink)
            self.sync_connect.set_result(True)

    @callback
    def async_zones_updated_callback(self, data):
        """Handle zone timer updates."""
        LOGGER.debug("Envisalink sent a zone update event. Updating zones")
        async_dispatcher_send(self.hass, SIGNAL_ZONE_UPDATE, data)

    @callback
    def async_alarm_data_updated_callback(self, data):
        """Handle non-alarm based info updates."""
        LOGGER.debug("Envisalink sent new alarm info. Updating alarms")
        async_dispatcher_send(self.hass, SIGNAL_KEYPAD_UPDATE, data)

    @callback
    def async_partition_updated_callback(self, data):
        """Handle partition changes thrown by evl (including alarms)."""
        LOGGER.debug("The envisalink sent a partition update event")
        async_dispatcher_send(self.hass, SIGNAL_PARTITION_UPDATE, data)

    @callback
    def async_zone_bypass_update(self, data):
        """Handle zone bypass status updates."""
        LOGGER.debug("Envisalink sent a zone bypass update event. Updating zones")
        async_dispatcher_send(self.hass, SIGNAL_ZONE_BYPASS_UPDATE, data)

    @callback
    async def stop_envisalink(self, event):
        """Shutdown envisalink connection and thread on exit."""
        LOGGER.info("Shutting down Envisalink")
        await self.controller.stop()

    async def handle_custom_function(self, call: ServiceCall) -> None:
        """Handle custom/PGM service."""
        custom_function = call.data.get(ATTR_CUSTOM_FUNCTION)
        partition = call.data.get(ATTR_PARTITION)
        self.controller.command_output(code, partition, custom_function)



