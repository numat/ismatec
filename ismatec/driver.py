"""A single Ismatec Reglo ICC multi-channel peristaltic pump, class and usage example."""
from .util import SerialCommunicator, SocketCommunicator


class Pump(object):
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
            self.hw = SerialCommunicator(address=address, debug=debug, **kwargs)
        elif type(address) == tuple and len(address) == 2:
            # socket
            self.hw = SocketCommunicator(address=address, debug=debug, **kwargs)
        else:
            raise RuntimeError('Specify serial device or (host, port) tuple!')
        self.hw.start()

        # Assign address 1 to pump
        self.hw.command(b'@1')

        # Set everything to default
        self.hw.command(b'10')

        # Enable independent channel addressing
        self.hw.command(b'1~1')

        # Get number of channels
        try:
            nChannels = int(self.hw.query(b'1xA'))
        except ValueError:
            nChannels = 0

        # Enable asynchronous messages
        self.hw.command(b'1xE1')

        # list of channel indices for iteration and checking
        self.channels = list(range(1, nChannels + 1))

        # initial running states
        self.stop()
        self.hw.setRunningStatus(False, self.channels)

    ####################################################################
    # Properties or setters/getters                                    #
    # one per channel for the ones that have the channel kwarg.        #
    ####################################################################

    def getPumpVersion(self):
        """Return the pump model, firmware version, and pump head type code."""
        return self.hw.query(b'1#').strip()

    def getFlowrate(self, channel):
        """Return the current flowrate of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(b'%df' % channel)
        return float(reply) if reply else 0

    def getRunning(self, channel):
        """Return True if the specified channel is running."""
        assert channel in self.channels
        return self.hw.running[channel]

    def getTubingInnerDiameter(self, channel):
        """Return the set peristaltic tubing inner diameter on the specified channel, in mm."""
        assert channel in self.channels
        return float(self.hw.query(b'%d+' % channel).split(' ')[0])

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
        return self.hw.command(b'%d+%s' % (channel, self._discrete2(diam)))

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
                maxrates.append(float(self.hw.query(b'%d?' % ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(b'%d?' % channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.command(b'%dM' % channel)
        # set flow direction.  K=clockwise, J=counterclockwise
        if rate < 0:
            self.hw.command(b'%dK' % channel)
        else:
            self.hw.command(b'%dJ' % channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(b'%df%s' % (channel, self._volume2(rate)))
        # make sure the running status gets set from the start
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

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
                maxrates.append(float(self.hw.query(b'%d?' % ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(b'%d?' % channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # volume at rate mode
        self.hw.command(b'%dO' % channel)
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.hw.command(b'%dK' % channel)
        else:
            self.hw.command(b'%dJ' % channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(b'%df%s' % (channel, self._volume2(rate)))
        if units == 'rpm':
            self.hw.command(b'%dS%s' % (channel, self._discrete3(rate * 100)))
        else:
            self.hw.query(b'%df%s' % (channel, self._volume2(rate)))
        # set volume
        self.hw.query(b'%dv%s' % (channel, self._volume2(vol)))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

    def dispense_vol_over_time(self, vol, time, channel=0):
        """
        Dispense vol (ml) over time (min) on specified channel.

        If no channel is specified, dispense on all channels.
        """
        assert channel in self.channels or channel == 0
        # volume over time mode
        self.hw.command(b'%dG' % channel)
        # set flow direction
        if vol < 0:
            self.hw.command(b'%dK' % channel)
            vol *= -1
        else:
            self.hw.command(b'%dJ' % channel)
        # set volume
        self.hw.query(b'%dv%s' % (channel, self._volume2(vol)))
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(b'%dxT%s' % (channel, self._time2(time, units='m')))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

    def dispense_flow_over_time(self, rate, time, units='ml/min', channel=0):
        """
        Dispense at a set flowrate over time (min) on specified channel.

        Rate is specified by units, either 'ml/min' or 'rpm'.
        If no channel is specified, dispense on all channels.
        """
        assert channel in self.channels or channel == 0
        # set flow direction
        if rate < 0:
            self.hw.command(b'%dK' % channel)
            rate *= -1
        else:
            self.hw.command(b'%dJ' % channel)
        # set to flowrate mode first, otherwise Time mode uses RPMs
        self.hw.query(b'%dM' % channel)
        # Set to flowrate over time ("Time") mode
        self.hw.command(b'%dN' % channel)
        # set flowrate
        self.hw.query(b'%df%s' % (channel, self._volume2(rate)))
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(b'%dxT%s' % (channel, self._time2(time, units='m')))
        # make sure the running status gets set from the start
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

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
        return self.hw.command(b'%dI' % channel)

    ##################
    # Helper methods #
    ##################
    def _time1(self, number, units='s'):
        """Convert number to 'time type 1'.

        1-8 digits, 0 to 35964000 in units of 0.1s
        (0 to 999 hr)
        """
        number = 10 * number  # 0.1s
        if units == 'm':
            number = 60 * number
        if units == 'h':
            number = 60 * number
        return str(min(number, 35964000)).replace('.', '').encode()

    def _time2(self, number, units='s'):
        """Convert number to 'time type 2'.

        8 digits, 0 to 35964000 in units of 0.1s, left-padded with zeroes
        (0 to 999 hr)
        """
        number = 10 * number  # 0.1s
        if units == 'm':
            number = 60 * number
        if units == 'h':
            number = 60 * number
        return str(min(number, 35964000)).replace('.', '').zfill(8).encode()

    def _volume2(self, number):
        # convert number to "volume type 2"
        number = '%.3e' % abs(number)
        number = number[0] + number[2:5] + number[-3] + number[-1]
        return number.encode()

    def _volume1(self, number):
        # convert number to "volume type 1"
        number = '%.3e' % abs(number)
        number = number[0] + number[2:5] + 'E' + number[-3] + number[-1]
        return number.encode()

    def _discrete2(self, number):
        # convert float to "discrete type 2"
        s = str(number).strip('0')
        whole, decimals = s.split('.')
        return b'%04d' % int(whole + decimals)

    def _discrete3(self, number):
        """Convert number to 'discrete type 3'.

        6 digits, 0 to 999999, left-padded with zeroes
        """
        return str(number).zfill(6).encode()
