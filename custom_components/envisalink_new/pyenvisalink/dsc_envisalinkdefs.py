## Alarm Server
## Supporting Envisalink 2DS/3
##
## This code is under the terms of the GPL v3 license.

evl_Commands = {
    'KeepAlive' : '000',
    'StatusReport' : '001',
    'DumpZoneTimers' : '008',
    'PartitionKeypress' : '071',
    'Disarm' : '040',
    'ArmStay' : '031',
    'ArmAway' : '030',
    'ArmMax' : '032',
    'Login' : '005',
    'Panic' : '060',
    'SendCode' : '200',
    'CommandOutput' : '020',
    'SetTime' : '010'
}

evl_PanicTypes = {
    'Fire' : '1',
    'Ambulance' : '2',
    'Police' : '3'
}

evl_ArmModes = {
        '0' : {'name' : 'Arm Away', 'status':{'armed_away': True, 'armed_zero_entry_delay': False, 'alpha':'Arm Away', 'exit_delay':False, 'entry_delay': False }},
        '1' : {'name' : 'Arm Stay', 'status':{'armed_stay': True, 'armed_zero_entry_delay': False, 'alpha':'Arm Stay', 'exit_delay':False, 'entry_delay': False }},
        '2' : {'name' : 'Arm Zero Entry Away', 'status':{'armed_away': True, 'armed_zero_entry_delay': True, 'alpha':'Arm Zero Entry Away', 'exit_delay':False, 'entry_delay': False }},
        '3' : {'name' : 'Arm Zero Entry Stay', 'status':{'armed_stay': True, 'armed_zero_entry_delay': True, 'alpha':'Arm Zero Entry Stay', 'exit_delay':False, 'entry_delay': False }}
    }

evl_ResponseTypes = {
    '505' : {'name':'Login Prompt', 'handler':'login'},
    '615' : {'name':'Envisalink Zone Timer Dump', 'handler':'zone_timer_dump'},
    '500' : {'name':'Command Acknowledge', 'handler':'command_response'},
    '501' : {'name':'Command Error', 'handler':'command_response'},
    '502' : {'name':'System Error', 'handler':'command_response'},
    '900' : {'name':'EnterCode', 'handler':'send_code'},
    '912' : {'name':'PGMEnterCode', 'handler':'send_code'},

#ZONE UPDATES

    '601' : {'name':'Zone Alarm', 'handler':'zone_state_change', 'status':{'alarm' : True}},
    '602' : {'name':'Zone Alarm Restore', 'handler':'zone_state_change', 'status':{'alarm' : False}},
    '603' : {'name':'Zone Tamper', 'handler':'zone_state_change', 'status':{'tamper' : True}},
    '604' : {'name':'Zone Tamper Restore', 'handler':'zone_state_change', 'status':{'tamper' : False}},
    '605' : {'name':'Zone Fault', 'handler':'zone_state_change', 'status':{'fault' : True}},
    '606' : {'name':'Zone Fault Restore', 'handler':'zone_state_change', 'status':{'fault' : False}},
    '609' : {'name':'Zone Open', 'handler':'zone_state_change', 'status':{'open' : True}},
    '610' : {'name':'Zone Restored', 'handler':'zone_state_change', 'status':{'open' : False}},

#PARTITION UPDATES
    '650' : {'name':'Ready', 'handler':'partition_state_change', 'status':{'ready' : True, 'alpha' : 'Ready'}},
    '651' : {'name':'Not Ready', 'handler':'partition_state_change', 'status':{'ready' : False, 'alpha' : 'Not Ready'}},
    '652' : {'name':'Armed', 'handler':'partition_state_change'},
    '653' : {'name':'Ready - Force Arming Enabled', 'handler':'partition_state_change', 'status':{'ready': True, 'alpha' : 'Ready - Force Arm'}},
    '654' : {'name':'Alarm', 'handler':'partition_state_change', 'status':{'alarm' : True, 'alpha' : 'Alarm'}},
    '655' : {'name':'Disarmed', 'handler':'partition_state_change', 'status' : {'alarm' : False, 'armed_stay' : False, 'armed_zero_entry_delay': False, 'armed_away' : False, 'exit_delay' : False, 'entry_delay' : False, 'alpha' : 'Disarmed'}},
    '656' : {'name':'Exit Delay in Progress', 'handler':'partition_state_change', 'status':{'exit_delay' : True, 'alpha' : 'Exit Delay In Progress'}},
    '657' : {'name':'Entry Delay in Progress', 'handler':'partition_state_change', 'status':{'entry_delay' : True, 'alpha' : 'Entry Delay in Progress'}},
    '663' : {'name':'ChimeOn', 'handler':'partition_state_change', 'status': {'chime': True}},
    '664' : {'name':'ChimeOff', 'handler':'partition_state_change', 'status': {'chime': False}},
    '673' : {'name':'Busy', 'handler':'partition_state_change', 'status': {'alpha': 'Busy'}},
    '700' : {'name':'Armed by user', 'handler':'partition_state_change', 'status':{}},
    '750' : {'name':'Disarmed by user', 'handler':'partition_state_change', 'status' : {'alarm' : False, 'armed_stay' : False, 'armed_away' : False, 'armed_zero_entry_delay': False, 'exit_delay' : False, 'entry_delay' : False, 'alpha' : 'Disarmed'}},
    '751' : {'name':'Disarmed special', 'handler':'partition_state_change', 'status' : {'alarm' : False, 'armed_stay' : False, 'armed_away' : False, 'armed_zero_entry_delay': False, 'exit_delay' : False, 'entry_delay' : False, 'alpha' : 'Disarmed'}},
    '840' : {'name':'Trouble LED', 'handler':'partition_state_change', 'status':{'trouble' : True}},
    '841' : {'name':'Trouble Clear', 'handler':'partition_state_change', 'status':{'trouble' : False, 'ac_present': True}},

#GENERAL UPDATES
    '621' : {'name':'FireAlarmButton', 'handler':'keypad_update', 'status':{'fire' : True, 'alarm': True, 'alpha' : 'Fire Alarm'}},
    '622' : {'name':'FireAlarmButtonOff', 'handler':'keypad_update', 'status':{'fire' : False, 'alarm': False, 'alpha' : 'Fire Alarm Cleared'}},
    '623' : {'name':'AuxAlarmButton', 'handler':'keypad_update', 'status':{'alarm': True, 'alpha' : 'Aux Alarm'}},
    '624' : {'name':'AuxAlarmButtonOff', 'handler':'keypad_update', 'status':{'alarm': False, 'alpha' : 'Aux Alarm Cleared'}},
    '625' : {'name':'PanicAlarmButton', 'handler':'keypad_update', 'status':{'alarm': True, 'alpha' : 'Panic Alarm'}},
    '626' : {'name':'PanicAlarmButtonOff', 'handler':'keypad_update', 'status':{'alarm': False, 'alpha' : 'Panic Alarm Cleared'}},
    '631' : {'name':'SmokeAlarmButton', 'handler':'keypad_update', 'status':{'alarm': True, 'alpha' : 'Smoke Alarm'}},
    '632' : {'name':'SmokeAlarmButtonOff', 'handler':'keypad_update', 'status':{'alarm': False, 'alpha' : 'Smoke Alarm Cleared'}},
    '660' : {'name':'PGMrelay', 'handler':'keypad_update', 'status':{'PGMrelay': True, 'alpha' : 'PGM output active'}},
    '800' : {'name':'LowBatTrouble', 'handler':'keypad_update', 'status':{'bat_trouble': True, 'alpha' : 'Low Battery'}},
    '801' : {'name':'LowBatTroubleOff', 'handler':'keypad_update', 'status':{'bat_trouble': False, 'alpha' : 'Low Battery Cleared'}},
    '802' : {'name':'ACTrouble', 'handler':'keypad_update', 'status':{'ac_present': False, 'alpha' : 'AC Power Lost'}},
    '803' : {'name':'ACTroubleOff', 'handler':'keypad_update', 'status':{'ac_present': True, 'alpha' : 'AC Power Restored'}},
    '829' : {'name':'SystemTamper', 'handler':'keypad_update', 'status':{'alpha' : 'System tamper'}},
    '830' : {'name':'SystemTamperOff', 'handler':'keypad_update', 'status':{'alpha' : 'System tamper Restored'}},
    '849' : {'name':'TroubleVerbose', 'handler':'keypad_update', 'status':None},

#ZONE BYPASS UPDATES
    '616' : {'name':'Zone Bypass', 'handler':'zone_bypass_update', 'status':None}
}

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

