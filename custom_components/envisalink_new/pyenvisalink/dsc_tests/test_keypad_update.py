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
evl_verboseTrouble = {
 0 : 'Service is Required',
 1 : 'AC Power Lost',
 2 : 'Telephone Line Fault',
 3 : 'Failure to communicate',
 4 : 'Zone/Sensor Fault', 
 5 : 'Zone/Sensor Tamper',
 6 : 'Zone/Sensor Low Battery',
 7 : 'Loss of time'
}


alarmState = AlarmState.get_initial_alarm_state(64, 8)

def handle_keypad_update(code, data):
    """Handle general- non partition based info"""
    if code == '849':
        bits = "{0:016b}".format(int(data,16))
        trouble_description = ""
        ac_present = True
        print(bits)
        for i in range(0, 7):
            if bits[15-i] == '1':
                trouble_description += evl_verboseTrouble[i] + ', '
                if i == 1:
                    ac_present = False
        new_status = {'alpha':trouble_description.strip(', '), 'ac_present': ac_present}
    else:
        new_status = evl_ResponseTypes[code]['status']

    for part in alarmState['partition']:
        alarmState['partition'][part]['status'].update(new_status)
    _LOGGER.debug(str.format("(All partitions) state has updated: {0}", json.dumps(new_status)))

_LOGGER.info('Alarm State before:')
print(alarmState['partition'])
handle_keypad_update('849','02')
_LOGGER.info('Alarm State after:')
print(alarmState['partition'])
