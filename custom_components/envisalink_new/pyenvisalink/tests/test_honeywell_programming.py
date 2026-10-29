"""Regression tests for Honeywell keypad state handling."""
import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.const import STATE_CHANGE_PARTITION, STATE_CHANGE_ZONE, STATE_CHANGE_ZONE_BYPASS
from pyenvisalink.envisalink_base_client import EnvisalinkClient
from pyenvisalink.honeywell_client import HoneywellClient


class HoneywellTestCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.panel = SimpleNamespace(alarm_state=AlarmState.get_initial_alarm_state(64, 8))
        self.client = HoneywellClient(self.panel)
        self.zones = self.panel.alarm_state["zone"]

    def tearDown(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    def report(self, flags="0008", zone="02", alpha="FAULT 02 TEST", partition=1):
        return self.client.handle_keypad_update("%00", f"{partition:02},{flags},{zone},00,{alpha}")


# Sanitized display frames representative of a real installer session.
PROGRAMMING_FRAMES = [
    ("0040", "20", "Installer Code                20"),
    ("0C40", "FF", "Field?                          "),
    ("0840", "F5", "Field?                         5"),
    ("0C40", "F5", "Set to Confirm? 0=No,1=Yes     0"),
    ("0040", "01", "Enter Zn Num.   (00=Quit)     01"),
    ("0040", "11", "Enter Zn Num.   (00=Quit)     11"),
    ("0040", "10", "02 Zone Type    Inter. w/dly  10"),
    ("0C40", "10", "02 Partition                   1"),
    ("0040", "10", "02 Report Code  1st 01 2nd 00 10"),
    ("0C40", "10", "02 Hardwire TypeNorm Close     1"),
    ("0C40", "02", "Program Alpha?  0=No,1=Yes     0"),
    ("0040", "EE", "Not Used                      EE"),
    ("0C40", "FF", "Enter * or #                    "),
    ("0840", "F9", "Field?                         9"),
]


class TestHoneywellProgramming(HoneywellTestCase):
    def test_programming_does_not_change_zones_timers_or_bypass(self):
        for zone in ("02", "09", "15"):
            self.report(zone=zone, alpha=f"FAULT {zone} TEST")
        self.report("0018", "06", "BYPAS 06 TEST")
        before = copy.deepcopy(self.zones)
        timers = copy.deepcopy(self.client._zoneTimers)
        for flags, zone, alpha in PROGRAMMING_FRAMES * 3:
            with self.subTest(flags=flags, zone=zone, alpha=alpha):
                result = self.report(flags, zone, alpha)
                self.assertEqual(result, {STATE_CHANGE_PARTITION: [1]})
                self.assertEqual(self.zones, before)
                self.assertEqual(self.client._zoneTimers, timers)
                self.assertTrue(self.panel.alarm_state["partition"][1]["status"]["armed_bypass"])
        self.assertTrue(self.panel.alarm_state["partition"][1]["status"]["programming"])

    def test_exit_resumes_faults_and_ready_closes_known_openings(self):
        self.report(zone="09", alpha="FAULT 09 TEST")
        self.report(*PROGRAMMING_FRAMES[0])
        self.report("1008", "08", "****DISARMED****Ready to Arm")
        self.assertFalse(self.zones[9]["status"]["open"])
        self.assertFalse(self.panel.alarm_state["partition"][1]["status"]["programming"])
        self.report(zone="15", alpha="FAULT 15 TEST")
        self.assertTrue(self.zones[15]["status"]["open"])

    def test_zone_dump_suppressed_until_all_programming_partitions_exit(self):
        self.report(*PROGRAMMING_FRAMES[0])
        self.report(*PROGRAMMING_FRAMES[0], partition=2)
        before = copy.deepcopy(self.zones)
        with patch.object(EnvisalinkClient, "handle_zone_timer_dump", return_value={STATE_CHANGE_ZONE: []}) as handler:
            self.assertEqual(self.client.handle_zone_timer_dump("%03", ""), {})
            handler.assert_not_called()
            self.report("0C08", "08", "****DISARMED****Hit * for faults")
            self.assertEqual(self.client.handle_zone_timer_dump("%03", ""), {})
            handler.assert_not_called()
            self.report("0C08", "08", "****DISARMED****Hit * for faults", partition=2)
            self.assertEqual(self.client.handle_zone_timer_dump("%03", ""), {STATE_CHANGE_ZONE: []})
            handler.assert_called_once()
        self.assertEqual(self.zones, before)

    def test_other_partition_continues_normal_keypad_updates(self):
        self.report(*PROGRAMMING_FRAMES[0])
        self.report(zone="03", alpha="FAULT 03 TEST", partition=2)
        self.assertTrue(self.zones[3]["status"]["open"])
        self.assertIn(1, self.client._programmingPartitions)

    def test_exit_refreshes_timer_budget_without_losing_openings(self):
        self.report()
        self.client._zoneTimers[1]["2|state"] = 50
        self.report(*PROGRAMMING_FRAMES[0])
        self.report("0C08", "08", "****DISARMED****Hit * for faults")
        self.assertEqual(self.client._zoneTimers[1]["2|state"], 1)
        self.assertTrue(self.zones[2]["status"]["open"])

    def test_arming_countdown_still_withholds_armed_state(self):
        self.report("8008", "01", "ARMED STAY May Exit Now")
        status = self.panel.alarm_state["partition"][1]["status"]
        self.assertTrue(status["exit_delay"])
        self.assertFalse(status["armed_stay"])


if __name__ == "__main__":
    unittest.main()
