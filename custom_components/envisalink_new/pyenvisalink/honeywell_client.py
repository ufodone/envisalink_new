import json
import logging
import re
import time

from .envisalink_base_client import EnvisalinkClient
from .honeywell_envisalinkdefs import (
    IconLED_Flags,
    evl_ArmDisarm_CIDs,
    evl_CID_Events,
    evl_CID_Qualifiers,
    evl_Commands,
    evl_PanicTypes,
    evl_Partition_Status_Codes,
    evl_ResponseTypes,
    evl_TPI_Response_Codes,
    evl_Virtual_Keypad_How_To_Beep,
    get_partition_state,
    get_zone_report_type,
)

_LOGGER = logging.getLogger(__name__)


class HoneywellClient(EnvisalinkClient):
    """Represents a honeywell alarm client."""

    def __init__(self, panel, loop):
        super().__init__(panel, loop)
        self._zoneTimers = {}

    def handle_zone_timer_dump(self, code, data):
        """Handle the zone timer data."""
        # TODO: Is there any reason to use zone timer dumps?

    async def keep_alive(self):
        await self.queue_command(evl_Commands["KeepAlive"], "")

    async def send_command(self, code, data, logData=None):
        """Send a command in the proper honeywell format."""
        to_send = "^" + code + "," + data + "$"
        await self.send_data(to_send, logData)

    async def dump_zone_timers(self):
        """Send a command to dump out the zone timers."""
        await self.queue_command(evl_Commands["DumpZoneTimers"], "")

    async def queue_keypresses_to_partition(self, partitionNumber, keypresses, logData):
        commands = []
        for idx, char in enumerate(keypresses):
            log = data = f"{partitionNumber},{char}"
            if logData:
                log = f"{partitionNumber},{logData[idx]}"

            commands.append(
                {
                    "cmd": evl_Commands["PartitionKeypress"],
                    "data": data,
                    "log": log,
                }
            )

        # Queue up all the keypresses together to ensure an unrelated command cannot
        # be inserted in the middle.
        await self.queue_commands(commands)

    async def keypresses_to_partition(self, partitionNumber, keypresses):
        """Send keypresses to a particular partition."""
        await self.queue_keypresses_to_partition(partitionNumber, keypresses, None)

    async def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        await self.queue_keypresses_to_partition(
            partitionNumber,
            code + "3",
            ("*" * len(code)) + "3",
        )

    async def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        await self.queue_keypresses_to_partition(
            partitionNumber,
            code + "2",
            ("*" * len(code)) + "2",
        )

    async def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        await self.queue_keypresses_to_partition(
            partitionNumber,
            code + "4",
            ("*" * len(code)) + "4",
        )

    async def arm_night_partition(self, code, partitionNumber, mode=None):
        """Public method to arm/max a partition."""
        mode_keys = "33"
        if mode is not None:
            mode_keys = mode
        await self.queue_keypresses_to_partition(
            partitionNumber,
            code + mode_keys,
            ("*" * len(code)) + mode_keys,
        )

    async def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        await self.queue_keypresses_to_partition(
            partitionNumber,
            code + "1",
            ("*" * len(code)) + "1",
        )

    async def panic_alarm(self, panicType):
        """Public method to raise a panic alarm."""
        await self.keypresses_to_partition(1, evl_PanicTypes[panicType])

    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        cmd = {}
        _LOGGER.debug(str.format("Data received:{0}", rawInput))

        parse = re.match(r"([%\^].+)\$", rawInput)
        if parse and parse.group(1):
            # keep first sentinel char to tell difference between tpi and
            # Envisalink command responses.  Drop the trailing $ sentinel.
            inputList = parse.group(1).split(",")
            code = inputList[0]
            cmd["code"] = code
            cmd["data"] = ",".join(inputList[1:])
            _LOGGER.debug(str.format("Code:{0} Data:{1}", code, cmd["data"]))
        elif not self._loggedin:
            # assume it is login info
            code = rawInput
            cmd["code"] = code
            cmd["data"] = ""
        else:
            _LOGGER.error("Unrecognized data recieved from the envisalink. Ignoring.")
            return None
        try:
            cmd["handler"] = "handle_%s" % evl_ResponseTypes[code]["handler"]
            cmd["callback"] = "callback_%s" % evl_ResponseTypes[code]["handler"]
        except KeyError:
            _LOGGER.warning(str.format("No handler defined in config for {0}, skipping...", code))

        return cmd

    def handle_login(self, code, data):
        """When the envisalink asks us for our password- send it."""
        self.create_internal_task(self.queue_login_response(), name="queue_login_response")

    async def queue_login_response(self):
        await self.send_data(self._alarmPanel.password)

    def handle_command_response(self, code, data):
        """Handle the envisalink's initial response to our commands."""
        if data in evl_TPI_Response_Codes:
            responseInfo = evl_TPI_Response_Codes[data]
            _LOGGER.debug("Envisalink response: " + responseInfo["msg"])
            if data == "00":
                self.command_succeeded(code[1:])
            else:
                _LOGGER.error(
                    "error sending command to envisalink.  Response was: " + responseInfo["msg"]
                )
                self.command_failed(retry=responseInfo["retry"])
        else:
            _LOGGER.error(str.format("Unrecognized response code ({0}) received", data))
            self.command_failed(retry=False)

    def handle_hw_keypad_update(self, code, data):
        """Handle the response to when the envisalink sends keypad updates our way."""
        results = {"partitions": [], "zones": [], "bypass": [], "zone_update":False, "bypass_update": False}
        dataList = data.split(",")
        # Custom messages and alpha fields might contain unescaped commas, so we'll recombine them:
        if len(dataList) > 5:
            dataList[4] = ",".join(dataList[4:])
            del dataList[5:]
        # make sure data is in format we expect, current TPI seems to send bad data every so often
        # TODO: Make this a regex...
        if "%" in data:
            _LOGGER.error("Data format invalid from Envisalink, ignoring...")
            return

        partitionNumber = int(dataList[0])
        if not (partitionNumber in self._zoneTimers.keys()):
            self._zoneTimers[partitionNumber] = {}
        results['partitions'].append(partitionNumber)
        flags = IconLED_Flags()
        flags.asShort = int(dataList[1], 16)
        # user_zone_field = int(dataList[2])
        beep = evl_Virtual_Keypad_How_To_Beep.get(dataList[3], "unknown")
        alpha = dataList[4]
        partition_status = get_partition_state(flags, alpha)
        zone_code = get_zone_report_type(flags,alpha)
        try:
            # ready seems to already be populated by this point, but trap in case of error.
            prior_ready = self._alarmPanel.alarm_state['partition'][partitionNumber]['status']['ready']
        except:
            _LOGGER.debug(f'Ready state unknown for partition {partitionNumber}')
            prior_ready = False
        try:
            # This will throw an error the first time through after start up.
            prior_bypass = self._alarmPanel.alarm_state['partition'][partitionNumber]['status']['armed_bypass']
        except:
            _LOGGER.debug(f'Bypass state unknown for partition {partitionNumber}')
            prior_bypass = True

        # TODO "armed_bypass" is included in the state below but just passes the bypass flag. How is that used?
        # TODO "bypass" is part of "status" but isn't updated below.
        self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
            {
                "alarm": bool(flags.alarm),
                "alarm_in_memory": bool(flags.alarm_in_memory),
                "armed_away": bool(flags.armed_away),
                "ac_present": bool(flags.ac_present),
                "armed_bypass": bool(flags.bypass),
                "chime": bool(flags.chime),
                "armed_zero_entry_delay": bool(flags.armed_zero_entry_delay),
                "alarm_fire_zone": bool(flags.alarm_fire_zone),
                "trouble": bool(flags.system_trouble),
                "ready": bool(flags.ready),
                "fire": bool(flags.fire),
                "armed_stay": bool(flags.armed_stay),
                "alpha": alpha,
                "beep": beep,
            }
        )

        if (partition_status == 'ready') and not prior_ready:
            # Clear all zones known to be in this partition
            _LOGGER.debug(f'Clear partition {partitionNumber}')
            for z in list(self._zoneTimers[partitionNumber]):
                _LOGGER.debug(f'Timer {z} :: {self._zoneTimers[partitionNumber][z]} Closing')
                timer = str.split(z,'|')
                results['zones'].append(int(timer[0]))
                results['zone_update'] = True
                if timer[1] == 'state':
                    self._alarmPanel.alarm_state['zone'][int(timer[0])]['status'].update({'open':False, 'fault': False})
                self._zoneTimers[partitionNumber].pop(z)

        if prior_bypass and not bool(flags.bypass):
            # Partition has switched from bypassed to not bypassed, so clear bypass flags
            # TODO Need to know which bypassed zones are in which partition to handle this. No zone timers for these - either maintain a list or add partition to zone status
            _LOGGER.debug('Clear bypassed zones')

        if bool(flags.not_used2) and bool(flags.not_used3):
            # Keypad update is giving partition status. Battery report applies to system battery
            _LOGGER.debug(f"Keypad update is giving partition {partitionNumber} status. Partition: {partition_status} Zonecode: {zone_code}")
            self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({'bat_trouble': bool(flags.low_battery)})
            
            if (partition_status == 'arming') and (zone_code == 'notready'):
                # Keypad is counting down. Nothing to do
                # TODO Add entry_delay to %00 update handler
                _LOGGER.debug(f"Keypad is counting down to arm partition {partitionNumber}.")

        elif isinstance(user_zone_field, int):
            # Keypad is giving zone status. Update zone status and check zone timers
            _LOGGER.debug(f"Keypad is giving zone status for partition {partitionNumber}.")

            # Increment all existing zone timers by 1
            for z in self._zoneTimers[partitionNumber]:
                    self._zoneTimers[partitionNumber][z] += 1
            
            # Add a zone timer (if needed) of the appropriate type and update zone status
            if zone_code in ['battery','tamper']:
                # Battery or tamper report for a wireless zone. These are added to the keypad update queue separate from state changes, so need their own zone timers.
                self._zoneTimers[partitionNumber][f"{user_zone_field}|{zone_code}"] = 1
            elif zone_code == 'bypass':
                # Bypassed zones only show once in keypad updates and only clear when the partition is disarmed. No zone timer needed.
                self._alarmPanel.alarm_state['zone'][user_zone_field]['bypassed'] = True
                results['bypass'].append(user_zone_field)
                results['bypass_update'] = True
            elif zone_code in ['alarm','alarmcleared','notready']:
                # Zone is open
                # TODO There is a "last_tripped_time" attribute that was previously populated based on zone timer dumps. Does that add enough value to merit reproducing?
                self._alarmPanel.alarm_state['zone'][user_zone_field]['status'].update({'open': True, 'fault': True})
                self._zoneTimers[partitionNumber][f"{user_zone_field}|state"] = 1
                results['zones'].append(user_zone_field)
                results['zone_update'] = True

            # Check and kill any overdue timers
            active_timers = len(self._zoneTimers[partitionNumber])
            #TODO Is this the right margin to add?
            max_timer = round(active_timers * 2 + 2, 0)
            for z in list(self._zoneTimers[partitionNumber]):
                if self._zoneTimers[partitionNumber][z] > max_timer:
                    _LOGGER.debug(f'Timer {z} :: {self._zoneTimers[partitionNumber][z]} Closing')
                    timer = str.split(z,'|')
                    results['zones'].append(int(timer[0]))
                    results['zone_update'] = True
                    if timer[1] == 'state':
                        self._alarmPanel.alarm_state['zone'][int(timer[0])]['status'].update({'open':False, 'fault': False})
                    #else:
                        #TODO Clear tamper/battery status
                    self._zoneTimers[partitionNumber].pop(z)
                else:
                    _LOGGER.debug(f'Timer {z} :: {self._zoneTimers[partitionNumber][z]}')
            _LOGGER.debug(f"There are ({active_timers}) active timers")

        _LOGGER.debug(
            json.dumps(self._alarmPanel.alarm_state["partition"][partitionNumber]["status"])
        )
        return results

    def handle_zone_state_change(self, code, data):
        """Handle when the envisalink sends us a zone change."""
        # Ignore these EVL-generated messages in favor of the raw keypad updates directly from the panel

    def handle_partition_state_change(self, code, data):
        """Handle when the envisalink sends us a partition change."""
        # Ignore these EVL-generated messages in favor of the raw keypad updates directly from the panel
        """
        for currentIndex in range(0, 8):
            partitionStateCode = data[currentIndex * 2 : (currentIndex * 2) + 2]
            partitionState = evl_Partition_Status_Codes[str(partitionStateCode)]
            partitionNumber = currentIndex + 1
            previouslyArmed = self._alarmPanel.alarm_state["partition"][partitionNumber][
                "status"
            ].get("armed", False)
            armed = partitionState["name"] in ("ARMED_STAY", "ARMED_AWAY", "ARMED_MAX")
            self._alarmPanel.alarm_state.update(
                {
                    "arm": not armed,
                    "disarm": armed,
                    "cancel": bool(partitionState["name"] == "EXIT_ENTRY_DELAY"),
                }
            )
            self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                {
                    "exit_delay": bool(
                        partitionState["name"] == "EXIT_ENTRY_DELAY" and not previouslyArmed
                    ),
                    "entry_delay": bool(
                        partitionState["name"] == "EXIT_ENTRY_DELAY" and previouslyArmed
                    ),
                    "armed": armed,
                    "ready": bool(
                        partitionState["name"] == "READY"
                        or partitionState["name"] == "READY_BYPASS"
                    ),
                }
            )

            if partitionState["name"] == "NOT_READY":
                self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                    {"ready": False}
                )
            _LOGGER.debug(
                "Partition " + str(partitionNumber) + " is in state " + partitionState["name"]
            )
            _LOGGER.debug(
                json.dumps(self._alarmPanel.alarm_state["partition"][partitionNumber]["status"])
            )
        """

    def handle_realtime_cid_event(self, code, data):
        """Handle when the envisalink sends us an alarm arm/disarm/trigger."""
        eventTypeInt = int(data[0])
        eventType = evl_CID_Qualifiers[eventTypeInt]
        cidEventInt = int(data[1:4])
        cidEvent = evl_CID_Events[cidEventInt]
        partitionNumber = int(data[4:6])
        zoneOrUser = int(data[6:9])
        if cidEventInt in evl_ArmDisarm_CIDs:
            if eventTypeInt == 1:
                self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                    {"last_disarmed_by_user": zoneOrUser}
                )
            if eventTypeInt == 3:
                self._alarmPanel.alarm_state["partition"][partitionNumber]["status"].update(
                    {"last_armed_by_user": zoneOrUser}
                )

        _LOGGER.debug("Event Type is " + eventType)
        _LOGGER.debug("CID Type is " + cidEvent["type"])
        _LOGGER.debug("CID Description is " + cidEvent["label"])
        _LOGGER.debug("Partition is " + str(partitionNumber))
        _LOGGER.debug(cidEvent["type"] + " value is " + str(zoneOrUser))

        return cidEvent

    def is_zone_open_from_zonedump(self, zone, ticks) -> bool:
        now = time.time()
        last_zone_dump = now - self._alarmPanel.zone_timer_interval
        last_update = self._alarmPanel.alarm_state["zone"][zone]["updated"]

        if last_zone_dump < last_update:
            # This zone has been explicitly updated since the last zone timer dump so honor
            # its current state
            return self._alarmPanel.alarm_state["zone"][zone]["status"]["open"]

        # The envisalink never seems to report back exactly 0 seconds for an open zone.
        # It always seems to be 1-3 ticks.  So 3 ticks or less will be considered open.
        return ticks <= 3
