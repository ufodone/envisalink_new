import asyncio
import logging
import re
from enum import Enum
from functools import partial

import aiohttp

from .alarm_state import AlarmState
from .const import (
    EVL3_MAX_ZONES,
    EVL4_MAX_ZONES,
    MAX_PARTITIONS,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
)
from .dsc_client import DSCClient
from .honeywell_client import HoneywellClient

_LOGGER = logging.getLogger(__name__)

COMMAND_ERR = "Cannot run this command while disconnected. Please run start() first."


class EnvisalinkAlarmPanel:
    """This class represents an envisalink-based alarm panel."""

    class ConnectionResult(Enum):
        SUCCESS = "success"
        INVALID_AUTHORIZATION = "invalid_authorization"
        CONNECTION_FAILED = "connection_failed"
        INVALID_PANEL_TYPE = "invalid_panel_type"
        INVALID_EVL_VERSION = "invalid_evl_version"
        DISCOVERY_NOT_COMPLETE = "discovery_not_complete"
        TIMEOUT = "timeout"

    def __init__(
        self,
        host,
        port=4025,
        userName="user",
        password="user",
        zoneTimerInterval=20,
        keepAliveInterval=30,
        connectionTimeout=10,
        zoneBypassEnabled=False,
        commandTimeout=5.0,
        httpPort=8080,
    ):
        self._macAddress = None
        self._firmwareVersion = None
        self._host = host
        self._port = port
        self._httpPort = httpPort
        self._connectionTimeout = connectionTimeout
        self._panelType = None
        self._evlVersion = 0
        self._username = userName
        self._password = password
        self._keepAliveInterval = keepAliveInterval
        self._zoneTimerInterval = zoneTimerInterval
        self._maxPartitions = EnvisalinkAlarmPanel.get_max_partitions()
        self._alarmState = None
        self._client = None
        self._zoneBypassEnabled = zoneBypassEnabled
        self._commandTimeout = commandTimeout

        self._connectionStatusCallback = self._defaultCallback
        self._loginSuccessCallback = partial(self._defaultCallback, None)
        self._loginFailureCallback = partial(self._defaultCallback, None)
        self._loginTimeoutCallback = partial(self._defaultCallback, None)
        self._keypadUpdateCallback = self._defaultCallback
        self._zoneStateChangeCallback = self._defaultCallback
        self._partitionStateChangeCallback = self._defaultCallback
        self._zoneBypassStateChangeCallback = self._defaultCallback
        self._cidEventCallback = self._defaultCallback

        loggingconfig = {
            "level": "DEBUG",
            "format": "%(asctime)s %(levelname)s <%(name)s %(module)s %(funcName)s> %(message)s",
        }

        logging.basicConfig(**loggingconfig)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def httpPort(self):
        return self._httpPort

    @property
    def connection_timeout(self):
        return self._connectionTimeout

    @property
    def command_timeout(self):
        return self._commandTimeout

    @property
    def user_name(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def panel_type(self):
        return self._panelType

    @panel_type.setter
    def panel_type(self, panel_type):
        self._panelType = panel_type

    @property
    def envisalink_version(self):
        return self._evlVersion

    @envisalink_version.setter
    def envisalink_version(self, version):
        self._evlVersion = version

    @property
    def keepalive_interval(self):
        return self._keepAliveInterval

    @property
    def zone_timer_interval(self):
        return self._zoneTimerInterval

    @property
    def alarm_state(self):
        return self._alarmState

    @property
    def firmware_version(self):
        return self._firmwareVersion

    @property
    def mac_address(self):
        return self._macAddress

    @property
    def max_zones(self):
        return EnvisalinkAlarmPanel.get_max_zones_by_version(self._evlVersion)

    def get_max_zones_by_version(version) -> int:
        return EVL3_MAX_ZONES if version < 4 else EVL4_MAX_ZONES

    def get_max_partitions() -> int:
        return MAX_PARTITIONS

    @property
    def max_partitions(self):
        return self._maxPartitions

    @property
    def callback_connection_status(self):
        return self._connectionStatusCallback

    @callback_connection_status.setter
    def callback_connection_status(self, value):
        self._connectionStatusCallback = value

    @property
    def callback_login_success(self):
        return self._loginSuccessCallback

    @callback_login_success.setter
    def callback_login_success(self, value):
        self._loginSuccessCallback = value

    @property
    def callback_login_failure(self):
        return self._loginFailureCallback

    @callback_login_failure.setter
    def callback_login_failure(self, value):
        self._loginFailureCallback = value

    @property
    def callback_login_timeout(self):
        return self._loginTimeoutCallback

    @callback_login_timeout.setter
    def callback_login_timeout(self, value):
        self._loginTimeoutCallback = value

    @property
    def callback_keypad_update(self):
        return self._keypadUpdateCallback

    @callback_keypad_update.setter
    def callback_keypad_update(self, value):
        self._keypadUpdateCallback = value

    @property
    def callback_zone_state_change(self):
        return self._zoneStateChangeCallback

    @callback_zone_state_change.setter
    def callback_zone_state_change(self, value):
        self._zoneStateChangeCallback = value

    @property
    def callback_zone_bypass_state_change(self):
        return self._zoneBypassStateChangeCallback

    @callback_zone_bypass_state_change.setter
    def callback_zone_bypass_state_change(self, value):
        self._zoneBypassStateChangeCallback = value

    @property
    def callback_partition_state_change(self):
        return self._partitionStateChangeCallback

    @callback_partition_state_change.setter
    def callback_partition_state_change(self, value):
        self._partitionStateChangeCallback = value

    @property
    def callback_realtime_cid_event(self):
        return self._cidEventCallback

    @callback_realtime_cid_event.setter
    def callback_realtime_cid_event(self, value):
        self._cidEventCallback = value

    def _defaultCallback(self, data):
        """This is the callback that occurs when the client doesn't subscribe."""
        _LOGGER.debug("Callback has not been set by client.")

    async def start(self):
        result = await self.discover_panel_type()
        if result != self.ConnectionResult.SUCCESS:
            return result

        self._alarmState = AlarmState.get_initial_alarm_state(
            max(EVL3_MAX_ZONES, EVL4_MAX_ZONES), MAX_PARTITIONS
        )

        """Connect to the envisalink, and listen for events to occur."""
        logging.info(
            str.format(
                "Connecting to envisalink on host: {0}, port: {1}",
                self._host,
                self._port,
            )
        )
        self._syncConnect: asyncio.Future[self.ConnectionResult] = asyncio.Future()
        if self._panelType == PANEL_TYPE_HONEYWELL:
            self._client = HoneywellClient(self)
            self._client.start()
        elif self._panelType == PANEL_TYPE_DSC:
            self._client = DSCClient(self)
            self._client.start()
        else:
            _LOGGER.error("Unexpected panel type: '%s'", self._panelType)
            return self.ConnectionResult.INVALID_PANEL_TYPE

        # Wait until we are successfully connected and authenticated
        try:
            result = await asyncio.wait_for(self._syncConnect, self.connection_timeout)
        except asyncio.exceptions.TimeoutError:
            result = self.ConnectionResult.TIMEOUT

        if result != self.ConnectionResult.SUCCESS:
            await self.stop()
        return result

    async def stop(self):
        """Shut down and close our connection to the envisalink."""
        if self._client:
            _LOGGER.info("Disconnecting from the envisalink...")
            await self._client.stop()
        else:
            _LOGGER.error(COMMAND_ERR)

    async def dump_zone_timers(self):
        """Request a zone timer dump from the envisalink."""
        if self._client:
            await self._client.dump_zone_timers()
        else:
            _LOGGER.error(COMMAND_ERR)

    async def change_partition(self, partitionNumber):
        """Request that the default partition be changed."""
        if self._client:
            await self._client.change_partition(partitionNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def keypresses_to_default_partition(self, keypresses):
        """Send a key to the current partition."""
        if self._client:
            await self._client.keypresses_to_default_partition(keypresses)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def keypresses_to_partition(self, partitionNumber, keypresses):
        """Send a key to a partition other than the current one."""
        if self._client:
            await self._client.keypresses_to_partition(partitionNumber, keypresses)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        if self._client:
            await self._client.arm_stay_partition(code, partitionNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        if self._client:
            await self._client.arm_away_partition(code, partitionNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        if self._client:
            await self._client.arm_max_partition(code, partitionNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def arm_night_partition(self, code, partitionNumber, mode=None):
        """Public method to arm/night a partition."""
        if self._client:
            await self._client.arm_night_partition(code, partitionNumber, mode)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        if self._client:
            await self._client.disarm_partition(code, partitionNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def panic_alarm(self, panic_type):
        """Public method to raise a panic alarm."""
        if self._client:
            await self._client.panic_alarm(panic_type)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def toggle_zone_bypass(self, zone):
        """Public method to toggle a zone's bypass state."""
        if not self._zoneBypassEnabled:
            _LOGGER.error(COMMAND_ERR)
        elif self._client:
            await self._client.toggle_zone_bypass(zone)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def toggle_chime (self, code)
        """Public method to toggle chime."""
        if self._client:
            await self._client.toggle_chime(code)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def command_output(self, code, partitionNumber, outputNumber):
        """Public method to activate an output"""
        if self._client:
            await self._client.command_output(code, partitionNumber, outputNumber)
        else:
            _LOGGER.error(COMMAND_ERR)

    async def discover_device_details(self) -> bool:
        self._evlVersion = 0
        self._panelType = None

        try:
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(self._username, self._password),
                timeout=aiohttp.ClientTimeout(total=self.connection_timeout),
            ) as client:
                url = f"http://{self._host}:{self._httpPort}/2"
                resp = await client.get(url)
                if resp.status != 200:
                    _LOGGER.warn(
                        "Unable to discover Envisalink version and panel type: '%s'",
                        resp.status,
                    )
                    return False

                # Try and scrape the HTML for the EVL version and panel type
                html = await resp.text()
                version_regex = r"<TITLE>Envisalink ([0-9])<\/TITLE>"

                m = re.search(version_regex, html)
                if m is None or m.lastindex != 1:
                    _LOGGER.warn("Unable to determine version: raw HTML: %s", html)
                else:
                    self._evlVersion = int(m.group(1))

                panel_regex = ">Security Subsystem - ([^<]*)<"
                m = re.search(panel_regex, html)
                if m is None or m.lastindex != 1:
                    _LOGGER.warn("Unable to determine panel type: raw HTML: %s", html)
                else:
                    self._panelType = m.group(1).upper()
                    if self._panelType not in [PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL]:
                        _LOGGER.warn("Unrecognized panel type: %s", self._panelType)
        except Exception as ex:
            _LOGGER.error("Unable to fetch panel information: %s", ex)
            return self.ConnectionResult.CONNECTION_FAILED

        _LOGGER.info("Discovered Envisalink %s: %s", self._evlVersion, self._panelType)
        return True

    async def discover(self) -> ConnectionResult:
        self._macAddress = None
        self._firmwareVersion = None

        try:
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(self._username, self._password),
                timeout=aiohttp.ClientTimeout(total=self.connection_timeout),
            ) as client:
                url = f"http://{self._host}:{self._httpPort}/3"
                resp = await client.get(url)
                if resp.status == 401:
                    _LOGGER.error("Unable to validate connection: invalid authorization.")
                    return self.ConnectionResult.INVALID_AUTHORIZATION
                elif resp.status == 404:
                    # Connection was successful but unable to extract FW and MAC info
                    _LOGGER.warn(
                        (
                            "Connection successful but unable to fetch FW/MAC: "
                            "404 (page not found): '%s'"
                        ),
                        url,
                    )
                elif resp.status != 200:
                    # Connection was successful but unable to extract FW and MAC info
                    _LOGGER.warn(
                        "Connection successful but unable to fetch FW/MAC: '%s'",
                        resp.status,
                    )
                else:
                    # Attempt to extract the firmware version and MAC address from the returned HTML
                    html = await resp.text()
                    fw_regex = "Firmware Version: ([^ ]*)"
                    mac_regex = "MAC: ([0-9a-fA-F]*)"

                    m = re.search(fw_regex, html)
                    if m is None or m.lastindex != 1:
                        _LOGGER.warn("# Unable to extract Firmware version")
                    else:
                        self._firmwareVersion = m.group(1)

                    m = re.search(mac_regex, html)
                    if m is None or m.lastindex != 1:
                        _LOGGER.warn("# Unable to extract MAC address")
                    else:
                        self._macAddress = m.group(1).lower()
        except Exception as ex:
            _LOGGER.error("Unable to validate connection: %r", ex)
            return self.ConnectionResult.CONNECTION_FAILED

        await self.discover_device_details()

        _LOGGER.info(
            f"Firmware Version: '{self._firmwareVersion}' / MAC address: '{self._macAddress}'"
        )
        return self.ConnectionResult.SUCCESS

    async def discover_panel_type(self) -> ConnectionResult:
        _LOGGER.info("Checking panel type for %s", self.host)
        self._panelType = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.connection_timeout
            )
            data = await asyncio.wait_for(
                reader.readuntil(separator=b"\n"), self.connection_timeout
            )
            if data:
                data = data.decode("ascii").strip()
                if HoneywellClient.detect(data):
                    self._panelType = PANEL_TYPE_HONEYWELL
                    _LOGGER.info("Panel type: %s", self._panelType)
                    return self.ConnectionResult.SUCCESS
                elif DSCClient.detect(data):
                    self._panelType = PANEL_TYPE_DSC
                    _LOGGER.info("Panel type: %s", self._panelType)
                    return self.ConnectionResult.SUCCESS
            _LOGGER.error("Unable to determine panel type from connection data: '%s'", data)
        except ConnectionResetError:
            _LOGGER.error(
                "Unable to connect to %s; it is likely that another client is already connected",
                self.host,
            )
        except Exception as ex:
            _LOGGER.error("Unable to connect to %s: %r", self.host, ex)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        return self.ConnectionResult.INVALID_PANEL_TYPE

    def is_online(self):
        if not self._client:
            return False
        return self._client.is_online()

    def handle_connection_status(self, status):
        if not status and not self._syncConnect.done():
            self._syncConnect.set_result(self.ConnectionResult.CONNECTION_FAILED)

        self.callback_connection_status(status)

    def handle_login_success(self):
        if not self._syncConnect.done():
            self._syncConnect.set_result(self.ConnectionResult.SUCCESS)
        self.callback_login_success()

    def handle_login_failure(self):
        if not self._syncConnect.done():
            self._syncConnect.set_result(self.ConnectionResult.INVALID_AUTHORIZATION)
        self.callback_login_failure()

    def handle_login_timeout(self):
        if not self._syncConnect.done():
            self._syncConnect.set_result(self.ConnectionResult.INVALID_AUTHORIZATION)
        self.callback_login_timeout()
