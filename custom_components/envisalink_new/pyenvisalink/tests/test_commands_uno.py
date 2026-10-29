"""Tests for the commands UnoClient sends to the Envisalink.

The Uno has its own commands for arming, disarming, panic and bypass, and
inherits keypresses and housekeeping commands from HoneywellClient. Arming
never needs a code; disarm sends it.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.honeywell_envisalinkdefs import evl_Commands as honeywell_Commands
from pyenvisalink.uno_client import UnoClient
from pyenvisalink.uno_envisalinkdefs import evl_Commands


class _TestClient(UnoClient):
    """UnoClient with the asyncio side of __init__ skipped, and the command
    queue replaced with a mock."""

    def __init__(self):
        panel = MagicMock()
        panel.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        self._loggedin = True
        self._alarmPanel = panel
        self._shutdown = False
        self._cachedCode = None
        self._commandQueue = []
        self.queue_commands = AsyncMock()


def command(cmd, data, code=None):
    """Expected queued command list for a single command."""
    return [{"cmd": cmd, "data": data, "code": code}]


class TestUnoCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = _TestClient()

    def queued(self):
        """Return the command list passed to the last queue_commands call."""
        return self.client.queue_commands.await_args.args[0]

    # Arm stay / away: code is ignored

    async def test_arm_stay_with_code(self):
        await self.client.arm_stay_partition("1234", 1)
        self.assertEqual(self.queued(), command(evl_Commands["StayArm"], "1"))

    async def test_arm_stay_no_code(self):
        await self.client.arm_stay_partition(None, 1)
        self.assertEqual(self.queued(), command(evl_Commands["StayArm"], "1"))

    async def test_arm_away_with_code(self):
        await self.client.arm_away_partition("1234", 2)
        self.assertEqual(self.queued(), command(evl_Commands["AwayArm"], "2"))

    async def test_arm_away_no_code(self):
        await self.client.arm_away_partition(None, 1)
        self.assertEqual(self.queued(), command(evl_Commands["AwayArm"], "1"))

    # Not supported on Uno

    async def test_arm_max_not_supported(self):
        with self.assertRaises(NotImplementedError):
            await self.client.arm_max_partition("1234", 1)

    async def test_arm_night_not_supported(self):
        with self.assertRaises(NotImplementedError):
            await self.client.arm_night_partition("1234", 1)

    async def test_toggle_chime_not_supported(self):
        with self.assertRaises(NotImplementedError):
            await self.client.toggle_chime("1234")

    # Disarm, panic, bypass

    async def test_disarm_sends_partition_and_code(self):
        await self.client.disarm_partition("1234", 1)
        self.assertEqual(self.queued(), command(evl_Commands["Disarm"], "1,1234", "1234"))

    async def test_disarm_no_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.uno_client", level="ERROR"):
            await self.client.disarm_partition(None, 1)
        self.client.queue_commands.assert_not_awaited()

    async def test_disarm_empty_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.uno_client", level="ERROR"):
            await self.client.disarm_partition("", 1)
        self.client.queue_commands.assert_not_awaited()

    async def test_panic_fire(self):
        await self.client.panic_alarm("Fire")
        self.assertEqual(self.queued(), command(evl_Commands["PanicAlarm"], "1,0"))

    async def test_panic_ambulance(self):
        await self.client.panic_alarm("Ambulance")
        self.assertEqual(self.queued(), command(evl_Commands["PanicAlarm"], "1,1"))

    async def test_panic_police(self):
        await self.client.panic_alarm("Police")
        self.assertEqual(self.queued(), command(evl_Commands["PanicAlarm"], "1,2"))

    async def test_bypass_zone(self):
        await self.client.bypass_zone(5, 1, True)
        self.assertEqual(self.queued(), command(evl_Commands["BypassZone"], "005"))

    async def test_unbypass_zone(self):
        await self.client.bypass_zone(5, 1, False)
        self.assertEqual(self.queued(), command(evl_Commands["UnbypassZone"], "005"))

    # Login

    async def test_complete_login_requests_host_info_then_state_dump(self):
        await self.client.complete_login()
        first, second = [c.args[0] for c in self.client.queue_commands.await_args_list]
        self.assertEqual(first, command(evl_Commands["HostInfo"], ""))
        self.assertEqual(second, command(evl_Commands["InitialStateDump"], ""))

    # Inherited from HoneywellClient

    async def test_keypresses_to_partition(self):
        await self.client.keypresses_to_partition(1, "*4")
        self.assertEqual(
            self.queued(),
            [
                {"cmd": honeywell_Commands["PartitionKeypress"], "data": "1,*", "log": "1,*"},
                {"cmd": honeywell_Commands["PartitionKeypress"], "data": "1,4", "log": "1,4"},
            ],
        )

    async def test_keep_alive(self):
        await self.client.keep_alive()
        self.assertEqual(self.queued(), command(honeywell_Commands["KeepAlive"], ""))


if __name__ == "__main__":
    unittest.main()
