import ctypes

c_uint8 = ctypes.c_uint8
c_uint16 = ctypes.c_uint16


class MajorTrouble_Bitfield(ctypes.LittleEndianStructure):
    _fields_ = [
        ("service_required", c_uint8, 1),
        ("ac_failure", c_uint8, 1),
        ("wireless_device_low_Battery", c_uint8, 1),
        ("server_offline", c_uint8, 1),
        ("zone_trouble", c_uint8, 1),
        ("system_battery_overcurrent", c_uint8, 1),
        ("system_Bell_fault", c_uint8, 1),
        ("wireless_device_fauled", c_uint8, 1),
    ]

    def __str__(self) -> str:
        b = bytes(self)
        return f"{b[0]:02x}"


class MajorTrouble_Flags(ctypes.Union):
    _fields_ = [("b", MajorTrouble_Bitfield), ("asByte", c_uint8)]
    _anonymous_ = "b"


evl_Commands = {
    "BypassZone": "04",
    "UnbypassZone": "05",
    "StayArm": "08",
    "AwayArm": "09",
    "InitialStateDump": "0C",
    "HostInfo": "0D",
    "PanicAlarm": "11",
    "Disarm": "12",
}

evl_PanicTypes = {"Fire": "0", "Ambulance": "1", "Police": "2"}

evl_ResponseTypes = {
    "%04": {
        "name": "Zone Bypass State Change",
        "description": "The panel wants to update the bypass state of a zone",
        "handler": "zone_bypass_update",
        "state_change": True,
    },
    "%05": {
        "name": "Host Information Report",
        "description": "Reports host MAC address, device type, and firmware version",
        "handler": "host_information_report",
        "state_change": False,
    },
    "%06": {
        "name": "Partition Trouble State Change",
        "description": "The trouble state for a partition has changed",
        "handler": "partition_trouble_state_change",
        "state_change": False,
    },

    "^04": {
        "type": "envisalink",
        "name": "BypassZone",
        "description": "Bypass a zone",
        "handler": "command_response",
    },
    "^05": {
        "type": "envisalink",
        "name": "UnbypassZone",
        "description": "Unbypass a zone",
        "handler": "command_response",
    },
    "^08": {
        "type": "envisalink",
        "name": "StayArm",
        "description": "Arm the panel in stay mode",
        "handler": "command_response",
    },
    "^09": {
        "type": "envisalink",
        "name": "AwayArm",
        "description": "Arm the panel in awaymode",
        "handler": "command_response",
    },
    "^0C": {
        "type": "envisalink",
        "name": "InitialStateDump",
        "description": "Initial State Dump",
        "handler": "command_response",
    },
    "^0D": {
        "type": "envisalink",
        "name": "HostInfo",
        "description": "Host Info Dump",
        "handler": "command_response",
    },
    "^11": {
        "type": "envisalink",
        "name": "PanicAlarm",
        "description": "Trigger a panel alarm",
        "handler": "command_response",
    },
    "^12": {
        "type": "envisalink",
        "name": "Disarm",
        "description": "Disarm the partition",
        "handler": "command_response",
    },
}
