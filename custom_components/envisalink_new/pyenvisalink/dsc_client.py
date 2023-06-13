import asyncio
import datetime
import json
import logging
import re
import time

from .const import (
    STATE_CHANGE_KEYPAD,
    STATE_CHANGE_PARTITION,
    STATE_CHANGE_ZONE,
    STATE_CHANGE_ZONE_BYPASS,
)
from .dsc_envisalinkdefs import (
    KeypadLED_Flags,
    evl_ArmModes,
    evl_Commands,
    evl_PanicTypes,
    evl_ResponseTypes,
    evl_TPI_Response_Codes,
    evl_verboseTrouble,
)
from .envisalink_base_client import EnvisalinkClient

_LOGGER = logging.getLogger(__name__)


class DSCClient(EnvisalinkClient):
    """Represents a dsc alarm client."""

    def detect(prompt):
        """Given the initial connection data, determine if this is a DSC panel."""
        code = "505"
        data = "3"
        login = code + data + DSCClient.get_checksum(code, data)
        return prompt == login

    def __init__(self, panel):
        super().__init__(panel)
        self._loginEvent = asyncio.Event()
        self._bypassStateInitialized = False

    def to_chars(string):
        chars = []
        for char in string:
            chars.append(ord(char))
        return chars

    def get_checksum(code, data):
        """part of each command includes a checksum.  Calculate."""
        return ("%02X" % sum(DSCClient.to_chars(code) + DSCClient.to_chars(data)))[-2:]

    async def send_command(self, code, data, logData=None):
        """Send a command in the proper honeywell format."""
        to_send = code + data + DSCClient.get_checksum(code, data)
        await self.send_data(to_send)

    async def dump_zone_timers(self):
        """Send a command to dump out the zone timers."""
        await self.queue_command(evl_Commands["DumpZoneTimers"], "")

    async def keypresses_to_partition(self, partitionNumber, keypresses):
        """Send keypresses (max of 6) to a particular partition."""
        await self.queue_command(
            evl_Commands["PartitionKeypress"],
            str.format("{0}{1}", partitionNumber, keypresses[:6]),
        )

    async def keep_alive(self):
        """Send a keepalive command to reset it's watchdog timer."""
        await self.queue_command(evl_Commands["KeepAlive"], "")

    async def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        await self.queue_command(evl_Commands["ArmStay"], str(partitionNumber), code)

    async def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        await self.queue_command(evl_Commands["ArmAway"], str(partitionNumber), code)

    async def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        await self.queue_command(evl_Commands["ArmMax"], str(partitionNumber), code)

    async def arm_night_partition(self, code, partitionNumber, mode=None):
        """Public method to arm/max a partition."""
        await self.arm_max_partition(code, partitionNumber)

    async def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        await self.queue_command(evl_Commands["Disarm"], str(partitionNumber) + str(code), code)

    async def panic_alarm(self, panicType):
        """Public method to raise a panic alarm."""
        await self.queue_command(evl_Commands["Panic"], evl_PanicTypes[panicType])

    async def toggle_zone_bypass(self, zone):
        """Public method to toggle a zone's bypass state."""
        await self.keypresses_to_partition(1, "*1%02d#" % zone)

    async def command_output(self, code, partitionNumber, outputNumber):
        """Used to activate the selected command output"""
        await self.queue_command(
            evl_Commands["CommandOutput"],
            str.format("{0}{1}", partitionNumber, outputNumber),
            code,
        )

    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        cmd = {}
        dataoffset = 0
        if rawInput != "":
            if re.match(r"\d\d:\d\d:\d\d\s", rawInput):
                dataoffset = dataoffset + 9
            code = rawInput[dataoffset : dataoffset + 3]
            cmd["code"] = code
            cmd["data"] = rawInput[dataoffset + 3 :][:-2]

            try:
                # Interpret the login command further to see what our handler is.
                if evl_ResponseTypes[code]["handler"] == "login":
                    if cmd["data"] == "3":
                        handler = "login"
                    elif cmd["data"] == "2":
                        handler = "login_timeout"
                    elif cmd["data"] == "1":
                        handler = "login_success"
                    elif cmd["data"] == "0":
                        handler = "login_failure"

                    cmd["handler"] = "handle_%s" % handler
                else:
                    cmd["handler"] = "handle_%s" % evl_ResponseTypes[code]["handler"]
                cmd["state_change"] = evl_ResponseTypes[code].get("state_change", False)
            except KeyError:
                _LOGGER.debug(str.format("No handler defined in config for {0}, skipping...", code))

        return cmd

    def handle_login(self, code, data):
        """When the envisalink asks us for our password- send it."""
        self.create_internal_task(self.queue_login_response(), name="queue_login_response")

    async def queue_login_response(self):
        self._loginEvent.clear()
        await self.queue_command(evl_Commands["Login"], self._alarmPanel.password)

        # Wait until the 505 resposnse is received
        try:
            await asyncio.wait_for(
                self._loginEvent.wait(), timeout=self._alarmPanel.connection_timeout
            )
        except Exception:
            pass

        if not self._loggedin:
            # Timed out waiting for login
            await self.disconnect()

    def handle_login_success(self, code, data):
        """Handler for when the envisalink accepts our credentials."""
        super().handle_login_success(code, data)

        self._loginEvent.set()
        self.create_internal_task(self.complete_login(), name="complete_login")

    def handle_login_failure(self, code, data):
        """Handler for when the envisalink rejects our credentials."""
        super().handle_login_failure(code, data)
        self._loginEvent.set()

    async def complete_login(self):
        dt = datetime.datetime.now().strftime("%H%M%m%d%y")
        await self.queue_command(evl_Commands["SetTime"], dt)
        await self.queue_command(evl_Commands["StatusReport"], "")

    def handle_command_response(self, code, data):
        """Handle the envisalink's initial response to our commands."""
        if code == "500":
            _LOGGER.debug("DSC ack recieved.")
            self.command_succeeded(data)
        elif code == "501":
            _LOGGER.error("Issued command resulted in a checksum failure.")
            self.command_failed(retry=True)
        elif code == "502":
            retry = False
            if data in evl_TPI_Response_Codes:
                errorInfo = evl_TPI_Response_Codes[data]
                retry = errorInfo["retry"]
                msg = f"System error received for issued command: {errorInfo['msg']} ({data})"
                if retry:
                    _LOGGER.warn(msg)
                else:
                    _LOGGER.error(msg)

            else:
                _LOGGER.error(f"Unrecognized system error for issued command: '{data}'")
            self.command_failed(retry=retry)

    def handle_zone_state_change(self, code, data):
        """Handle when the envisalink sends us a zone change."""
        """Event 601-610."""
        now = time.time()
        parse = re.match("^[0-9]{3,4}$", data)
        if parse:
            zoneNumber = int(data[-3:])
            self._alarmPanel.alarm_state["zone"][zoneNumber]["status"].update(
                evl_ResponseTypes[code]["status"]
            )
            self._alarmPanel.alarm_state["zone"][zoneNumber]["updated"] = now

            if evl_ResponseTypes[code]["is_fault"]:
                self._alarmPanel.alarm_state["zone"][zoneNumber]["last_fault"] = now

            _LOGGER.debug(
                str.format(
                    "(zone {0}) state has updated: {1}",
                    zoneNumber,
                    json.dumps(evl_ResponseTypes[code]["status"]),
                )
            )
            return {STATE_CHANGE_ZONE: [zoneNumber]}
        else:
            _LOGGER.error("Invalid data has been passed in the zone update.")

    def handle_partition_state_change(self, code, data):
        """Handle when the envisalink sends us a partition change.
        Event 650-674, 652 is an exception, because 2 bytes are passed for partition
        and zone type."""
        if code == "652":
            parse = re.match("^[0-9]{2}$", data)
            if parse:
                partitionNumber = int(data[0])
                self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                    evl_ArmModes[data[1]]["status"]
                )
                _LOGGER.debug(
                    str.format(
                        "(partition {0}) state has updated: {1}",
                        partitionNumber,
                        json.dumps(evl_ArmModes[data[1]]["status"]),
                    )
                )
                return {STATE_CHANGE_PARTITION: [partitionNumber]}
            else:
                _LOGGER.error("Invalid data has been passed when arming the alarm.")
        else:
            parse = re.match("^[0-9]+$", data)
            if parse:
                partitionNumber = int(data[0])
                self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                    evl_ResponseTypes[code]["status"]
                )
                _LOGGER.debug(
                    str.format(
                        "(partition {0}) state has updated: {1}",
                        partitionNumber,
                        json.dumps(evl_ResponseTypes[code]["status"]),
                    )
                )

                """Log the user who last armed or disarmed the alarm"""
                if code == "700":
                    lastArmedBy = {"last_armed_by_user": int(data[1:5])}
                    self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                        lastArmedBy
                    )
                elif code == "750":
                    lastDisarmedBy = {"last_disarmed_by_user": int(data[1:5])}
                    self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                        lastDisarmedBy
                    )

                result = {STATE_CHANGE_PARTITION: [partitionNumber]}
                if code == "655" and self._alarmPanel._zoneBypassEnabled:
                    """Partition was disarmed so any zone bypasses will have been reset"""
                    cleared_zones = self.clear_zone_bypass_state()
                    if len(cleared_zones) != 0:
                        result[STATE_CHANGE_ZONE_BYPASS] = cleared_zones

                return result
            else:
                _LOGGER.error("Invalid data has been passed in the partition update.")

    def handle_send_code(self, code, data):
        """The DSC will, depending upon settings, challenge us with the code.  If the user
        passed it in, we'll send it."""
        self.create_internal_task(self.foo(), name="send_code")

    async def send_code(self):
        if self._cachedCode is None:
            _LOGGER.error("The envisalink asked for a code, but we have no code in our cache.")
        else:
            await self.send_command(evl_Commands["SendCode"], self._cachedCode)
            self._cachedCode = None

    def handle_keypad_update(self, code, data):
        """Handle general- non partition based info"""
        if code == "849":
            bits = f"{int(data,16):016b}"
            trouble_description = ""
            ac_present = True
            for i in range(0, 7):
                if bits[15 - i] == "1":
                    trouble_description += evl_verboseTrouble[i] + ", "
                    if i == 1:
                        ac_present = False
            new_status = {
                "alpha": trouble_description.strip(", "),
                "ac_present": ac_present,
            }
        else:
            new_status = evl_ResponseTypes[code]["status"]

        updatedPartitions = []
        for part in self._alarmPanel.alarm_state["partition"]:
            self._alarmPanel.alarm_state["partition"][part]["status"].update(new_status)
            updatedPartitions.append(part)
        _LOGGER.debug(str.format("(All partitions) state has updated: {0}", json.dumps(new_status)))
        return {STATE_CHANGE_KEYPAD: updatedPartitions}

    def handle_zone_bypass_update(self, code, data):
        """Handle zone bypass update triggered when *1 is used on the keypad"""
        if not self._alarmPanel._zoneBypassEnabled:
            return

        if len(data) == 16:
            updates = []
            for byte in range(8):
                bypassBitfield = int("0x" + data[byte * 2] + data[(byte * 2) + 1], 0)

                for bit in range(8):
                    zoneNumber = (byte * 8) + bit + 1
                    bypassed = bypassBitfield & (1 << bit) != 0
                    if self._alarmPanel.alarm_state["zone"][zoneNumber]["bypassed"] != bypassed:
                        updates.append(zoneNumber)
                    self._alarmPanel.alarm_state["zone"][zoneNumber]["bypassed"] = bypassed
                    _LOGGER.debug(
                        str.format(
                            "(zone {0}) bypass state has updated: {1}",
                            zoneNumber,
                            bypassed,
                        )
                    )

            _LOGGER.debug(str.format("zone bypass updates: {0}", updates))
            return {STATE_CHANGE_ZONE_BYPASS: updates}
        else:
            _LOGGER.error(
                str.format(
                    "Invalid data length ({0}) has been received in the bypass update.",
                    len(data),
                )
            )

    async def dump_zone_bypass_status(self):
        """Trigger a 616 'Bypassed Zones Bitfield Dump' to initialize the bypass state.
        There is unfortunately not a specific command to request a zone bypass dump so
        the *1# keypresses are sent instead.  It appears that limitations in the envisalink
        API (or perhaps the panel itself) makes it impossible for this feature
        to work if the alarm panel is setup to require a code to bypass zones."""

        await self.keypresses_to_partition(1, "*1#")

    def is_zone_open_from_zonedump(self, zone, ticks) -> bool:
        # DSC seems to report accurately to 0 means open, anything else means closed
        return ticks == 0

    def handle_keypad_led_state_update(self, code, data):
        if len(data) == 2:
            flags = KeypadLED_Flags()
            flags.asByte = int(data, 16)

            _LOGGER.debug(f"Keypad LED state update: {flags}")

            if (
                self._alarmPanel._zoneBypassEnabled
                and not self._bypassStateInitialized
                and flags.ready
                and flags.bypass
            ):
                # We've just started up and the LEDs indicate that there are zones bypassed
                # so request a zone bypass dump.  This is only necessary on startup
                # to get the initial state.  Zones bypassed after startup will automatically
                # trigger a 616 update.
                self.create_internal_task(
                    self.dump_zone_bypass_status(), name="dump_zone_bypass_status"
                )

            self._bypassStateInitialized = True

    def handle_keypad_led_flash_state_update(self, code, data):
        if len(data) == 2:
            flags = KeypadLED_Flags()
            flags.asByte = int(data, 16)

            _LOGGER.debug(f"Keypad LED FLASH state update: {flags}")
