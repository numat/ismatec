"""Contains mocks for driver objects for offline testing."""

from unittest.mock import MagicMock

from .driver import Pump as RealPump
from .util import Protocol


class AsyncClientMock(MagicMock):
    """Magic mock that works with async methods."""

    async def __call__(self, *args, **kwargs):
        """Convert regular mocks into into an async coroutine."""
        return super().__call__(*args, **kwargs)


class Pump(RealPump):
    """Mocks the overhead stirrer driver for offline testing."""

    def __init__(self, *args, **kwargs):
        """Set up connection parameters with default port."""
        self.client = AsyncClientMock()
        self.channels = [1, 2, 3, 4]
        self.running = {channel: False for channel in self.channels}
        self.state = {
            'channel_addressing': False,  # FIXME verify
            'event_messaging': False,  # FIXME verify
        }
        self.state['channels'] = [
            {
                'flowrate': 1.0 * c,
                'rotation': Protocol.Rotation.CLOCKWISE,
                'mode': Protocol.Mode.RPM,
                'diameter': Protocol.Tubing[0],
                'setpoint_type': Protocol.Setpoint.RPM,
                'rpm': 0.0,
                'volume': 0.0,
                'cycles': 0,
                'runtime': 0.0,
            }
            for c in self.channels]
        self.hw = Communicator()
        self.hw.channels = self.channels
        self.hw.running = self.running
        self.hw.state = self.state

    async def __aenter__(self, *args):
        """Set up connection."""
        return self

    async def __aexit__(self, *args):
        """Close connection."""
        pass


class Communicator(MagicMock, Protocol):
    """Mock the pump communication hardware."""

    def query(self, command) -> str:
        """Mock replies to queries."""
        if command == '1~':  # channel addressing
            return '1' if self.state['channel_addressing'] else '0'
        channel = int(command[0])
        if channel not in self.channels:
            raise ValueError
        command = command[1:]
        if command == 'f':  # getFlowrate (in mL/min)
            return self._volume1(self.state['channels'][channel - 1]['flowrate'])
        elif command == 'xD':  # get rotation direction
            return Protocol.Rotation[self.state['channels'][channel - 1]['rotation']].value
        elif command == 'xM':  # get current mode
            return Protocol.Mode[self.state['channels'][channel - 1]['mode']].value
        elif command == 'xf':  # get current setpoint type
            return Protocol.Setpoint[self.state['channels'][channel - 1]['setpoint_type']].value
        elif command == 'xE':  # async event messages enabled?
            return '1' if self.state['event_messaging'] else '0'
        elif command == 'x!':  # protocol version
            return '8'
        elif command == '+':  # tubing diameter
            return str(self.state['channels'][channel - 1]['diameter']) + ' mm'
        elif command == 'S':  # get speed (RPM)
            return str(self.state['channels'][channel - 1]['rpm'])
        elif command == 'v':  # get volume (mL)
            return str(round(self.state['channels'][channel - 1]['volume'] * 100, 2)) + 'E+1'
        elif command.startswith('xT'):  # get runtime (in min)
            return self._time1(self.state['channels'][channel - 1]['runtime'], units='m')
        elif command == '#':  # pump version
            return 'REGLO ICC 0208 306'
        elif command == 'xe':
            return self._get_cannot_run_response(channel)
        elif command in ['!', '?']:
            return ('0.281 ml/min' if self.state['channels'][channel - 1]['diameter'] == 0.19
                    else '0.138 ml/min')
        else:
            raise NotImplementedError

    def _get_cannot_run_response(self, channel):
        """Return the responses for when the pump failed to run."""
        if (self.state['channels'][channel - 1]['mode'] == Protocol.Mode.VOL_PAUSE.name
           and self.state['channels'][channel - 1]['cycles'] == 0):
            return 'C 0000E+1'  # cycles = 0
        elif (self.state['channels'][channel - 1]['mode'] == Protocol.Mode.FLOWRATE.name
              and self.state['channels'][channel - 1]['flowrate'] == 0):
            return 'R 1386E-1'  # flowrate = 0
        elif (self.state['channels'][channel - 1]['mode'].startswith('VOL_')
              and self.state['channels'][channel - 1]['volume'] >= 1256):
            return 'V 8308E+3'  # flowrate > max
        return ValueError

    def command(self, command):
        """Mock commands."""
        if command == '10':  # reset all settings
            for channel, _ in enumerate(self.channels):
                self.state['channels'][channel]['rotation'] = Protocol.Rotation.CLOCKWISE.name
                self.state['channels'][channel]['flowrate'] = 0.0
                self.running[channel] = False
            return True
        elif command.startswith('1~'):
            self.state['channel_addressing'] = bool(int(command[-1]))
            return True
        channel = int(command[0])
        if channel not in self.channels:
            raise ValueError
        command = command[1:]
        if command in ['J', 'K']:  # set to CCW (K) or CW (J) rotation
            self.state['channels'][channel - 1]['rotation'] = Protocol.Rotation(command).name
        elif command.startswith('xE'):
            self.state['event_messaging'] = bool(int(command[-1]))
        elif command == 'H':  # start
            if self._check_pump_will_run(channel):
                self.running[channel] = True
            else:
                return False
        elif command == 'I':  # stop
            self.running[channel] = False
        elif command in [m.value for m in Protocol.Mode]:
            self.state['channels'][channel - 1]['mode'] = Protocol.Mode(command).name
        elif command.startswith('xf'):  # set mode to RPM (0) or flowrate (1)
            type = Protocol.Setpoint(command[-1]).name
            self.state['channels'][channel - 1]['setpoint_type'] = type
        elif command.startswith('+'):  # set tubing ID
            self.state['channels'][channel - 1]['diameter'] = float(command[1:]) / 100
        elif command.startswith('S'):  # set speed (RPM)
            self.state['channels'][channel - 1]['rpm'] = float(command[1:]) / 100
        elif command.startswith('f'):  # set flowrate (in mL/min)
            exponent = int(command[-2:])
            matissa = float(command[1:5]) / 1000
            self.state['channels'][channel - 1]['flowrate'] = float(matissa * 10**exponent)
        elif command.startswith('v'):  # set volume (in mL)
            exponent = int(command[-2:])
            matissa = float(command[1:5]) / 1000
            self.state['channels'][channel - 1]['volume'] = float(matissa * 10**exponent)
        elif command.startswith('xT'):  # set runtime (in min)
            seconds = float(command[3:]) / 10
            self.state['channels'][channel - 1]['runtime'] = seconds / 60
        else:
            raise NotImplementedError
        return True

    def _check_pump_will_run(self, channel):
        """Return whether or not the pump will run with the current settings."""
        return not ((self.state['channels'][channel - 1]['mode'] == Protocol.Mode.VOL_PAUSE.name
                    and self.state['channels'][channel - 1]['cycles'] == 0)
                    or (self.state['channels'][channel - 1]['mode'] == Protocol.Mode.FLOWRATE.name
                    and self.state['channels'][channel - 1]['flowrate'] == 0)
                    or (self.state['channels'][channel - 1]['mode'].startswith('VOL_')
                    and self.state['channels'][channel - 1]['volume'] >= 1256))
