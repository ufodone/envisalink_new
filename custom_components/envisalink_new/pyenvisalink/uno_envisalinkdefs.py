import ctypes

from .honeywell_envisalinkdefs import (
    evl_ResponseTypes as honeywell_evl_ResponseTypes,
    evl_TPI_Response_Codes as honeywell_evl_TPI_Response_Codes,
)

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
        ("system_bell_fault", c_uint8, 1),
        ("wireless_device_faulted", c_uint8, 1),
    ]

    def __str__(self) -> str:
        b = bytes(self)
        return f"{b[0]:02x}"


class MajorTrouble_Flags(ctypes.Union):
    _fields_ = [("b", MajorTrouble_Bitfield), ("asByte", c_uint8)]
    _anonymous_ = "b"

    def __str__(self) -> str:
        return (
            f"0x{int(self.asByte):02x}"
            f" service_required={self.service_required}"
            f" ac_failure={self.ac_failure}"
            f" wireless_device_low_Battery={self.wireless_device_low_Battery}"
            f" server_offline={self.server_offline}"
            f" zone_trouble={self.zone_trouble}"
            f" system_battery_overcurrent={self.system_battery_overcurrent}"
            f" system_bell_fault={self.system_bell_fault}"
            f" wireless_device_faulted={self.wireless_device_faulted}"
        )

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

evl_ResponseTypes = honeywell_evl_ResponseTypes | {
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
        "state_change": True,
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

evl_TPI_Response_Codes = honeywell_evl_TPI_Response_Codes | {
    "06": {
        "retry": False,
        "msg": "The action command received cannot be completed for some reason (e.g., attempt to arm a partition that is already armed).", # noqa: E501
    },
}

evl_Partition_Status_Codes = {
    "00": {
        "name": "NOT_USED",
        "description": "Partition is not used or doesn" "t exist",
    },
    "01": {
        "name": "READY",
        "description": "Ready",
        "status": {
            "ready": True,
            "alarm": False,
            "armed": False,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Ready",
        },
    },
    "02": {
        "name": "READY_BYPASS",
        "description": "Ready to Arm (Zones are Bypasses)",
        "status": {
            "ready": True,
            "alarm": False,
            "armed": False,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Ready (Bypass)",
        },
    },
    "03": {
        "name": "NOT_READY",
        "description": "Not Ready",
        "status": {
            "ready": False,
            "alarm": False,
            "armed": False,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Not Ready",
        },
    },
    "04": {
        "name": "ARMED_STAY",
        "description": "Armed in Stay Mode",
        "status": {
            "alarm": False,
            "armed": True,
            "armed_stay": True,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Armed Stay",
        },
    },
    "05": {
        "name": "ARMED_AWAY",
        "description": "Armed in Away Mode",
        "status": {
            "alarm": False,
            "armed": True,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": True,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Armed Away",
        },
    },
    "08": {
        "name": "EXIT_DELAY",
        "description": "Alarm in Exit Delay",
        "status": {
            "alarm": False,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": True,
            "entry_delay": False,
            "alpha": "Exit Delay",
        },
    },
    "09": {
        "name": "ARMED_ZERO_ENTRY_DELAY",
        "description": "Armed zero entry delay - away",
        "status": {
            "alarm": False,
            "armed_stay": False,
            "armed_zero_entry_delay": True,
            "armed_away": True,
            "exit_delay": False,
            "entry_delay": False,
            "alpha": "Exit Delay",
        },
    },
    "0C": {
        "name": "ENTRY_DELAY",
        "description": "Alarm in EntryDelay",
        "status": {
            "alarm": False,
            "armed_stay": False,
            "armed_zero_entry_delay": False,
            "armed_away": False,
            "exit_delay": False,
            "entry_delay": True,
            "alpha": "EntryDelay",
        },
    },
    "11": {
        "name": "IN_ALARM",
        "description": "Partition is in Alarm",
        "status": {
            "alarm": True,
            "alpha": "In Alarm",
        },
    },
}
