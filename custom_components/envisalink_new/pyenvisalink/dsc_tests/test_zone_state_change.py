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

def handle_zone_state_change(code, data):
        """Handle when the envisalink sends us a zone change."""
        """Event 601-610."""
        parse = re.match('^[0-9]{3,4}$', data)
        if parse:
            zoneNumber = int(data[-3:])
            alarmState['zone'][zoneNumber]['status'].update(evl_ResponseTypes[code]['status'])
            _LOGGER.debug(str.format("(zone {0}) state has updated: {1}", zoneNumber, json.dumps(evl_ResponseTypes[code]['status'])))
            return zoneNumber
        else:
            _LOGGER.error("Invalid data has been passed in the zone update.")

_LOGGER.info('Alarm State before:')
print(alarmState['zone'])
handle_zone_state_change('609','001')
_LOGGER.info('Alarm State after:')
print(alarmState['zone'])
