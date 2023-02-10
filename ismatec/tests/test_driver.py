"""Test the pump driver responds with correct data.  Test order is from RegloICC manual."""
from random import choice, randint, uniform
from unittest import mock

import pytest
from ismatec import command_line
from ismatec.mock import Pump
from ismatec.util import Protocol


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

# Communications management


async def test_channel_addressing_roundtrip():
    """Confirm that enabling/disabling channel addressing works."""
    async with Pump('fakeip') as device:
        await device.set_channel_addressing(True)
        assert await device.has_channel_addressing()
        await device.set_channel_addressing(False)
        assert await device.has_channel_addressing() is False


async def test_event_messaging_roundtrip():
    """Confirm that enabling/disabling async event messages works."""
    async with Pump('fakeip') as device:
        await device.set_event_messaging(True)
        assert await device.has_event_messaging()
        await device.set_event_messaging(False)
        assert await device.has_event_messaging() is False


async def test_serial_protocol_version():
    """Confirm getting the serial protocol version."""
    async with Pump('fakeip') as device:
        assert await device.get_serial_protocol_version() == 2


# Pump drive


async def test_start_stop_roundtrip():
    """Confirm starting and stopping works."""
    async with Pump('fakeip') as device:
        # FIXME the Pump class has no start method yet
        device.hw.command('1H')
        assert device.get_running(1) is True
        assert await device.get_running(2) is False
        await device.start(2)
        assert await device.get_running(2) is True

        device.stop(1)
        assert device.get_running(1) is False
        assert await device.get_running(2) is True
        await device.stop(2)
        assert await device.get_running(2) is False


@pytest.mark.skip
async def test_pause_pumping():
    """Confirm pausing pumping works."""
    channel = choice([1, 2, 3, 4])
    async with Pump('fakeip') as device:
        await device.set_mode(channel, Protocol.Mode.RPM)
        await device.start(channel)
        await device.pause(channel)  # Pause = cancel in RPM mode
        assert await device.get_running(1) is False
        await device.set_mode(channel, Protocol.Mode.VOL_AT_RATE)
        await device.start(channel)
        await device.pause(channel)
        await device.pause(channel)  # unpause
        assert await device.get_running(channel)


async def test_rotation_roundtrip():
    """Confirm setting/getting flow direction works."""
    async with Pump('fakeip') as device:
        rotation_1 = choice(['K', 'J'])
        rotation_2 = choice(['counterclockwise', 'clockwise'])
        # FIXME the Pump class has no setRotation method yet
        device.hw.command(f'1{rotation_1}')
        await device.set_rotation(channel=2, rotation=rotation_2)
        assert rotation_1 == device.hw.query('1xD')
        assert rotation_2 == await device.get_rotation(channel=2)


async def test_cannot_run_responses():
    """Test reading the reason for a pump not running."""
    raise NotImplementedError

# Operational mode and settings


@pytest.mark.parametrize('mode', Protocol.Mode)
async def test_modes(mode):
    """Confirm setting/getting modes works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        await device.set_mode(channel, mode)
        assert mode.name == await device.get_mode(channel)


async def test_setpoint_type_roundtrip():
    """Confirm changing between flow and speed setpoint works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        await device.set_setpoint_type(channel, Protocol.Setpoint.RPM)
        assert await device.get_setpoint_type(channel, Protocol.Setpoint.FLOWRATE)
        await device.set_setpoint_type(channel, Protocol.Setpoint.ML)
        assert await device.get_setpoint_type(channel, Protocol.Setpoint.FLOWRATE)


async def test_speed_roundtrip():
    """Confirm that setting/getting speed (RPM) works."""
    async with Pump('fakeip') as device:
        sp_1 = randint(1, 100)
        sp_2 = randint(1, 100)
        await device.set_speed(channel=1, rpm=sp_1)
        await device.set_speed(channel=2, rpm=sp_2)
        assert sp_1 == await device.get_speed(1)
        assert sp_2 == await device.get_speed(2)


