"""Test the pump driver responds with correct data.  Test order is from RegloICC manual."""
from random import choice, randint, uniform
from unittest import mock

import pytest

from ismatec import command_line
from ismatec.mock import Pump
from ismatec.util import Protocol


@pytest.fixture
def driver():
    """Confirm the pump correctly initializes."""
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
        assert await device.get_serial_protocol_version() == 8


# Pump drive


async def test_start_stop_roundtrip():
    """Confirm starting and stopping works."""
    async with Pump('fakeip') as device:
        await device.set_mode(1, Protocol.Mode.VOL_AT_RATE)
        await device.set_volume_setpoint(1, 10)
        await device.set_setpoint_type(1, Protocol.Setpoint.FLOWRATE)
        await device.set_flow_rate(1, flowrate=0.1)
        await device.set_mode(2, Protocol.Mode.FLOWRATE)
        await device.set_flow_rate(2, flowrate=0.1)

        await device.start(1)
        assert await device.is_running(1) is True
        assert await device.is_running(2) is False
        await device.start(2)
        assert await device.is_running(2) is True

        await device.stop(1)
        assert await device.is_running(1) is False
        assert await device.is_running(2) is True
        await device.stop(2)
        assert await device.is_running(2) is False


@pytest.mark.skip
async def test_pause_pumping():
    """Confirm pausing pumping works."""
    channel = choice([1, 2, 3, 4])
    async with Pump('fakeip') as device:
        await device.set_mode(channel, Protocol.Mode.RPM)
        await device.start(channel)
        await device.pause(channel)  # Pause = cancel in RPM mode
        assert await device.is_running(1) is False
        await device.set_mode(channel, Protocol.Mode.VOL_AT_RATE)
        await device.start(channel)
        await device.pause(channel)
        await device.pause(channel)  # unpause
        assert await device.is_running(channel)


async def test_rotation_roundtrip():
    """Confirm setting/getting flow direction works."""
    async with Pump('fakeip') as device:
        rotation_1 = choice(list(Protocol.Rotation))
        rotation_2 = choice(list(Protocol.Rotation))
        await device.set_rotation(1, rotation=rotation_1)
        await device.set_rotation(2, rotation=rotation_2)
        assert rotation_1 == await device.get_rotation(1)
        assert rotation_2 == await device.get_rotation(2)


async def test_cannot_run_responses():
    """Test reading the reason for a pump not running."""
    async with Pump('fakeip') as device:
        # await device.set_pump_cycle_count(channel=1, count=0)
        await device.set_mode(1, Protocol.Mode.VOL_PAUSE)
        assert await device.start(1) is False
        assert await device.get_run_failure_reason(1) == ('C', 0.0)  # 0 cycles

        await device.set_mode(2, Protocol.Mode.FLOWRATE)
        await device.set_flow_rate(2, flowrate=0)
        assert await device.start(2) is False
        assert await device.get_run_failure_reason(2) == ('R', 0.1386)  # 0 flowrate

        await device.set_mode(3, Protocol.Mode.VOL_AT_RATE)
        await device.set_setpoint_type(3, Protocol.Setpoint.FLOWRATE)
        await device.set_flow_rate(3, flowrate=0.01)
        await device.set_volume_setpoint(channel=3, vol=9999999)
        assert await device.start(3) is False
        assert await device.get_run_failure_reason(3) == ('V', 8308.0)  # max volume
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
        assert await device.get_setpoint_type(channel) == Protocol.Setpoint.RPM
        await device.set_setpoint_type(channel, Protocol.Setpoint.FLOWRATE)
        assert await device.get_setpoint_type(channel) == Protocol.Setpoint.FLOWRATE


