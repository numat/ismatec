"""Ismatec Reglo ICC multi-channel peristaltic pump driver.

Distributed under the GNU General Public License v3
Copyright (C) 2022 NuMat Technologies
"""
import logging

from .util import Protocol, SerialCommunicator, SocketCommunicator

logger = logging.getLogger('ismatec')


class Pump(Protocol):
    """Driver for a single Ismatec Reglo ICC peristaltic pump.

    The driver supports both serial and ethernet communication.

    If the pump has multiple tube channels, they can be controlled
    independently. See `self.channels` for available channels.
    """

    def __init__(self, address='/dev/ttyUSB0', **kwargs) -> None:
        """Connect to the pump and set initial state.

        This optionally takes an address of the form
            tcp://<<address>>:<<port>>
        to talk to connected serial-to-ethernet converters.

        Note that initialization sends multiple requests to the pump:
        1. Enable independent channel addressing (TODO why?)
        2. Disable asynchronous messages (TODO why?)
        3. Get list of all available tube channels. (TODO why?)
        4. Set initial running states (TODO why? to what?)
        """
        if address.startswith('tcp://'):
            ip, port = address[6:].split(':')
            self.hw = SocketCommunicator(address=(ip, int(port)), **kwargs)
        else:
            self.hw = SerialCommunicator(address=address, **kwargs)

        # Enable independent channel addressing
        self.hw.command('1~1')
        # Disable asynchronous messages
        self.hw.command('1xE0')
        # Get channel indices for request validation
        self.channels = self.get_channels()
        # Set initial running states and manually update cache
        for channel in self.channels:
            self.hw.command(f'{channel}I')
        self.hw.set_running_status(False, self.channels)

    async def __aenter__(self):
        """Asynchronously connect with the context manager."""
        return self

    async def __aexit__(self, *args):
        """Provide exit to the context manager."""
        self.hw._stop_event.set()

    async def get_version(self) -> str:
        """Get device version information."""
        pump_version = self.hw.query('1#').strip().split(' ')
        protocol_version = int(self.hw.query('1x!'))
        return {
            'description': pump_version[0],
            'software': pump_version[1],
            'pump head': pump_version[2],
            'protocol': protocol_version,
        }

    async def set_flow_rate(self, channel: int, flowrate):
        """Set the flow rate of the specified channel."""
        assert channel in self.channels
        flow = self._volume2(flowrate)  # TODO Clearer explanation of datatypes
        self.hw.command(f'{channel}f{flow}')

    async def get_flow_rate(self, channel: int) -> float:
        """Get the flow rate of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(f'{channel}f')
        return float(reply) / 1000 if reply else 0

    async def is_running(self, channel: int) -> bool:
        """Return if the specified channel is running."""
        assert channel in self.channels
        return self.hw.running[channel]

    async def get_mode(self, channel: int) -> str:
        """Get the mode of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(f'{channel}xM')
        return Protocol.Mode(reply).name

    async def set_mode(self, channel: int, mode: Protocol.Mode):
        """Set the mode of the specified channel."""
        assert channel in self.channels
        return self.hw.command(f'{channel}{mode.value}')

    def get_channels(self) -> list:
        """Get a list of available channel options.

        Return None if the pump is not configured for independent channels.
        """
        try:
            number_of_channels = int(self.hw.query('1xA'))
            return list(range(1, number_of_channels + 1))
        except ValueError:
            return None

    async def get_tubing_inner_diameter(self, channel: int) -> float:
        """Get the peristaltic tubing inner diameter (mm) of a channel."""
        assert channel in self.channels
        response = self.hw.query(f'{channel}+')
        return float(response[:-3])

    async def set_tubing_inner_diameter(self, channel: int, diam):
        """Set the peristaltic tubing inner diameter (mm) of a channel."""
        return self.hw.command(f'{channel}+{self._discrete2(diam)}')

    async def get_speed(self, channel) -> float:
        """Get the speed (RPM) of a channel."""
        return float(self.hw.query(f'{channel}S'))

    async def set_speed(self, channel: int, rpm: float) -> bool:
        """Set the speed (RPM) of a channel."""
        assert channel in self.channels
        rpm = int(round(rpm * 100, 2))
        return self.hw.command(f'{channel}S{self._discrete3(rpm)}')

    async def get_runtime(self, channel: int) -> float:
        """Get the runtime (minutes) of a channel."""
        assert channel in self.channels
        return float(self.hw.query(f'{channel}xT')) / 10 / 60

    async def set_runtime(self, channel: int, runtime: float) -> bool:
        """Set the runtime (minutes) of a channel."""
        assert channel in self.channels
        packed_time = self._time2(runtime, units='m')
        return self.hw.command(f'{channel}xT{packed_time}')

    async def get_volume_setpoint(self, channel) -> float:
        """Get the volume setpoint (mL) of a channel."""
        return float(self.hw.query(f'{channel}v')) / 1000

    async def set_volume_setpoint(self, channel, vol: float) -> bool:
        """Set the volume (mL) of a channel."""
        assert channel in self.channels
        return self.hw.command(f'{channel}v{self._volume2(vol)}')

    async def get_rotation(self, channel: int) -> Protocol.Rotation:  # Don't like this
        """Return the rotation direction on the specified channel."""
        assert channel in self.channels
        rotation_code = self.hw.query(f'{channel}xD')
        return Protocol.Rotation(rotation_code)

    async def set_rotation(self, channel: int, rotation: Protocol.Rotation):
        """Set the rotation direction on the specified channel."""
        return self.hw.command(f'{channel}{rotation.value}')

    async def get_setpoint_type(self, channel: int) -> Protocol.Setpoint:
        """Return the setpoint type (RPM or flowrate) on the specified channel."""
        assert channel in self.channels
        type_code = self.hw.query(f'{channel}xf')
        return Protocol.Setpoint(type_code)

    async def set_setpoint_type(self, channel: int, type: Protocol.Setpoint):
        """Set the setpoint type (RPM or flow rate) on the specified channel."""
        return self.hw.command(f'{channel}xf{type.value}')

    async def get_max_flow_rate(self, channel: int, calibrated=False):
        """Get the max flow rate (mL/min) achievable with current settings."""
        if calibrated:
            return self.hw.query(f'{channel}!')
        else:
            return self.hw.query(f'{channel}?')

    async def get_run_failure_reason(self, channel: int) -> tuple:
        """Get reason for failure to run."""
        result = self.hw.query(f'{channel}xe')
        exponent = float(result[-2:].strip('+'))
        mantissa = float(result[2:6]) / 1000
        return (result[0], mantissa * 10 ** exponent)

    async def has_channel_addressing(self) -> bool:
        """Return status of channel addressing."""
        return self.hw.query('1~') == '1'

    async def set_channel_addressing(self, on) -> bool:
        """Enable or disable channel addressing."""
        on = 1 if on else 0
        return bool(self.hw.command(f'1~{on}'))

    async def has_event_messaging(self) -> bool:
        """Return status of event messaging."""
        return self.hw.query('1xE') == '1'

    async def set_event_messaging(self, on) -> bool:
        """Enable or disable event messaging."""
        on = 1 if on else 0
        return bool(self.hw.command(f'1xE{on}'))

    async def reset_default_settings(self) -> bool:
        """Reset all user configurable data to default values."""
        return bool(self.hw.command('10'))  # '1' is a pump address, not channel

    async def continuous_flow(self, channel: int, rate: float):
        """Start continuous flow (mL/min) on specified channel."""
        assert channel in self.channels
        maxrate = float(self.hw.query(f'{channel}?').split(' ')[0])
        # flow rate mode
        self.hw.command(f'{channel}M')
        # set flow direction.  K=clockwise, J=counterclockwise
        if rate < 0:
            self.hw.command(f'{channel}K')
        else:
            self.hw.command(f'{channel}J')
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        # make sure the running status gets set from the start
        self.hw.set_running_status(True, channel)
        # start
        self.hw.command(f'{channel}H')

    async def dispense_vol_at_rate(self, channel: int, vol, rate, units='ml/min'):
        """Dispense vol (ml) at rate on specified channel.

        Rate is specified by units, either 'ml/min' or 'rpm'.
        If no channel is specified, dispense on all channels.
        """
        if units == 'rpm':
            maxrate = 100.0
        elif channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query(f'{ch}?').split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(f'{channel}?').split(' ')[0])
        assert channel in self.channels or channel == 0
        # volume at rate mode
        self.hw.command(f'{channel}O')
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.hw.command(f'{channel}K')
        else:
            self.hw.command(f'{channel}J')
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        if units == 'rpm':
            self.hw.command(f'{channel}S{self._discrete3(rate * 100)}')
        else:
            self.hw.query(f'{channel}f{self._volume2(rate)}')
        # set volume
        self.hw.query(f'{channel}v{self._volume2(vol)}')
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.set_running_status(True, channel)
        # start
        self.hw.command(f'{channel}H')

    async def dispense_vol_over_time(self, channel: int, vol, time):
        """Dispense vol (ml) over time (min) on specified channel."""
        assert channel in self.channels
        # volume over time mode
        self.hw.command(f'{channel}G')
        # set flow direction
        if vol < 0:
            self.hw.command(f'{channel}K')
            vol *= -1
        else:
            self.hw.command(f'{channel}J')
        # set volume
        self.hw.query(f'{channel}v{self._volume2(vol)}')
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(f"{channel}xT{self._time2(time, units='m')}")
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.set_running_status(True, channel)
        # start
        self.hw.command(f'{channel}H')

    async def dispense_flow_over_time(self, channel: int, rate, time, units='ml/min'):
        """Dispense at a set flowrate over time (min) on specified channel."""
        assert channel in self.channels
        # set flow direction
        if rate < 0:
            self.hw.command(f'{channel}K')
            rate *= -1
        else:
            self.hw.command(f'{channel}J')
        # set to flowrate mode first, otherwise Time mode uses RPMs
        self.hw.query(f'{channel}M')
        # Set to flowrate over time ("Time") mode
        self.hw.command(f'{channel}N')
        # set flowrate
        self.hw.query(f'{channel}f{self._volume2(rate)}')
        # set time.  Note: if the time is too short, the pump will not start.
        self.hw.query(f"{channel}xT{self._time2(time, units='m')}")
        # make sure the running status gets set from the start
        self.hw.set_running_status(True, channel)
        # start
        self.hw.command(f'{channel}H')

    async def start(self, channel: int):
        """Start any pumping operation on specified channel."""
        assert channel in self.channels
        # doing this misses the asynchronous start signal, so set manually
        result = self.hw.command(f'{channel}H')
        self.hw.set_running_status(result, channel)
        return result

    async def stop(self, channel: int):
        """Stop any pumping operation on specified channel."""
        # here we can stop all channels by specifying 0
        assert channel in self.channels
        # doing this misses the asynchronous stop signal, so set manually
        result = self.hw.command(f'{channel}I')
        self.hw.set_running_status(not result, channel)
        return result
