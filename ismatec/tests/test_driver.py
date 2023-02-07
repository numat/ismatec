"""Test the pump driver responds with correct data."""
from random import choice, uniform
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
        await device.setFlowrate(channel=2, flowrate=flow_sp_2)
        assert flow_sp_1 == await device.getFlowrate(1)
        assert flow_sp_2 == await device.getFlowrate(2)


async def test_rotation_roundtrip():
    """Confirm setting/getting flow direction works."""
    async with Pump('fakeip') as device:
        rotation_1 = choice(['K', 'J'])
        rotation_2 = choice(['counterclockwise', 'clockwise'])
        # FIXME the Pump class has no setRotation method yet
        device.hw.command(f'1{rotation_1}')
        await device.setRotation(channel=2, rotation=rotation_2)
        assert rotation_1 == device.hw.query('1xD')
        assert rotation_2 == await device.getRotation(channel=2)


async def test_start_stop_roundtrip():
    """Confirm starting and stopping works."""
    async with Pump('fakeip') as device:
        # FIXME the Pump class has no start method yet
        device.hw.command('1H')
        assert device.getRunning(1) is True
        assert await device.getRunning(2) is False
        await device.start(2)
        assert await device.getRunning(2) is True

        device.stop(1)
        assert device.getRunning(1) is False
        assert await device.getRunning(2) is True
        await device.stop(2)
        assert await device.getRunning(2) is False