async def test_speed_roundtrip():
    """Confirm that setting/getting speed (RPM) works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_speed(channel=1, rpm=sp_1)
        await device.set_speed(channel=2, rpm=sp_2)
        assert sp_1 == await device.get_speed(1)
        assert sp_2 == await device.get_speed(2)


async def test_flow_rate_roundtrip():
    """Confirm that setting/getting flowrates works."""
    async with Pump('fakeip') as device:
        flow_sp_1 = round(uniform(0.01, 0.14), 3)
        flow_sp_2 = round(uniform(0.01, 0.14), 3)
        await device.set_flow_rate(1, flowrate=flow_sp_1)
        await device.set_flow_rate(2, flowrate=flow_sp_2)
        assert flow_sp_1 == await device.get_flow_rate(1)
        assert flow_sp_2 == await device.get_flow_rate(2)


async def test_volume_setpoint_roundtrip():
    """Confirm setting/getting the volume setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_volume_setpoint(1, vol=sp_1)
        await device.set_volume_setpoint(2, vol=sp_2)
        assert sp_1 == await device.get_volume_setpoint(1)
        assert sp_2 == await device.get_volume_setpoint(2)


async def test_runtime_setpoint_roundtrip():
    """Confirm setting/getting the runtime setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 1)  # minutes
        sp_2 = round(uniform(1, 100), 1)
        await device.set_runtime(1, runtime=sp_1)
        await device.set_runtime(2, runtime=sp_2)
        assert sp_1 == await device.get_runtime(1)
        assert sp_2 == await device.get_runtime(2)


@pytest.mark.skip
async def test_pause_time_setpoint_roundtrip():
    """Confirm setting/getting the pause time setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 100), 2)
        sp_2 = round(uniform(1, 100), 2)
        await device.set_pause_time_setpoint(1, vol=sp_1)
        await device.set_pause_time_setpoint(2, vol=sp_2)
        assert sp_1 == await device.get_pause_time_setpoint(1)
        assert sp_2 == await device.get_pause_time_setpoint(2)


@pytest.mark.skip
async def test_cycle_count_roundtrip():
    """Confirm setting/getting the pause time setpoint works."""
    async with Pump('fakeip') as device:
        sp_1 = round(uniform(1, 10), 1)
        sp_2 = round(uniform(1, 10), 1)
        await device.set_cycles(1, vol=sp_1)
        await device.set_cycles(2, vol=sp_2)
        assert sp_1 == await device.get_cycles(1)
        assert sp_2 == await device.get_cycles(2)


async def test_max_flow_rate():
    """Confirm getting the (computed) maxmimum flowrates works."""
    async with Pump('fakeip') as device:
        await device.reset_default_settings()
        assert '0.138 ml/min' == await device.get_max_flow_rate(1, calibrated=False)
        await device.set_tubing_inner_diameter(1, diam=0.19)
        assert '0.281 ml/min' == await device.get_max_flow_rate(1, calibrated=False)
        assert '0.281 ml/min' == await device.get_max_flow_rate(1, calibrated=True)


@pytest.mark.skip
async def test_calculated_dispense_time():
    """Confirm getting the (computed) time to dispense a volume works."""
    raise NotImplementedError
    # async with Pump('fakeip') as device:
    #     channel = choice([1, 2, 3, 4])
    #     set a flowrate
    #     set a volume
    #     compute time to dispense
    #     assert time == await device.get_calculated_dispense_time(channel)


# Configuration


@pytest.mark.parametrize('tubing', Protocol.Tubing[::10])
async def test_tubing_diameter_roundtrip(tubing):
    """Confirm setting/getting the tubing Inner Diameter (ID) works."""
    async with Pump('fakeip') as device:
        channel = choice([1, 2, 3, 4])
        await device.set_tubing_inner_diameter(channel, tubing)
        assert tubing == await device.get_tubing_inner_diameter(channel)


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
        await device.set_rotation(1, rotation=Protocol.Rotation.COUNTERCLOCKWISE)
        assert Protocol.Rotation.COUNTERCLOCKWISE == await device.get_rotation(1)
        await device.reset_default_settings()
        assert Protocol.Rotation.CLOCKWISE == await device.get_rotation(1)


#  Calibration (not implemented)
#  System (not implemented)

async def test_pump_version():
    """Confirm getting the pump model."""
    async with Pump(('192.168.10.12', 23)) as device:
        assert await device.get_pump_version() == 'REGLO ICC 0208 306'
