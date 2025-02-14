import json
import logging
import re
import time

from .const import STATE_CHANGE_PARTITION, STATE_CHANGE_ZONE, STATE_CHANGE_ZONE_BYPASS
from .honeywell_client import HoneywellClient
from .uno_envisalinkdefs import (
    evl_Commands,
    evl_PanicTypes,
    evl_Partition_Status_Codes,
    evl_ResponseTypes,
    evl_TPI_Response_Codes,
)

_LOGGER = logging.getLogger(__name__)


class UnoClient(HoneywellClient):
    """Represents an Uno alarm client."""
    def __init__(self, panel):
        super().__init__(panel)
        self._evl_ResponseTypes = evl_ResponseTypes
        self._evl_TPI_Response_Codes = evl_TPI_Response_Codes

    def handle_login_success(self, code, data):
        """Handler for when the envisalink accepts our credentials."""
        super().handle_login_success(code, data)

        self.create_internal_task(self.complete_login(), name="complete_login")

    async def complete_login(self):
        await self.queue_command(evl_Commands["HostInfo"], "")
        await self.queue_command(evl_Commands["InitialStateDump"], "")

    def handle_keypad_update(self, code, data):
        return None

    def handle_zone_state_change(self, code, data):
        """Handle when the envisalink sends us a zone change."""
        zone_updates = []
        now = time.time()

        zoneNumber = 0
        num_bytes = len(data)
        idx = 0
        while (idx < num_bytes):
            byte = int(data[idx:idx+2], 16)
            idx += 2
            for bit in range(8):
                faulted = byte & (1 << bit) != 0
                zoneNumber += 1

                self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update({'open': faulted, 'fault': faulted})
                if faulted:
                    self._alarmPanel.alarm_state['zone'][zoneNumber]['last_fault'] = now

                _LOGGER.debug("(zone %i) is %s", zoneNumber, "Open/Faulted" if faulted else "Closed/Not Faulted")
                zone_updates.append(zoneNumber)

        return { STATE_CHANGE_ZONE: zone_updates }

    def handle_partition_state_change(self, code, data):
        """Handle when the envisalink sends us a partition change."""
        partition_updates = []
        for currentIndex in range(0, 8):
            partitionNumber = currentIndex + 1
            partitionStateCode = data[currentIndex * 2:(currentIndex * 2) + 2]
            partitionState = evl_Partition_Status_Codes.get(str(partitionStateCode))
            if not partitionState:
                _LOGGER.warn("Unrecognized partition state code (%s) received for partition %d",
                    str(partitionStateCode), partitionNumber)
                continue

            if not partitionState or partitionState['name'] == 'NOT_USED':
                continue

            previouslyArmed = self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].get('armed', False)
            armed = partitionState['status'].get('armed', False)
            self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update(
                partitionState['status'])

            if partitionState['name'] == 'EXIT_ENTRY_DELAY':
                self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({
                    'exit_delay': not previouslyArmed,
                    'entry_delay': previouslyArmed,
                })

            _LOGGER.debug('Partition ' + str(partitionNumber) + ' is in state ' + partitionState['name'])
            _LOGGER.debug(json.dumps(self._alarmPanel.alarm_state['partition'][partitionNumber]['status']))
            partition_updates.append(partitionNumber)

        return { STATE_CHANGE_PARTITION: partition_updates }

    def handle_zone_bypass_update(self, code, data):
        updates= []
        zoneNumber = 0
        num_bytes = len(data)
        idx = 0
        while (idx < num_bytes):
            byte = int(data[idx:idx+2], 16)
            idx += 2
            for bit in range(8):
                bypassed= byte & (1 << bit) != 0
                zoneNumber += 1

                _LOGGER.debug(
                    str.format(
                        "(zone {0}) bypass state: {1}",
                        zoneNumber,
                        bypassed,
                    )
                )

                if self._alarmPanel.alarm_state['zone'][zoneNumber]['bypassed'] != bypassed:
                    updates.append(zoneNumber)
                    self._alarmPanel.alarm_state['zone'][zoneNumber]['bypassed'] = bypassed
                    updates.append(zoneNumber)


        return { STATE_CHANGE_ZONE_BYPASS: updates}

    def handle_host_information_report(self, code, data):
        """Process Host Information Report"""

        host_info = data.split(',')
        if len(host_info) != 3:
            pass

        mac_address = host_info[0]
        device_type = host_info[1]
        version = host_info[2]
        _LOGGER.debug("Host info: MAC=%s, Device Type=%s, Version='%s'",
            mac_address, device_type, version
        )
        return

    def handle_partition_trouble_state_change(self, code, data):
        """Process Partition Trouble State Change"""
        # TODO
        return

    async def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        await self.queue_command(evl_Commands["StayArm"], str(partitionNumber))

    async def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        await self.queue_command(evl_Commands["AwayArm"], str(partitionNumber))

    async def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        raise NotImplementedError()

    async def arm_night_partition(self, code, partitionNumber, mode=None):
        """Public method to arm/max a partition."""
        raise NotImplementedError()

    async def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        await self.queue_command(evl_Commands["Disarm"], f"{partitionNumber},{code}", code)

    async def panic_alarm(self, panicType):
        """Public method to raise a panic alarm."""
        await self.queue_command(evl_Commands["PanicAlarm"], f"1,{evl_PanicTypes[panicType]}")

    async def bypass_zone(self, zone, partition, enable):
        command = evl_Commands["BypassZone" if enable else "UnbypassZone"]
        await self.queue_command(command, f"{zone:03}")

    async def toggle_chime(self, code):
        """Public method to toggle a zone's bypass state."""
        raise NotImplementedError()

