"""Tests for the commands HoneywellClient sends to the Envisalink.

Each test calls a public command method and checks what gets queued. Most
Honeywell commands are keypresses: one "03" (PartitionKeypress) command per
key, with data "<partition>,<key>" and a log string that hides any code.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.honeywell_client import HoneywellClient
from pyenvisalink.honeywell_envisalinkdefs import evl_Commands

KEYPRESS = evl_Commands["PartitionKeypress"]


class _TestClient(HoneywellClient):
    """HoneywellClient with the asyncio side of __init__ skipped, and the
    command queue and network send replaced with mocks."""

    def __init__(self):
        panel = MagicMock()
        panel.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        panel.password = "secret"
        self._loggedin = True
        self._alarmPanel = panel
        self._shutdown = False
        self._cachedCode = None
        self._commandQueue = []
        self.queue_commands = AsyncMock()
        self.send_data = AsyncMock()


def keys(partition, sent, logged=None):
    """Expected queued commands for a string of keypresses."""
    logged = sent if logged is None else logged
    return [
        {"cmd": KEYPRESS, "data": f"{partition},{s}", "log": f"{partition},{l}"}
        for s, l in zip(sent, logged)
    ]


def command(cmd, data, code=None):
    """Expected queued command for a non-keypress command."""
    return [{"cmd": cmd, "data": data, "code": code}]


class TestHoneywellCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = _TestClient()

    def queued(self):
        """Return the command list passed to the last queue_commands call."""
        return self.client.queue_commands.await_args.args[0]

    # Arm stay

    async def test_arm_stay_with_code(self):
        await self.client.arm_stay_partition("1234", 1)
        self.assertEqual(self.queued(), keys(1, "12343", "****3"))

    async def test_arm_stay_no_code_uses_quick_arm(self):
        await self.client.arm_stay_partition(None, 1)
        self.assertEqual(self.queued(), keys(1, "#3"))

    async def test_arm_stay_empty_code_uses_quick_arm(self):
        await self.client.arm_stay_partition("", 1)
        self.assertEqual(self.queued(), keys(1, "#3"))

    # Arm away

    async def test_arm_away_with_code(self):
        await self.client.arm_away_partition("1234", 2)
        self.assertEqual(self.queued(), keys(2, "12342", "****2"))

    async def test_arm_away_no_code_uses_quick_arm(self):
        await self.client.arm_away_partition(None, 1)
        self.assertEqual(self.queued(), keys(1, "#2"))

    async def test_arm_away_empty_code_uses_quick_arm(self):
        await self.client.arm_away_partition("", 1)
        self.assertEqual(self.queued(), keys(1, "#2"))

    # Arm max, night, disarm

    async def test_arm_max_with_code(self):
        await self.client.arm_max_partition("1234", 1)
        self.assertEqual(self.queued(), keys(1, "12344", "****4"))

    async def test_arm_night_default_mode_is_33(self):
        await self.client.arm_night_partition("1234", 1)
        self.assertEqual(self.queued(), keys(1, "123433", "****33"))

    async def test_arm_night_instant_mode(self):
        await self.client.arm_night_partition("1234", 1, "7")
        self.assertEqual(self.queued(), keys(1, "12347", "****7"))

    async def test_arm_night_no_code_uses_quick_arm(self):
        await self.client.arm_night_partition(None, 1)
        self.assertEqual(self.queued(), keys(1, "#33"))

    async def test_arm_night_instant_no_code_uses_quick_arm(self):
        await self.client.arm_night_partition(None, 1, "7")
        self.assertEqual(self.queued(), keys(1, "#7"))

    async def test_arm_night_empty_code_uses_quick_arm(self):
        await self.client.arm_night_partition("", 1, "33")
        self.assertEqual(self.queued(), keys(1, "#33"))

    async def test_disarm_with_code(self):
        await self.client.disarm_partition("1234", 1)
        self.assertEqual(self.queued(), keys(1, "12341", "****1"))

    async def test_disarm_no_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.honeywell_client", level="ERROR"):
            await self.client.disarm_partition(None, 1)
        self.client.queue_commands.assert_not_awaited()

    async def test_disarm_empty_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.honeywell_client", level="ERROR"):
            await self.client.disarm_partition("", 1)
        self.client.queue_commands.assert_not_awaited()

    # Panic and chime

    async def test_panic_fire(self):
        await self.client.panic_alarm("Fire")
        self.assertEqual(self.queued(), keys(1, "A"))

    async def test_panic_ambulance(self):
        await self.client.panic_alarm("Ambulance")
        self.assertEqual(self.queued(), keys(1, "B"))

    async def test_panic_police(self):
        await self.client.panic_alarm("Police")
        self.assertEqual(self.queued(), keys(1, "C"))

    async def test_toggle_chime_sends_code_and_9_and_masks_log(self):
        await self.client.toggle_chime("1234")
        self.assertEqual(self.queued(), keys(1, "12349", "****9"))

    async def test_toggle_chime_no_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.honeywell_client", level="ERROR"):
            await self.client.toggle_chime(None)
        self.client.queue_commands.assert_not_awaited()

    async def test_toggle_chime_empty_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.honeywell_client", level="ERROR"):
            await self.client.toggle_chime("")
        self.client.queue_commands.assert_not_awaited()

    # Raw keypresses

    async def test_keypresses_to_partition(self):
        await self.client.keypresses_to_partition(3, "*4")
        self.assertEqual(self.queued(), keys(3, "*4"))

    async def test_keypresses_are_queued_together(self):
        """All keys go in one queue_commands call so nothing can land in between."""
        await self.client.arm_stay_partition("1234", 1)
        self.client.queue_commands.assert_awaited_once()

    # Housekeeping commands

    async def test_keep_alive(self):
        await self.client.keep_alive()
        self.assertEqual(self.queued(), command(evl_Commands["KeepAlive"], ""))

    async def test_dump_zone_timers(self):
        await self.client.dump_zone_timers()
        self.assertEqual(self.queued(), command(evl_Commands["DumpZoneTimers"], ""))

    async def test_login_response_sends_password(self):
        await self.client.queue_login_response()
        self.client.send_data.assert_awaited_once_with("secret")

    # Wire format

    async def test_send_command_format(self):
        await self.client.send_command("03", "1,3")
        self.client.send_data.assert_awaited_once_with("^03,1,3$", "^03,1,3$")

    async def test_send_command_uses_log_data_for_log(self):
        await self.client.send_command("03", "1,5", "1,*")
        self.client.send_data.assert_awaited_once_with("^03,1,5$", "^03,1,*$")


if __name__ == "__main__":
    unittest.main()
