"""Support for Envisalink devices."""
import asyncio
import logging
from typing import Any
from collections.abc import Callable

from .pyenvisalink.alarm_panel import EnvisalinkAlarmPanel

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
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_PASS,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_ZONEDUMP_INTERVAL,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_KEEPALIVE,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    LOGGER,
    STATE_UPDATE_TYPE_PARTITION,
    STATE_UPDATE_TYPE_ZONE,
    STATE_UPDATE_TYPE_ZONE_BYPASS,
)

class EnvisalinkController:

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:

        self._entry_id = entry.entry_id

        # Config
        self.alarm_name = entry.title
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_EVL_PORT)
        user = entry.data.get(CONF_USERNAME)
        password = str(entry.data.get(CONF_PASS))

        # Options 
        keep_alive = entry.options.get(CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE)
        zone_dump = entry.options.get(CONF_ZONEDUMP_INTERVAL, DEFAULT_ZONEDUMP_INTERVAL)
        create_zone_bypass_switches = entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES)
        connection_timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        self.hass = hass
        self.sync_connect: asyncio.Future[EnvisalinkAlarmPanel.ConnectionResult] = asyncio.Future()

        self.controller = EnvisalinkAlarmPanel(
            host,
            port,
            user,
            password,
            zone_dump,
            keep_alive,
            hass.loop,
            connection_timeout,
            create_zone_bypass_switches,
        )

        self._listeners = {
            STATE_UPDATE_TYPE_PARTITION : { },
            STATE_UPDATE_TYPE_ZONE : { },
            STATE_UPDATE_TYPE_ZONE_BYPASS : { },
        }

        self.controller.callback_zone_timer_dump = self.async_zone_timer_dump_callback
        self.controller.callback_zone_state_change = self.async_zones_updated_callback
        self.controller.callback_partition_state_change = self.async_partition_updated_callback
        self.controller.callback_keypad_update = self.async_alarm_data_updated_callback
        self.controller.callback_connection_status = self.async_connection_status_callback
        self.controller.callback_login_failure = self.async_login_fail_callback
        self.controller.callback_login_timeout = self.async_login_timeout_callback
        self.controller.callback_login_success = self.async_login_success_callback
        self.controller.callback_zone_bypass_update = self.async_zone_bypass_update

        LOGGER.debug("Created EnvisalinkController for %s (host=%s port=%r)",
            self.alarm_name,
            host,
            port
        )

    def add_state_change_listener(self, state_type, state_key, update_callback) -> Callable[[], None]:
        """Register an entity to have a state update triggered when it's underlying data is changed."""

        def remove_listener() -> None:
            for state_types in self._listeners.values():
                for key_list in state_types.values():
                    for idx, listener in enumerate(key_list):
                        if listener[0] == remove_listener:
                            key_list.pop(idx)
                            break

        state_info = self._listeners[state_type]
        if state_key not in state_info:
            state_info[state_key] = []
        state_info[state_key].append((remove_listener, update_callback))
        return remove_listener

    def _process_state_change(self, update_type: str, update_keys : list = None):
        state_info = self._listeners[update_type]
        if update_keys is None:
            # No specific zone/partition provided so update all the listeners
            for key_list in state_info.values():
                for listener in key_list:
                    listener[1]()
        else:
            for key in update_keys:
                if key in state_info:
                    for listener in state_info[key]:
                        listener[1]()

    def _update_entity_states(self):
        """Trigger a state update for all entities"""
        for state_info in self._listeners.values():
            for key_list in state_info.values():
                for listener in key_list:
                    listener[1]()

    @property
    def unique_id(self):
        id = self.controller.mac_address
        if not id:
            LOGGER.warn("MAC address not available from EVL.  Using config entry ID as unique ID.")
            id = self._entry_id
        return id


    async def start(self) -> bool:
        LOGGER.info("Start envisalink")
        result = await self.controller.discover()
        if result != self.controller.ConnectionResult.SUCCESS:
            raise ConfigEntryNotReady(self.get_exception_message(result, f"{self.controller.host}:{self.controller.httpPort}"))

        result = await self.controller.start()
        if result != self.controller.ConnectionResult.SUCCESS:
            raise ConfigEntryNotReady(self.get_exception_message(result, f"{self.controller.host}:{self.controller.port}"))

        result = await self.sync_connect
        if result != self.controller.ConnectionResult.SUCCESS:
            await self.stop()
            raise ConfigEntryNotReady(
                self.get_exception_message(
                    result,
                    f"{self.controller.host}:{self.controller.port}"
                )
            )

        return True

    async def stop(self):
        if self.controller:
            await self.controller.stop()

    def get_exception_message(self, error, location) -> str:
        if error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
            msg = "Unable to authenticate with Envisalink"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
            msg = "Unable to connect to Envisalink"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_PANEL_TYPE:
            msg = "Unrecognized/undetermined panel type"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_EVL_VERSION:
            msg = "Unrecognized/undetermined Envisalink version"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.DISCOVERY_NOT_COMPLETE:
            msg = "Unable to complete discovery of Envisalink"
        else:
            msg = f"Unknown error: {error}"
        return f"{msg} at {location}"

    @property
    def available(self) -> bool:
        if not self.controller:
            return False
        return self.controller.is_online()

    @callback
    def async_login_fail_callback(self, data):
        """Handle when the evl rejects our login."""
        LOGGER.error("The Envisalink rejected your credentials")
        if not self.sync_connect.done():
            self.sync_connect.set_result(EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION)
        self._update_entity_states()

    @callback
    def async_login_timeout_callback(self, data):
        """Timed out trying to login"""
        LOGGER.error("Timed out trying to login to the Envisalink- retrying")
        if not self.sync_connect.done():
            self.sync_connect.set_result(EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION)
        self._update_entity_states()

    @callback
    def async_login_success_callback(self, data):
        """Handle a successful login."""
        LOGGER.info("Established a connection and logged into the Envisalink")
        if not self.sync_connect.done():
            self.sync_connect.set_result(EnvisalinkAlarmPanel.ConnectionResult.SUCCESS)
        self._update_entity_states()

    @callback
    def async_connection_status_callback(self, connected):
        """Handle when the evl rejects our login."""
        if not connected:
            LOGGER.error("Lost connection to the envisalink device.")
            if not self.sync_connect.done():
                self.sync_connect.set_result(EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED)

            # Trigger a state update for all the entities so they appear as unavailable
            self._update_entity_states()
        else:
            LOGGER.info("Connected to the envisalink device.")

    @callback
    def async_zone_timer_dump_callback(self, data):
        """Handle zone dump updates."""
        LOGGER.debug("Envisalink sent a '%s' zone timer dump event. Updating zones: %r", self.alarm_name, data)
        self._process_state_change(STATE_UPDATE_TYPE_ZONE, data)

    @callback
    def async_zones_updated_callback(self, data):
        """Handle zone state updates."""
        LOGGER.debug("Envisalink sent a '%s' zone update event. Updating zones: %r", self.alarm_name, data)
        self._process_state_change(STATE_UPDATE_TYPE_ZONE, data)

    @callback
    def async_alarm_data_updated_callback(self, data):
        """Handle non-alarm based info updates."""
        LOGGER.debug("Envisalink sent '%s' new alarm info. Updating alarms: %r", self.alarm_name, data)
        self._process_state_change(STATE_UPDATE_TYPE_PARTITION)

    @callback
    def async_partition_updated_callback(self, data):
        """Handle partition changes thrown by evl (including alarms)."""
        LOGGER.debug("The envisalink '%s' sent a partition update event: %r", self.alarm_name, data)
        self._process_state_change(STATE_UPDATE_TYPE_PARTITION, data)

    @callback
    def async_zone_bypass_update(self, data):
        """Handle zone bypass status updates."""
        LOGGER.debug("Envisalink '%s' sent a zone bypass update event. Updating zones: %r", self.alarm_name, data)
        self._process_state_change(STATE_UPDATE_TYPE_ZONE_BYPASS, data)


