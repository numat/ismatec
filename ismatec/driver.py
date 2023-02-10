"""A single Ismatec Reglo ICC multi-channel peristaltic pump class."""
import logging

from .util import Protocol, SerialCommunicator, SocketCommunicator

logger = logging.getLogger('ismatec')


class Pump(Protocol):
    """
    Class for representing a single Ismatec Reglo ICC multi-channel peristaltic pump.

    It can be controlled over a serial server (gateway) or direct serial.

    The, which can be controlled independently, are available as self.channels.
    """

    def __init__(self, debug=False, address=None, **kwargs):
        """Initialize the Communicator and setup the pump to accept commands."""
        # make a hardware Communicator object
        if type(address) == str:
            # serial
            self.hw = SerialCommunicator(address=address, **kwargs)
        elif type(address) == tuple and len(address) == 2:
            # socket
            self.hw = SocketCommunicator(address=address, **kwargs)
        else:
            raise RuntimeError('Specify serial device or (host, port) tuple!')
        self.hw.start()

        # Assign address 1 to pump
        self.hw.command('@1')

        # Enable independent channel addressing
        self.hw.command('1~1')

        # Get number of channels

        # Enable asynchronous messages
        self.hw.command('1xE1')

        # list of channel indices for iteration and checking
        self.nChannels = self.getNumberChannels()
        self.channels = list(range(1, self.nChannels + 1))

        # initial running states
        self.stop()
        self.hw.setRunningStatus(False, self.channels)

    async def __aenter__(self):
        """Asynchronously connect with the context manager."""
        return self

    async def __aexit__(self, *args):
        """Provide exit to the context manager."""
        self.hw._stop_event.set()

    ####################################################################
    # Properties or setters/getters                                    #
    # one per channel for the ones that have the channel kwarg.        #
    ####################################################################

    def getPumpVersion(self):
        """Return the pump model, firmware version, and pump head type code."""
        return self.hw.query('1#').strip()

    async def get_serial_protocol_version(self):
        """Return serial protocol version."""
        return self.hw.query('1x!')

    async def setFlowrate(self, channel, flowrate):
        """Set the flowrate of the specified channel."""
        assert channel in self.channels
        flow = self._volume2(flowrate)
        self.hw.query(f'{channel}f{flow}')

    async def getFlowrate(self, channel):
        """Return the current flowrate of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(f'{channel}f')
        return float(reply) / 1000 if reply else 0

    def getRunning(self, channel):
        """Return True if the specified channel is running."""
        assert channel in self.channels
        return self.hw.running[channel - 1]

    async def get_mode(self, channel: int) -> str:
        """Return the current mode of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(f'{channel}xM')
        return Protocol.Mode(reply).name

    async def setMode(self, channel: int, mode: Protocol.Mode):
        """Set the mode of the specified channel."""
        assert channel in self.channels
        return self.hw.command(f'{channel}{mode.value}')

    def getNumberChannels(self):
        """Get the number of (currently configured) pump channels.

        Return 0 if the pump is not configured for independent channels.
        """
        try:
            return int(self.hw.query('1xA'))
        except ValueError:
            return 0

    def getTubingInnerDiameter(self, channel):
        """Return the set peristaltic tubing inner diameter on the specified channel, in mm."""
        assert channel in self.channels
        return float(self.hw.query(f'{channel}+').split(' ')[0])

    def setTubingInnerDiameter(self, diam, channel=None):
        """
        Set the peristaltic tubing inner diameter on the specified channel, in mm.

        If no channel is specified, set it on all channels.
        """
        if channel is None:
            allgood = True
            for ch in self.channels:
                allgood = allgood and self.setTubingInnerDiameter(diam, channel=ch)
            return allgood
        return self.hw.command(f'{channel}+{self._discrete2(diam)}')

    async def has_channel_addressing(self):
        """Return status of channel addressing."""
        return self.hw.query('1~')

    async def set_channel_addressing(self, on):
        """Enable or disable channel addressing."""
        on = 1 if on else 0
        return bool(self.hw.query(f'1~{on}'))

    async def has_event_messaging(self):
        """Return status of event messaging."""
        return self.hw.query('1xE')

    async def set_event_messaging(self, on):
        """Enable or disable event messaging."""
        on = 1 if on else 0
        return bool(self.hw.query(f'1xE{on}'))

    async def resetDefaultSettings(self):
        """Reset all user configurable data to default values."""
        return self.hw.command('10')  # '1' is a pump address, not channel

    def continuousFlow(self, rate, channel=None):
        """
        Start continuous flow at rate (ml/min) on specified channel.

        If no channel is specified, start flow on all channels.
        """
        if channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query(f'{ch}?').split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(f'{channel}?').split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.command(f'{channel}M')
        # set flow direction.  K=clockwise, J=counterclockwise
        if rate < 0:
            self.hw.command(f'{channel}K')
        else:
            self.hw.command(f'{channel}J')
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        # make sure the running status gets set from the start
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(f'{channel}H')

    def dispense_vol_at_rate(self, vol, rate, units='ml/min', channel=None):
        """
        Dispense vol (ml) at rate on specified channel.

        Rate is specified by units, either 'ml/min' or 'rpm'.
        If no channel is specified, dispense on all channels.
        """
        if units == 'rpm':
            maxrate = 100
        elif channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query(f'{ch}?').split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(f'{channel}?').split(' ')[0])
        assert channel in self.channels or channel == 0
        # volume at rate mode
        self.hw.command(f'{channel}O')
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.hw.command(f'{channel}K')
        else:
            self.hw.command(f'{channel}J')
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        if units == 'rpm':
            self.hw.command(f'{channel}S{self._discrete3(rate * 100)}')
        else:
            self.hw.query(f'{channel}f{self._volume2(rate)}')
        # set volume
        self.hw.query(f'{channel}v{self._volume2(vol)}')
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(f'{channel}H')

    def dispense_vol_over_time(self, vol, time, channel=0):
        """
        Dispense vol (ml) over time (min) on specified channel.

        If no channel is specified, dispense on all channels.
        """
        assert channel in self.channels or channel == 0
        # volume over time mode
        self.hw.command(f'{channel}G')
        # set flow direction
        if vol < 0:
            self.hw.command(f'{channel}K')
            vol *= -1
        else:
            self.hw.command(f'{channel}J')
        # set volume
        self.hw.query(f'{channel}v{self._volume2(vol)}')
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(f"{channel}xT{self._time2(time, units='m')}")
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(f'{channel}H')

    def dispense_flow_over_time(self, rate, time, units='ml/min', channel=0):
        """
        Dispense at a set flowrate over time (min) on specified channel.

        Rate is specified by units, either 'ml/min' or 'rpm'.
        If no channel is specified, dispense on all channels.
        """
        assert channel in self.channels or channel == 0
        # set flow direction
        if rate < 0:
            self.hw.command(f'{channel}K')
            rate *= -1
        else:
            self.hw.command(f'{channel}J')
        # set to flowrate mode first, otherwise Time mode uses RPMs
        self.hw.query(f'{channel}M')
        # Set to flowrate over time ("Time") mode
        self.hw.command(f'{channel}N')
        # set flowrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(f"{channel}xT{self._time2(time, units='m')}")
        # make sure the running status gets set from the start
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(f'{channel}H')

    def stop(self, channel=None):
        """
        Stop any pumping operation on specified channel.

        If no channel is specified, stop on all channels.
        """
        # here we can stop all channels by specifying 0
        channel = 0 if channel is None else channel
        assert channel in self.channels or channel == 0
        # doing this misses the asynchronous stop signal, so set manually
        self.hw.setRunningStatus(False, channel)
        return self.hw.command(f'{channel}I')