async def test_flowrate_roundtrip():
    """Confirm that setting/getting flowrates works."""
    async with Pump('fakeip') as device:
        flow_sp_1 = round(uniform(1, 10), 1)
        flow_sp_2 = round(uniform(1, 10), 1)
        await device.set_flowrate(channel=1, flowrate=flow_sp_1)
        await device.set_flowrate(channel=2, flowrate=flow_sp_2)
        assert flow_sp_1 == await device.get_flowrate(1)
        assert flow_sp_2 == await device.get_flowrate(2)


async def test_volume_setpoint_roundtrip():
    """Confirm setting/getting the volume setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_volume_setpoint(channel=1, vol=sp_1)
        await device.set_volume_setpoint(channel=2, vol=sp_2)
        assert sp_1 == await device.get_volume_setpoint(1)
        assert sp_2 == await device.get_volume_setpoint(2)


async def test_runtime_setpoint_roundtrip():
    """Confirm setting/getting the runtime setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_runtime_setpoint(channel=1, vol=sp_1)
        await device.set_runtime_setpoint(channel=2, vol=sp_2)
        assert sp_1 == await device.get_runtime_setpoint(1)
        assert sp_2 == await device.get_runtime_setpoint(2)


@pytest.mark.skip
async def test_pause_time_setpoint_roundtrip():
    """Confirm setting/getting the pause time setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_pause_time_setpoint(channel=1, vol=sp_1)
        await device.set_pause_time_setpoint(channel=2, vol=sp_2)
        assert sp_1 == await device.get_pause_time_setpoint(1)
        assert sp_2 == await device.get_pause_time_setpoint(2)


@pytest.mark.skip
async def test_cycle_count_roundtrip():
    """Confirm setting/getting the pause time setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 10), 1)
        sp_2 = round(uniform(1, 10), 1)
        await device.set_cycles(channel=1, vol=sp_1)
        await device.set_cycles(channel=2, vol=sp_2)
        assert sp_1 == await device.get_cycles(1)
        assert sp_2 == await device.get_cycles(2)


async def test_max_flowrate():
    """Confirm getting the (computed) maxmimum flowrates works."""
    async with Pump('fakeip') as device:
        raise NotImplementedError
        # set a known tubing size for channel 1
        # set a different known tubing size for channel 2
        # calibrate channel 2
        # compute max flowrate with that tubing size for channel 1
        # compute max calibrated flowrate for channel 2
        assert max1 == await device.get_max_flowrate(1, calibrated=False)
        assert max2 == await device.get_max_flowrate(2, calibrated=True)


@pytest.mark.skip
async def test_calculated_dispense_time():
    """Confirm getting the (computed) time to dispense a volume works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        raise NotImplementedError
        # set a flowrate
        # set a volume
        # compute time to dispense
        assert time == await device.get_calculated_dispense_time(channel)


# Configuration


@pytest.mark.parametrize('tubing', Protocol.Tubing[::10])
async def test_tubing_diameter_roundtrip(tubing):
    """Confirm setting/getting the tubing Inner Diameter (ID) works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        await device.set_tubing_diameter(channel, tubing)
        assert tubing == device.get_tubing_diameter(channel)


@pytest.mark.skip
async def test_backsteps_roundtrip():
    """Confirm setting/getting the backsteps works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        backsteps = randint(1, 100)
        await device.set_backsteps(channel, backsteps)
        assert backsteps == device.get_backsteps(channel)


async def test_reset():
    """Confirm resetting user-configurable data works."""
    async with Pump('fakeip') as device:
        # FIXME the Pump class has no setRotation method yet
        device.hw.command('1K')  # counterclockwise
        assert 'K' == device.hw.query('1xD')
        await device.reset_default_settings()
        assert 'J' == device.hw.query('1xD')


#  Calibration (not implemented)
#  System (not implemented)
