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


class TestHoneywellBypass(HoneywellTestCase):
    def test_clear_reports_bypass_events_without_closing_open_zone(self):
        self.report()
        result = self.report("0018", "02", "BYPAS 02 TEST")
        self.assertEqual(result[STATE_CHANGE_ZONE_BYPASS], [2])
        self.report("0018", "09", "BYPAS 09 TEST")
        result = self.report()
        self.assertEqual(set(result[STATE_CHANGE_ZONE_BYPASS]), {2, 9})
        self.assertFalse(self.zones[2]["bypassed"])
        self.assertFalse(self.zones[9]["bypassed"])
        self.assertTrue(self.zones[2]["status"]["open"])
        self.assertTrue(self.zones[2]["status"]["fault"])

    def test_other_partition_bypass_is_preserved(self):
        self.report("0018", "02", "BYPAS 02 TEST")
        self.report("0018", "20", "BYPAS 20 TEST", partition=2)
        result = self.report()
        self.assertEqual(result[STATE_CHANGE_ZONE_BYPASS], [2])
        self.assertTrue(self.zones[20]["bypassed"])

    def test_fault_with_bypass_led_does_not_clear_bypasses(self):
        self.report("0018", "02", "BYPAS 02 TEST")
        self.report("0018", "15", "FAULT 15 TEST")
        self.assertTrue(self.zones[2]["bypassed"])

    def test_reconcile_without_prior_led_transition(self):
        self.report("0018", "02", "BYPAS 02 TEST")
        self.panel.alarm_state["partition"][1]["status"]["armed_bypass"] = False
        self.report()
        self.assertFalse(self.zones[2]["bypassed"])
        self.assertNotIn(STATE_CHANGE_ZONE_BYPASS, self.report())

    def test_new_bypass_cycle_does_not_keep_previous_zones(self):
        self.report("0018", "02", "BYPAS 02 TEST")
        self.report()
        self.report("0018", "09", "BYPAS 09 TEST")
        self.assertFalse(self.zones[2]["bypassed"])
        self.assertTrue(self.zones[9]["bypassed"])


if __name__ == "__main__":
    unittest.main()
