#!/usr/bin/env python3
import asyncio
import sys

from pyenvisalink.alarm_panel import EnvisalinkAlarmPanel

# This is a test harness for the pyenvisalink library.
# It will assist in testing the library against both Honeywell and DSC.


async def shutdown_handler(testpanel):
    await testpanel.stop()
    asyncio.get_running_loop().stop()


def async_connection_status_callback(connected):
    print(f"Callback: connection status: {connected}")


def async_login_fail_callback(data):
    print("Callback: login failure")


def async_connection_fail_callback(data):
    print("Callback: connection failure")


def async_connection_success_callback(data):
    print("Callback: login success")


async def main():
    global testpanel
    loop = asyncio.get_running_loop()

    action = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    user = sys.argv[4]
    pw = sys.argv[5]
    httpPort = 8080
    if len(sys.argv) > 6:
        httpPort = int(sys.argv[6])

    testpanel = EnvisalinkAlarmPanel(
        host,
        port,
        user,
        pw,
        zoneTimerInterval=30,
        zoneBypassEnabled=True,
        eventLoop=loop,
        httpPort=httpPort,
        keepAliveInterval=60,
    )

    if action == "discover":
        await testpanel.discover()
        sys.exit(0)

    if action != "start":
        print(f"Unrecognized action: {action}")
        sys.exit(1)

    testpanel.callback_connection_status = async_connection_status_callback
    testpanel.callback_login_failure = async_login_fail_callback
    testpanel.callback_login_timeout = async_connection_fail_callback
    testpanel.callback_login_success = async_connection_success_callback

    result = await testpanel.start()
    if result == EnvisalinkAlarmPanel.ConnectionResult.SUCCESS:
        # await asyncio.sleep(5)
        # loop.create_task(testpanel.arm_stay_partition("12345", 1))
        # loop.create_task(testpanel.arm_away_partition("12345", 1))
        # loop.create_task(testpanel.arm_max_partition("12345", 1))
        # loop.create_task(testpanel.arm_night_partition("12345", 1))
        # loop.create_task(testpanel.disarm_partition("12345", 1))
        await asyncio.sleep(3600)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("You pressed Ctrl+C!")

asyncio.run(shutdown_handler(testpanel))
