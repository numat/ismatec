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


async def test_flowrate_roundtrip():
    """Confirm that setting/getting flowrates works."""
    async with Pump('fakeip') as device:
        flow_sp_1 = round(uniform(1, 10), 1)
        flow_sp_2 = round(uniform(1, 10), 1)
        # FIXME the Pump class has no setFlowrate method yet
        device.hw.query(f'1f{flow_sp_1}'.encode())
        device.hw.query(f'2f{flow_sp_2}'.encode())
        assert flow_sp_1 == await device.getFlowrate(1)
        assert flow_sp_2 == await device.getFlowrate(2)
