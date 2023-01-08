import logging
import json
import re
from pyenvisalink.dsc_envisalinkdefs import *
from pyenvisalink import AlarmState

_LOGGER = logging.getLogger(__name__)

loggingconfig = {'level': 'DEBUG',
                 'format': '%(asctime)s %(levelname)s <%(name)s %(module)s %(funcName)s> %(message)s',
                 'datefmt': '%a, %d %b %Y %H:%M:%S'}

logging.basicConfig(**loggingconfig)


alarmState = AlarmState.get_initial_alarm_state(64, 8)

def handle_partition_state_change(code, data):
        """Handle when the envisalink sends us a partition change."""
        """Event 650-674, 652 is an exception, because 2 bytes are passed for partition and zone type."""
        if code == '652':
            parse = re.match('^[0-9]{2}$', data)
            if parse:
                partitionNumber = int(data[0])
                alarmState['partition'][partitionNumber]['status'].update(evl_ArmModes[data[1]]['status'])
                _LOGGER.debug(str.format("(partition {0}) state has updated: {1}", partitionNumber, json.dumps(evl_ArmModes[data[1]]['status'])))
                return partitionNumber
            else:
                _LOGGER.error("Invalid data has been passed when arming the alarm.")
        else:
            parse = re.match('^[0-9]$', data)
            if parse:
                partitionNumber = int(data[0])
                alarmState['partition'][partitionNumber]['status'].update(evl_ResponseTypes[code]['status'])
                _LOGGER.debug(str.format("(partition {0}) state has updated: {1}", partitionNumber, json.dumps(evl_ResponseTypes[code]['status'])))
                return partitionNumber
            else:
                _LOGGER.error("Invalid data has been passed in the parition update.")

_LOGGER.info('Alarm State before:')
print(alarmState['partition'])
handle_partition_state_change('663','1')
_LOGGER.info('Alarm State after:')
print(alarmState['partition'])
