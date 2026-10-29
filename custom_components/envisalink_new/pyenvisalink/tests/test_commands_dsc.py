"""Tests for the commands DSCClient sends to the Envisalink.

Each test calls a public command method and checks the queue_command call:
(command number, data, code). The code is only used to hide it in logs and to
answer the panel if it asks for one after an arm command.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, call

from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.dsc_client import DSCClient
from pyenvisalink.dsc_envisalinkdefs import evl_Commands


class _TestClient(DSCClient):
    """DSCClient with the asyncio side of __init__ skipped, and the command
    queue and network send replaced with mocks."""

    def __init__(self):
        panel = MagicMock()
        panel.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        panel.password = "secret"
        panel.connection_timeout = 0.01
        self._loggedin = True
        self._alarmPanel = panel
        self._shutdown = False
        self._cachedCode = None
        self._commandQueue = []
        self._loginEvent = MagicMock()
        self._loginEvent.wait = AsyncMock()
        self.queue_command = AsyncMock()
        self.send_data = AsyncMock()
        self.disconnect = AsyncMock()


class TestDscCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = _TestClient()

    def assert_queued(self, *args):
        self.client.queue_command.assert_awaited_once_with(*args)

    # Arm stay / away

    async def test_arm_stay_with_code(self):
        await self.client.arm_stay_partition("1234", 1)
        self.assert_queued(evl_Commands["ArmStay"], "1", "1234")

    async def test_arm_stay_no_code_sends_no_code(self):
        await self.client.arm_stay_partition(None, 1)
        self.assert_queued(evl_Commands["ArmStay"], "1", None)

    async def test_arm_away_with_code(self):
        await self.client.arm_away_partition("1234", 2)
        self.assert_queued(evl_Commands["ArmAway"], "2", "1234")

    async def test_arm_away_no_code_sends_no_code(self):
        await self.client.arm_away_partition(None, 1)
        self.assert_queued(evl_Commands["ArmAway"], "1", None)

    # Arm max, night, disarm

    async def test_arm_max_with_code(self):
        await self.client.arm_max_partition("1234", 1)
        self.assert_queued(evl_Commands["ArmMax"], "1", "1234")

    async def test_arm_night_is_arm_max(self):
        await self.client.arm_night_partition("1234", 1, "7")
        self.assert_queued(evl_Commands["ArmMax"], "1", "1234")

    async def test_arm_night_no_code_sends_no_code(self):
        await self.client.arm_night_partition(None, 1)
        self.assert_queued(evl_Commands["ArmMax"], "1", None)

    async def test_disarm_sends_partition_then_code(self):
        await self.client.disarm_partition("1234", 1)
        self.assert_queued(evl_Commands["Disarm"], "11234", "1234")

    async def test_disarm_no_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.dsc_client", level="ERROR"):
            await self.client.disarm_partition(None, 1)
        self.client.queue_command.assert_not_awaited()

    async def test_disarm_empty_code_sends_nothing(self):
        with self.assertLogs("pyenvisalink.dsc_client", level="ERROR"):
            await self.client.disarm_partition("", 1)
        self.client.queue_command.assert_not_awaited()

    # Panic, bypass, chime, output

    async def test_panic_fire(self):
        await self.client.panic_alarm("Fire")
        self.assert_queued(evl_Commands["Panic"], "1")

    async def test_panic_ambulance(self):
        await self.client.panic_alarm("Ambulance")
        self.assert_queued(evl_Commands["Panic"], "2")

    async def test_panic_police(self):
        await self.client.panic_alarm("Police")
        self.assert_queued(evl_Commands["Panic"], "3")

    async def test_bypass_zone(self):
        await self.client.bypass_zone(5, 1, True)
        self.assert_queued(evl_Commands["PartitionKeypress"], "1*105#")

    async def test_toggle_chime(self):
        await self.client.toggle_chime("1234")
        self.assert_queued(evl_Commands["PartitionKeypress"], "1*4")

    async def test_command_output(self):
        await self.client.command_output("1234", 1, 2)
        self.assert_queued(evl_Commands["CommandOutput"], "12", "1234")

    async def test_dump_zone_bypass_status(self):
        await self.client.dump_zone_bypass_status()
        self.assert_queued(evl_Commands["PartitionKeypress"], "1*1#")

    # Raw keypresses

    async def test_keypresses_to_partition(self):
        await self.client.keypresses_to_partition(2, "*4")
        self.assert_queued(evl_Commands["PartitionKeypress"], "2*4")

    async def test_keypresses_limited_to_6(self):
        await self.client.keypresses_to_partition(1, "1234567")
        self.assert_queued(evl_Commands["PartitionKeypress"], "1123456")

    # Panel asks for a code

    async def test_send_code_sends_cached_code(self):
        self.client._cachedCode = "1234"
        await self.client.send_code()
        self.assert_queued(evl_Commands["SendCode"], "1234")
        self.assertIsNone(self.client._cachedCode)

    async def test_send_code_with_no_cached_code_logs_error(self):
        with self.assertLogs("pyenvisalink.dsc_client", level="ERROR"):
            await self.client.send_code()
        self.client.queue_command.assert_not_awaited()

    def test_log_scrub_with_no_code_leaves_data_alone(self):
        self.assertEqual(self.client.scrub_sensitive_data("0311", None), "0311")

    def test_log_scrub_hides_code(self):
        self.assertEqual(self.client.scrub_sensitive_data("04011234", "1234"), "0401****")

    # Housekeeping and login

    async def test_keep_alive(self):
        await self.client.keep_alive()
        self.assert_queued(evl_Commands["KeepAlive"], "")

    async def test_dump_zone_timers(self):
        await self.client.dump_zone_timers()
        self.assert_queued(evl_Commands["DumpZoneTimers"], "")

    async def test_login_response_sends_password(self):
        await self.client.queue_login_response()
        self.assert_queued(evl_Commands["Login"], "secret")
        self.client.disconnect.assert_not_awaited()

    async def test_login_response_disconnects_if_not_logged_in(self):
        self.client._loggedin = False
        await self.client.queue_login_response()
        self.client.disconnect.assert_awaited_once()

    async def test_complete_login_sets_time_then_requests_status(self):
        await self.client.complete_login()
        first, second = self.client.queue_command.await_args_list
        self.assertEqual(first.args[0], evl_Commands["SetTime"])
        self.assertRegex(first.args[1], r"^\d{10}$")  # HHMMmmddyy
        self.assertEqual(second, call(evl_Commands["StatusReport"], ""))

    # Wire format

    async def test_send_command_appends_checksum(self):
        await self.client.send_command("000", "")
        self.client.send_data.assert_awaited_once_with("00090")

    async def test_send_command_checksum_with_data(self):
        await self.client.send_command("031", "1")
        self.client.send_data.assert_awaited_once_with("0311C5")


if __name__ == "__main__":
    unittest.main()
