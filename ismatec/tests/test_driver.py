"""Test the pump driver responds with correct data."""
from random import uniform
from unittest import mock

import pytest

from ismatec import command_line
from ismatec.mock import Pump


@pytest.fixture
def driver():
    """Confirm the hotplate correctly initializes."""
    return Pump('fakeip')


@pytest.mark.parametrize('channel', ['1', '2', '3'])
@mock.patch('ismatec.Pump', Pump)
def test_driver_cli(capsys, channel):
    """Confirm the commandline interface works with different channels."""
    command_line(['fakeip', '--port', '126', '--channel', channel])
    captured = capsys.readouterr()
    assert f"{channel}.0" in captured.out