evl_TPI_Response_Codes = {
    '000' : { 'retry' : False, 'msg': 'No Error' },
    '001' : { 'retry' : True, 'msg': 'Receive Buffer Overrun (a command is received while another is still being processed)' },
    '002' : { 'retry' : True, 'msg': 'Receive Buffer Overflow' },
    '003' : { 'retry' : False, 'msg': 'Transmit Buffer Overflow' },

    '010' : { 'retry' : True, 'msg': 'Keybus Transmit Buffer Overrun' },
    '011' : { 'retry' : False, 'msg': 'Keybus Transmit Time Timeout' },
    '012' : { 'retry' : False, 'msg': 'Keybus Transmit Mode Timeout' },
    '013' : { 'retry' : False, 'msg': 'Keybus Transmit Keystring Timeout' },
    '014' : { 'retry' : False, 'msg': 'Keybus Interface Not Functioning (the TPI cannot communicate with the security system)' },
    '015' : { 'retry' : False, 'msg': 'Keybus Busy (Attempting to Disarm or Arm with user code)' },
    '016' : { 'retry' : False, 'msg': 'Keybus Busy – Lockout (The panel is currently in Keypad Lockout – too many disarm attempts)' },
    '017' : { 'retry' : False, 'msg': 'Keybus Busy – Installers Mode (Panel is in installers mode, most functions are unavailable)' },
    '018' : { 'retry' : False, 'msg': 'Keybus Busy – General Busy (The requested partition is busy)' },

    '020' : { 'retry' : False, 'msg': 'API Command Syntax Error' },
    '021' : { 'retry' : False, 'msg': 'API Command Partition Error (Requested Partition is out of bounds)' },
    '022' : { 'retry' : False, 'msg': 'API Command Not Supported' },
    '023' : { 'retry' : False, 'msg': 'API SystemNotArmed (sent in response to a disarm command)' },
    '024' : { 'retry' : False, 'msg': 'API System Not Ready to Arm (system is either not-secure, in exit-delay, or already armed)' },
    '025' : { 'retry' : False, 'msg': 'API Command Invalid Length' },
    '026' : { 'retry' : False, 'msg': 'API User Code not Required' },
    '027' : { 'retry' : False, 'msg': 'API Invalid Characters in Command (no alpha characters are allowed except for checksum)' },
}
