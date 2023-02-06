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


class Pump():
    """Mocks the overhead stirrer driver for offline testing."""

    def __init__(self, *args, **kwargs):
        """Set up connection parameters with default port."""
        self.client = AsyncClientMock()
        self.state = {}

    async def __aenter__(self, *args):
        """Set up connection."""
        return self

    async def __aexit__(self, *args):
        """Close connection."""
        pass

    async def getFlowrate(self, channel=1):
        """Return a fake flowrate."""
        return 1.0 * channel
