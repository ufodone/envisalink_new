import json
import logging
import re
import time

from .const import STATE_CHANGE_PARTITION, STATE_CHANGE_ZONE, STATE_CHANGE_ZONE_BYPASS
from .envisalink_base_client import EnvisalinkClient
from .honeywell_envisalinkdefs import (
    IconLED_Flags,
    evl_ArmDisarm_CIDs,
    evl_CID_Events,
    evl_CID_Qualifiers,
    evl_Commands,
    evl_PanicTypes,
    evl_ResponseTypes,
    evl_TPI_Response_Codes,
    evl_Virtual_Keypad_How_To_Beep,
    evl_Partition_Status_Codes,
)
from .honeywell_client import HoneywellClient

_LOGGER = logging.getLogger(__name__)


class UnoClient(HoneywellClient):
    """Represents an Uno alarm client."""

    def detect(prompt):
        """Given the initial connection data, determine if this is a Uno panel."""
        #TODO
        return prompt == "Login:"

    def handle_keypad_update(self, code, data):
        return None

    def handle_zone_state_change(self, code, data):
        """Handle when the envisalink sends us a zone change."""
        zone_updates = []
        # Envisalink TPI is inconsistent at generating these
        bigEndianHexString = ''
        # every four characters
        inputItems = re.findall('....', data)
        for inputItem in inputItems:
            # Swap the couples of every four bytes
            # (little endian to big endian)
            swapedBytes = []
            swapedBytes.insert(0, inputItem[0:2])
            swapedBytes.insert(0, inputItem[2:4])

            # add swapped set of four bytes to our return items,
            # converting from hex to int
            bigEndianHexString += ''.join(swapedBytes)

        # convert hex string to bitstring
        bitfieldString = str(bin(int(bigEndianHexString, 16))[2:].zfill(self._alarmPanel.max_zones))

        # reverse every 16 bits so "lowest" zone is on the left
        zonefieldString = ''
        inputItems = re.findall('.' * 16, bitfieldString)

        for inputItem in inputItems:
            zonefieldString += inputItem[::-1]

        for zoneNumber, zoneBit in enumerate(zonefieldString, start=1):
            self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update({'open': zoneBit == '1', 'fault': zoneBit == '1'})
            if zoneBit == '1':
                self._alarmPanel.alarm_state['zone'][zoneNumber]['last_fault'] = 0

            _LOGGER.debug("(zone %i) is %s", zoneNumber, "Open/Faulted" if zoneBit == '1' else "Closed/Not Faulted")
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


