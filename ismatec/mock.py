"""Contains mocks for driver objects for offline testing."""

import asyncio
from random import uniform
from unittest.mock import MagicMock

from .driver import Pump as RealPump


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


class Communicator(MagicMock):
    """Mock the pump communication hardware."""

    def query(self, command):
        """Mock replies to queries."""
        channel = int(command[0])
        if channel not in self.channels:
            raise NotImplementedError
        command = command[1:]
        if command == 'f':  # getFlowrate
            return float(self.state[channel - 1]['flowrate'])
