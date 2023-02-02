#!/usr/bin/env python3
import asyncio
import logging
import signal
import sys
from pyenvisalink import EnvisalinkAlarmPanel

#This is a test harness for the pyenvisalink library.  It will assist in testing the library against both Honeywell and DSC.

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        testpanel.stop()
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#Get Details from the user...
ip = input("Please input the IP address of your envisalink device: ")
port = input("Please input the port of your envisalink device (4025 is default): ")
if len(port) == 0:
    port = "4025"
user = input("Please input your envisalink username: ")
pw = input("Please input your envisalink password: ")

na = input("Config complete. Please press enter now to connect to the envisalink.  When finished, use Ctrl+C to disconnect and exit")

loop = asyncio.new_event_loop()

testpanel = EnvisalinkAlarmPanel(ip, int(port), user, pw, zoneTimerInterval=0, zoneBypassEnabled=True, eventLoop=loop)

result = asyncio.run(testpanel.start())
if result == EnvisalinkAlarmPanel.ConnectionResult.SUCCESS:
    loop.run_forever()

