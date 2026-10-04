"""Regression tests for HoneywellClient._parse_frames buffering across TCP read boundaries.

Without buffering, a frame split across two TCP recv() calls is processed as
two malformed pieces and logged as "Unrecognized data recieved". These tests
feed byte chunks through HoneywellClient._parse_frames and verify each
complete frame reaches the parser exactly once.
"""

import unittest
from unittest.mock import MagicMock

from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.honeywell_client import HoneywellClient


class _TestClient(HoneywellClient):
    """HoneywellClient with the asyncio side of __init__ skipped, plus a
    capture of every line that reaches the parser for assertion."""

    def __init__(self):
        panel = MagicMock()
        panel.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        self._loggedin = True
        self._alarmPanel = panel
        self._shutdown = False
        self._cachedCode = None

class TestFrameParsingHoneywell(unittest.TestCase):
    def setUp(self):
        self.client = _TestClient()

    def test_complete_frame_in_one_chunk(self):
        frames, remainder = self.client._parse_frames("%01,02000004000000000000000000000000$\r\n")
        self.assertEqual(frames, ["%01,02000004000000000000000000000000"])
        self.assertEqual(remainder, "\r\n")

    def test_two_frames_in_one_chunk(self):
        frames, remainder = self.client._parse_frames(
            "%01,02000004000000000000000000000000$\r\n"
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  $\r\n"
        )
        self.assertEqual(frames, [
            "%01,02000004000000000000000000000000",
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  ",
        ])
        self.assertEqual(remainder, "\r\n")

    def test_frame_split_mid_payload(self):
        """The reproducer for the bug: TCP delivers half a frame, then the rest."""
        full = "%00,01,0008,30,00,FAULT 30                        $\r\n"
        first, second = full[:26], full[26:]
        frames, remainder = self.client._parse_frames(first)
        self.assertEqual(frames, [])  # truncated line must not reach the parser
        frames, remainder = self.client._parse_frames(remainder + second)
        self.assertEqual(frames, [
            "%00,01,0008,30,00,FAULT 30                        ",
        ])
        self.assertEqual(remainder, "\r\n")

    def test_frame_split_at_terminator(self): # TODO
        """The CRLF itself is split between two recv() calls."""
        frames, remainder = self.client._parse_frames("%02,01000000$\r")
        self.assertEqual(frames, ["%02,01000000"])
        frames, remainder = self.client._parse_frames(remainder + "\n")
        self.assertEqual(frames, [])
        self.assertEqual(remainder, "\r\n")

    def test_split_inside_middle_frame(self):
        frames, remainder = self.client._parse_frames(
            "%01,02000004000000000000000000000000$\r\n"
            "%00,01,0008,05,00,FAULT"
        )
        self.assertEqual(frames, ["%01,02000004000000000000000000000000"])
        frames, remainder = self.client._parse_frames(remainder + 
            " 05                        $\r\n"
            "%02,03000000$\r\n"
        )
        self.assertEqual(frames, [
            "%00,01,0008,05,00,FAULT 05                        ",
            "%02,03000000",
        ])
        self.assertEqual(remainder, "\r\n")

    def test_empty_chunk_is_a_noop(self):
        frames, remainder = self.client._parse_frames("")
        self.assertEqual(frames, [])
        self.assertEqual(remainder, "")

    def test_login_prompt_is_delivered_when_terminator_arrives(self):
        """Pre-login the EVL sends 'Login:\\r\\n'; buffer must release it."""
        self.client._loggedin = False
        frames, remainder = self.client._parse_frames("Login:")
        self.assertEqual(frames, [])
        frames, remainder = self.client._parse_frames(remainder + "\r\n")
        self.assertEqual(frames, ["Login:"])
        self.assertEqual(remainder, "")

    def test_login_response_with_additional_frame(self):
        """Login success response and an additional frame in the same buffer."""
        self.client._loggedin = False
        frames, remainder = self.client._parse_frames(
            "OK\r\n"
            "%01,02000004000000000000000000000000$\r\n"
            "%02,03000000$\r\n"
        )
        self.assertEqual(frames, [
            "OK",
            "%01,02000004000000000000000000000000",
            "%02,03000000",
        ])
        self.assertEqual(remainder, "\r\n")

    def test_two_frames_in_one_chunk_no_crlf(self):
        frames, remainder = self.client._parse_frames(
            "%01,02000004000000000000000000000000$"
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  $"
        )
        self.assertEqual(frames, [
            "%01,02000004000000000000000000000000",
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  ",
        ])
        self.assertEqual(remainder, "")

    def test_extra_characters_between_frames(self):
        frames, remainder = self.client._parse_frames(
            "%01,02000004000000000000000000000000$"
            "GARBAGE"
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  $"
        )
        self.assertEqual(frames, [
            "%01,02000004000000000000000000000000",
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  ",
        ])
        self.assertEqual(remainder, "")

    def test_percent_sentinel_in_keypad_alpha(self):
        frames, remainder = self.client._parse_frames(
            "%00,01,1C08,08,00,BATTERY % at 100$"
        )
        self.assertEqual(frames, [
            "%00,01,1C08,08,00,BATTERY % at 100",
        ])
        self.assertEqual(remainder, "")

    def test_dollar_sign_sentinel_in_keypad_alpha(self):
        frames, remainder = self.client._parse_frames(
            "%00,01,1C08,08,00,MAKING $ HERE$\r\n"
            "%02,03000000$\r\n"
        )
        self.assertEqual(frames, [
            "%00,01,1C08,08,00,MAKING ",
            " HERE",
            "%02,03000000"
        ])
        self.assertEqual(remainder, "\r\n")

    def test_truncated_frame_glued_to_next_frame(self):
        """The EVL drops the tail (and '$') of the last frame in a burst, so the next
        frame arrives glued onto it. Captured on an EVL4 (fw 01.00.63A) / Vista 20P."""
        frames, remainder = self.client._parse_frames(
            "%01,48020000000000000000000000000000$\r\n"
            "%01,08020000000000000000000000000000$\r\n"
            "%00,01,0008,10,00,FAULT 10" + " " * 23
        )
        self.assertEqual(frames, [
            "%01,48020000000000000000000000000000",
            "%01,08020000000000000000000000000000",
        ])
        with self.assertLogs("pyenvisalink.honeywell_client", level="WARNING") as logs:
            frames, remainder = self.client._parse_frames(
                remainder + "%00,01,0008,04,00,FAULT 04" + " " * 24 + "$\r\n"
            )
        self.assertEqual(frames, ["%00,01,0008,04,00,FAULT 04" + " " * 24])
        self.assertEqual(remainder, "\r\n")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("FAULT 10", logs.output[0])

    def test_truncated_frame_glued_to_command_ack(self):
        """If the glued frame is the keepalive ack, the ack must still be delivered."""
        frames, remainder = self.client._parse_frames("%00,01,000")
        self.assertEqual(frames, [])
        with self.assertLogs("pyenvisalink.honeywell_client", level="WARNING"):
            frames, remainder = self.client._parse_frames(remainder + "^00,00$\r\n")
        self.assertEqual(frames, ["^00,00"])
        self.assertEqual(remainder, "\r\n")

    def test_sentinel_in_alpha_is_not_a_frame_header(self):
        """'%' or '^' in keypad text is only split when followed by two hex digits and a comma."""
        frames, remainder = self.client._parse_frames(
            "%00,01,1C08,08,00,50% ^UP  BATT %ZZ,$\r\n"
        )
        self.assertEqual(frames, ["%00,01,1C08,08,00,50% ^UP  BATT %ZZ,"])
        self.assertEqual(remainder, "\r\n")

if __name__ == "__main__":
    unittest.main()
