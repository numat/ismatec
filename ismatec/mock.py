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
        self.running = [False for channel in self.channels]
        self.state = [
            {
                'channel': c,
                'flowrate': 1.0 * c,
                'direction': 'clockwise',
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

    def query(self, command):
        """Mock replies to queries."""
        channel = int(command[0])
        if channel not in self.channels:
            raise ValueError
        command = command[1:]
        if command == 'f':  # getFlowrate (in mL/min)
            return self._volume1(self.state[channel - 1]['flowrate'])
        elif command.startswith('f'):  # set flowrate (in mL/min)
            exponent = int(command[-2:])
            matissa = float(command[1:5]) / 1000
            self.state[channel - 1]['flowrate'] = float(matissa * 10**exponent)
        elif command == 'xD':  # get rotation direction
            cw = self.state[channel - 1]['direction'] == 'clockwise'
            return 'J' if cw else 'K'
        else:
            raise NotImplementedError

    def command(self, command):
        """Mock commands."""
        if command == '10':  # reset all settings
            for channel, _ in enumerate(self.channels):
                self.state[channel]['direction'] = 'clockwise'
                self.state[channel]['flowrate'] = 0.0
                self.running[channel] = False
            return
        channel = int(command[0])
        if channel not in self.channels:
            raise ValueError
        command = command[1:]
        if command == 'K':  # set to CCW rotation
            self.state[channel - 1]['direction'] = 'counterclockwise'
        elif command == 'J':  # set to CW rotation
            self.state[channel - 1]['direction'] = 'clockwise'
        elif command == 'H':  # start
            self.running[channel - 1] = True
        elif command == 'I':  # stop
            self.running[channel - 1] = False
        else:
            raise NotImplementedError
        return '*'
