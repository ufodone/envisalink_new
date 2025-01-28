class AlarmState:
    """Helper class for alarm state functionality."""

    @staticmethod
    def get_initial_alarm_state(maxZones, maxPartitions):
        """Builds the proper alarm state collection."""

        _alarmState = {"partition": {}, "zone": {}}

        for i in range(1, maxPartitions + 1):
            _alarmState["partition"][i] = {
                "status": {
                    "partition_state": "N/A",
                    "alpha": "N/A",
                    "ac_present": True,
                    "beep": False,
                    "armed_bypass": False,
                    "entry_delay": False,
                    "exit_delay": False,
                    "last_armed_by_user": "",
                    "last_disarmed_by_user": "",
                    "ready": False,
                    "bat_trouble": False,
                    "trouble": False,
                    "fire": False,
                    "panic": False,
                    "alarm": False,
                    "alarm_fire_zone": False,
                    "alarm_in_memory": False,
                    "armed_away": False,
                    "armed_stay": False,
                    "armed_zero_entry_delay": False,
                    "armed_night": False,
                    "bell_trouble": False,
                }
            }
        for j in range(1, maxZones + 1):
            _alarmState["zone"][j] = {
                "status": {
                    "open": False,
                    "fault": False,
                    "alarm": False,
                    "tamper": False,
                    "low_battery": False,
                },
                "last_fault": 0,
                "bypassed": False,
                "updated": 0.0,
            }

        return _alarmState
