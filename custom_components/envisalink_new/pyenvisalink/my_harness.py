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
#ip = "localhost"
ip = "envisalink.home"
port = "4025"
version = "4"
panel = "DSC"
user = "user"
pw = "test"
#pw = "uxWug3Cht4"


loop = asyncio.new_event_loop()

testpanel = EnvisalinkAlarmPanel(ip, int(port), panel, int(version), user, pw, zoneTimerInterval=0, zoneBypassEnabled=True, eventLoop=loop)

result = asyncio.run(testpanel.start())
if result == EnvisalinkAlarmPanel.ConnectionResult.SUCCESS:
    loop.run_forever()

