import asyncio
import async_timeout
import threading
import time
import logging
import re
import aiohttp
from enum import Enum
from .alarm_state import AlarmState

_LOGGER = logging.getLogger(__name__)

class EnvisalinkClient(asyncio.Protocol):
    """Abstract base class for the envisalink TPI client."""

    class Operation:
        class State(Enum):
            QUEUED = "queued"
            SENT = "sent"
            SUCCEEDED = "succeeded"
            RETRY = "retry"
            FAILED = "failed"

        def __init__(self, cmd, data, code, logData):
            self.cmd = cmd
            self.data = data
            self.code = code
            self.logData = logData
            self.state = self.State.QUEUED
            self.retryDelay = 0.1 # Start the retry backoff at 100ms
            self.retryTime = 0
            self.expiryTime = 0
            self.responseEvent = asyncio.Event()


    def __init__(self, panel, loop):
        self._loggedin = False
        self._alarmPanel = panel
        if loop is None:
            _LOGGER.info("Creating our own event loop.")
            self._eventLoop = asyncio.new_event_loop()
            self._ownLoop = True
        else:
            _LOGGER.info("Latching onto an existing event loop.")
            self._eventLoop = loop
            self._ownLoop = False

        self._reader = None
        self._writer = None
        self._shutdown = False
        self._cachedCode = None
        self._commandTask = None
        self._readLoopTask = None
        self._keepAliveTask = None
        self._commandEvent = asyncio.Event()
        self._commandQueue = []
        self._activeTasks = set()

    def create_internal_task(self, coro, name=None):
        task = self._eventLoop.create_task(coro, name=name)
        task.add_done_callback(self.complete_internal_task)
        self._activeTasks.add(task)

    def complete_internal_task(self, task):
        self._activeTasks.remove(task)

    def start(self):
        """Public method for initiating connectivity with the envisalink."""
        self._shutdown = False
        self._commandTask = self.create_internal_task(self.process_command_queue(), name="command_processor")
        self._readLoopTask = self.create_internal_task(self.read_loop(), name="read_loop")

        if self._alarmPanel.keepalive_interval > 0:
            self.create_internal_task(
                self.periodic_command(self.keep_alive, self._alarmPanel.keepalive_interval),
                name="keep_alive"
            )

        if self._alarmPanel.zone_timer_interval > 0:
            self.create_internal_task(
                self.periodic_command(self.dump_zone_timers, self._alarmPanel.zone_timer_interval),
                name="zone_timer_dump"
            )

        if self._ownLoop:
            _LOGGER.info("Starting up our own event loop.")
            self._eventLoop.run_forever()
            self._eventLoop.close()
            _LOGGER.info("Connection shut down.")

    async def stop(self):
        """Public method for shutting down connectivity with the envisalink."""
        self._loggedin = False
        self._shutdown = True

        # Wake up the command processor task to allow it to exit
        self._commandEvent.set()
        
        # Cancel all tasks
        for t in self._activeTasks:
            t.cancel()

        await self.disconnect()

        if self._ownLoop:
            _LOGGER.info("Shutting down Envisalink client connection...")
            self._eventLoop.call_soon_threadsafe(self._eventLoop.stop)
        else:
            _LOGGER.info("An event loop was given to us- we will shutdown when that event loop shuts down.")

    async def read_loop(self):
        """Internal method handling connecting to the EVL and consuming data from it."""
        while not self._shutdown:
            self._reader = None
            self._writer = None

            _LOGGER.debug("Starting read loop.")

            await self.connect()

            if self._reader and self._writer:
                # Connected to EVL; start reading data from the connection
                try:
                    unprocessed_data = None
                    while not self._shutdown and self._reader:
                        _LOGGER.debug("Waiting for data from EVL")
                        try:
                            data = await asyncio.wait_for(self._reader.read(n=1024), 5)
                        except asyncio.exceptions.TimeoutError:
                            continue

                        if not data or len(data) == 0 or self._reader.at_eof():
                            _LOGGER.error('The server closed the connection.')
                            await self.disconnect()
                            break

                        data = data.decode('ascii')
                        _LOGGER.debug('{---------------------------------------')
                        _LOGGER.debug(str.format('RX < {0}', data))

                        if unprocessed_data:
                            data = unprocessed_data + data

                        unprocessed_data = self.process_data(data)
                        _LOGGER.debug('}---------------------------------------')
                except Exception as ex:
                    _LOGGER.error("Caught unexpected exception: %r", ex)
                    await self.disconnect()

            # Lost connection so reattempt connection in a bit
            if not self._shutdown:
                reconnect_time = 30
                _LOGGER.error("Reconnection attempt in %ds", reconnect_time)
                await asyncio.sleep(reconnect_time)

        await self.disconnect()

    async def periodic_command(self, action, interval):
        """Used to periodically send a keepalive command to reset the envisalink's watchdog timer."""
        while not self._shutdown:
            next_send = time.time() + interval

            if self._loggedin:
                await action()

            now = time.time();
            await asyncio.sleep(next_send - now)
            
    async def connect(self):
        _LOGGER.info(str.format("Started to connect to Envisalink... at {0}:{1}", self._alarmPanel.host, self._alarmPanel.port))
        try:
            coro = asyncio.open_connection(self._alarmPanel.host, self._alarmPanel.port)
            self._reader, self._writer = await asyncio.wait_for(coro, self._alarmPanel.connection_timeout)
            _LOGGER.info("Connection Successful!")
        except Exception as ex:
            self._loggedin = False
            if not self._shutdown:
                _LOGGER.error('Unable to connect to envisalink: %r', ex)
                self._alarmPanel._loginTimeoutCallback(False)
            await self.disconnect()

    async def disconnect(self):
        """Internal method for forcing connection closure if hung."""
        _LOGGER.debug('Cleaning up from disconnection with server.')

        self._loggedin = False

        # Fail all outstanding commands
        for op in self._commandQueue:
            op.state = self.Operation.State.FAILED

        # Tear down the connection
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as ex:
                _LOGGER.error("Exception while closing connection: %s", ex)

        self._writer = None
        self._reader = None
            
    async def send_data(self, data, logData = None):
        """Raw data send- just make sure it's encoded properly and logged."""
        # Scrub the password and alarm code if necessary
        if not logData:
            logData = self.scrub_sensitive_data(data)
        _LOGGER.debug('TX > %s', logData.encode('ascii'))

        try:
            self._writer.write((data + '\r\n').encode('ascii'))
            await self._writer.drain()
        except Exception as err:
            _LOGGER.error('Failed to write to the stream: %r', err)
            await self.disconnect()

    async def send_command(self, code, data, logData = None):
        """Used to send a properly formatted command to the envisalink"""
        raise NotImplementedError()

    async def dump_zone_timers(self):
        """Public method for dumping zone timers."""
        raise NotImplementedError()

    async def keep_alive(self):
        """Send a keepalive command to reset it's watchdog timer."""
        raise NotImplementedError()

    async def change_partition(self, partitionNumber):
        """Public method for changing the default partition."""
        raise NotImplementedError()

    async def keypresses_to_default_partition(self, keypresses):
        """Public method for sending a key to a particular partition."""
        self.send_data(keypresses)

    async def keypresses_to_partition(self, partitionNumber, keypresses):
        """Public method to send a key to the default partition."""
        raise NotImplementedError()

    async def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        raise NotImplementedError()

    async def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        raise NotImplementedError()

    async def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        raise NotImplementedError()

    async def arm_night_partition(self, code, partitionNumber, mode=None):
        """Public method to arm/max a partition."""
        raise NotImplementedError()

    async def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        raise NotImplementedError()

    async def panic_alarm(self, panicType):
        """Public method to trigger the panic alarm."""
        raise NotImplementedError()

    async def toggle_zone_bypass(self, zone):
        """Public method to toggle a zone's bypass state."""
        raise NotImplementedError()

    async def command_output(self, code, partitionNumber, outputNumber):
        """Public method to activate the selected command output"""
        raise NotImplementedError()

    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        raise NotImplementedError()
        
    def process_data(self, data) -> str:
        while data is not None and len(data) > 0:
            cmd, data = self.parseHandler(data)

            if not cmd:
                break

            try:
                _LOGGER.debug(str.format('calling handler: {0} for code: {1} with data: {2}', cmd['handler'], cmd['code'], cmd['data']))
                handlerFunc = getattr(self, cmd['handler'])
                result = handlerFunc(cmd['code'], cmd['data'])

            except (AttributeError, TypeError, KeyError) as err:
                _LOGGER.debug("No handler configured for evl command.")
                _LOGGER.debug(str.format("KeyError: {0}", err))

            try:
                _LOGGER.debug(str.format('Invoking callback: {0}', cmd['callback']))
                callbackFunc = getattr(self._alarmPanel, cmd['callback'])
                callbackFunc(result)

            except (AttributeError, TypeError, KeyError) as err:
                _LOGGER.debug("No callback configured for evl command.")

        # Return any unprocessed data (uncomplete command)
        if not data or len(data) == 0:
            return None
        return data

    def convertZoneDump(self, theString):
        """Interpret the zone dump result, and convert to readable times."""
        returnItems = []
        zoneNumber = 1
        # every four characters
        inputItems = re.findall('....', theString)
        for inputItem in inputItems:
            # Swap the couples of every four bytes (little endian to big endian)
            swapedBytes = []
            swapedBytes.insert(0, inputItem[0:2])
            swapedBytes.insert(0, inputItem[2:4])

            # add swapped set of four bytes to our return items, converting from hex to int
            itemHexString = ''.join(swapedBytes)
            itemInt = int(itemHexString, 16)

            # each value is a timer for a zone that ticks down every five seconds from maxint
            MAXINT = 0xffff
            itemTicks = MAXINT - itemInt
            itemSeconds = itemTicks * 5

            status = ''
            if self.is_zone_open_from_zonedump(zoneNumber, itemTicks):
                status = 'open'
            else:
                status = 'closed'

            returnItems.append({'zone': zoneNumber, 'status': status, 'seconds': itemSeconds})
            zoneNumber += 1
        return returnItems
            
    def handle_login(self, code, data):
        """Handler for when the envisalink challenges for password."""
        raise NotImplementedError()

    def handle_login_success(self, code, data):
        """Handler for when the envisalink accepts our credentials."""
        self._loggedin = True
        _LOGGER.debug('Password accepted, session created')

    def handle_login_failure(self, code, data):
        """Handler for when the envisalink rejects our credentials."""
        self._loggedin = False
        _LOGGER.error('Password is incorrect. Server is closing socket connection.')

    def handle_keypad_update(self, code, data):
        """Handler for when the envisalink wishes to send us a keypad update."""
        raise NotImplementedError()
        
    def handle_command_response(self, code, data):
        """When we send any command- this will be called to parse the initial response."""
        raise NotImplementedError()

    def handle_zone_state_change(self, code, data):
        """Callback for whenever the envisalink reports a zone change."""
        raise NotImplementedError()

    def handle_partition_state_change(self, code, data):
        """Callback for whenever the envisalink reports a partition change."""
        raise NotImplementedError()

    def handle_realtime_cid_event(self, code, data):
        """Callback for whenever the envisalink triggers alarm arm/disarm/trigger."""
        raise NotImplementedError()

    def is_zone_open_from_zonedump(self, zone, ticks) -> bool:
        """Indicate whether or not a zone should be considered open based on the number of
           ticks in a zone dump timer update"""
        raise NotImplementedError()

    def handle_zone_timer_dump(self, code, data):
        """Handle the zone timer data."""
        results = []
        zoneInfoArray = self.convertZoneDump(data)
        for zoneNumber, zoneInfo in enumerate(zoneInfoArray, start=1):
            currentStatus = self._alarmPanel.alarm_state['zone'][zoneNumber]['status']
            newOpen = zoneInfo['status'] == 'open'
            newFault = zoneInfo['status'] == 'open'
            if newOpen != currentStatus['open'] or newFault != currentStatus['fault']:
                # State changed so add to result list
                results.append(zoneNumber)

            self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update({'open': newOpen, 'fault': newFault})
            self._alarmPanel.alarm_state['zone'][zoneNumber]['last_fault'] = zoneInfo['seconds']
            _LOGGER.debug("(zone %i) %s", zoneNumber, zoneInfo['status'])
        return results


    async def queue_command(self, cmd, data, code = None):
        return await self.queue_commands([ { "cmd": cmd, "data": data, "code": code }])

    async def queue_commands(self, command_list : list):
        operations = []
        for command in command_list:
            cmd = command["cmd"]
            data = command["data"]
            code = command.get("code")
            logData = command.get("log")

            # Scrub the password and alarm code if necessary
            if not logData:
                logData = self.scrub_sensitive_data(data, code)
            _LOGGER.debug("Queueing command '%s' data: '%s' ; calling_task=%s", cmd, logData, asyncio.current_task().get_name())

            op = self.Operation(cmd, data, code, logData)
            op.expiryTime = time.time() + self._alarmPanel.command_timeout
            operations.append(op)
            self._commandQueue.append(op)

        self._commandEvent.set()
        for op in operations:
            await op.responseEvent.wait()
        return op.state == op.State.SUCCEEDED

    async def process_command_queue(self):
        """Manage processing of commands to be issued to the EVL.  Commands are serialized to the EVL to avoid 
           overwhelming it and to make it easy to pair up responses (since there are no sequence numbers for requests).

           Operations that fail due to a recoverable error (e.g. buffer overruns) will be re-tried with a backoff.
        """
        _LOGGER.info("Command processing task started.")

        while not self._shutdown:
            try:
                now = time.time()
                op = None

                # Default timeout to ensure we wake up periodically.
                timeout = self._alarmPanel.command_timeout

                while self._commandQueue:
                    _LOGGER.debug(f"Checking command queue: len={len(self._commandQueue)}")
                    op = self._commandQueue[0]
                    timeout = op.expiryTime - now

                    if op.state == self.Operation.State.SENT:
                        # Still waiting on a response from the EVL so break out of loop and wait for the response
                        if now >= op.expiryTime:
                            # Timeout waiting for response from the EVL so fail the command,
                            # This is likely due to the EVL becoming unresponsive so tear down the
                            # connection to start a recovery.
                            _LOGGER.error(f"Command '{op.cmd}' failed due to timeout waiting for response from EVL")
                            op.state = self.Operation.State.FAILED
                            await self.disconnect()
                        break
                    elif op.state == self.Operation.State.QUEUED:
                        # Send command to the EVL
                        op.state = self.Operation.State.SENT
                        self._cachedCode = op.code
                        try:
                            await self.send_command(op.cmd, op.data, op.logData)
                        except Exception as ex:
                            _LOGGER.error(f"Unexpected exception trying to send command: {ex}")
                            op.state = self.Operation.State.FAILED
                    elif op.state == self.Operation.State.SUCCEEDED:
                        # Remove completed command from head of the queue
                        self._commandQueue.pop(0)
                        op.responseEvent.set()
                    elif op.state == self.Operation.State.RETRY:
                        if now >= op.retryTime:
                            # Time to re-issue the command
                            op.state = self.Operation.State.QUEUED
                        else:
                            # Not time to re-issue yet so go back to sleep
                            timeout = op.retryTime - now
                            break
                    elif op.state == self.Operation.State.FAILED:
                        # Command completed; check the queue for more
                        op.responseEvent.set()
                        self._commandQueue.pop(0)

                # Wait until there is more work to do
                try:
                    self._commandEvent.clear()
                    await asyncio.wait_for(self._commandEvent.wait(), timeout=timeout)
                    _LOGGER.debug("Command processor woke up.")
                except asyncio.exceptions.TimeoutError:
                    pass
                except Exception as ex:
                    _LOGGER.error(f"Command processor woke up due unexpected exception {ex}")

            except Exception as ex:
                _LOGGER.error(f"Command processor caught unexpected exception {ex}")

        _LOGGER.info("Command processing task exited.")

    def command_succeeded(self, cmd):
        """Indicate that a command has been successfully processed by the EVL."""

        if self._commandQueue:
            op = self._commandQueue[0]
            if cmd and op.cmd != cmd:
                _LOGGER.error(f"Command acknowledgement received is different for a different command ({cmd}) than was issued ({op.cmd})")
            else:
                op.state = self.Operation.State.SUCCEEDED
        else:
            _LOGGER.error(f"Command acknowledgement received for '{cmd}' when no command was issued.")

        # Wake up the command processing task to process this result
        self._commandEvent.set()

    def command_failed(self, retry = False):
        """Indicate that a command issued to the EVL has failed."""

        if self._commandQueue:
            op = self._commandQueue[0]
            if op.state != self.Operation.State.SENT:
                _LOGGER.error("Command/system error received when no command was issued.")
            elif retry == False:
                # No retry request so tag the command as failed
                op.state = self.Operation.State.FAILED
            else:
                # Update the retry delay based on an exponential backoff
                op.retryDelay *= 2

                if op.retryDelay >= self._alarmPanel.command_timeout:
                    # Don't extend the retry delay beyond the overall command timeout
                    _LOGGER.error("Maximum command retries attempted; aborting command.")
                    op.state = self.Operation.State.FAILED
                else:
                    # Tag the command to be retried in the future by the command processor task
                    op.state = self.Operation.State.RETRY
                    op.retryTime = time.time() + op.retryDelay
                    _LOGGER.warn(f"Command '{op.cmd} {op.data}' failed; retry in {op.retryDelay} seconds.")
        else:
            _LOGGER.error("Command/system error received when no command is active.")

        # Wake up the command processing task to process this result
        self._commandEvent.set()

    def scrub_sensitive_data(self, data, code = None):
        if not self._loggedin:
            # Remove the password from the log entry
            logData = data.replace(self._alarmPanel.password, "*" * len(self._alarmPanel.password))
        else:
            logData = data

        if not code and self._commandQueue and self._commandQueue[0].code:
            code = str(self._commandQueue[0].code)
        if code:
            logData = logData.replace(code, "*" * len(code))
        return logData

