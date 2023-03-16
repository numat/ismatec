"""Transports and helpers for Ismatec Reglo ICC peristaltic pump.

Distributed under the GNU General Public License v3
Copyright (C) 2022 NuMat Technologies
"""
import logging
import select
import socket
import threading
import time
from abc import abstractmethod
from enum import Enum
from typing import Dict
from queue import Queue

import serial

logger = logging.getLogger('ismatec')


class Communicator(threading.Thread):
    """Interface to the Ismatec Reglo ICC peristaltic pump.

    It handles the communication via direct serial or through a serial
    server, and keeps track of the messy mix of synchronous (command)
    and asynchronous (status) communication.

    This communicator uses a threaded queue to provide non-blocking
    serial communication. TODO explore async serial development.
    """

    def __init__(self):
        """Initialize the communications link and create queues for commands and responses."""
        super(Communicator, self).__init__()
        self._stop_event = threading.Event()

        # internal request and response queues
        self.req_q: Queue = Queue()
        self.res_q: Queue = Queue()

        # dictionary of channel running status
        self.running: Dict[int, bool] = {}

        self.address = None

    def run(self):
        """Run continuously until threading.Event fires."""
        while not self._stop_event.is_set():
            self.loop()
        self.close()

    def query(self, cmd) -> str:
        """Place a query in the request queue and return the response."""
        self.requests.put(request)
        # H requests change device flow, needing a longer timeout
        if request.endswith('H'):
            time.sleep(0.5)
        return self.responses.get()

    def loop(self):
        """Do the repetitive work."""
        # deal with commands and queries found in the request queue
        if self.req_q.qsize():
            # disable asynchronous communication
            self.write('1xE0')
            self.read(1)
            # empty the ingoing buffer
            flush = self.read(100)
            if flush:
                logger.debug(f'flushed garbage before query: "{flush}"')
            # write command and get result
            cmd = self.req_q.get()
            self.write(cmd)
            res = self.readline()
            self.res_q.put(res)
            # enable asynchronous communication again
            self.write('1xE1')
            self.read(1)
        line = self.readline()
        if line:
            # check for running message
            if line[:2] == '^U':
                ch = int(line[2])
                self.running[ch] = True
            elif line[:2] == '^X':
                ch = int(line[2])
                self.running[ch] = False

    @abstractmethod
    def write(self, message):
        """Write a message to the device."""
        pass

    @abstractmethod
    def read(self, length):
        """Read a fixed number of bytes from the device."""
        pass

    @abstractmethod
    def readline(self):
        """Read until a LF terminator."""
        pass

    @abstractmethod
    def close(self):
        """Close the connection."""
        pass

    def join(self, timeout=None):
        """Stop the thread."""
        logger.debug('joining communications thread...')
        self._stop_event.set()
        super(Communicator, self).join(timeout)
        logger.debug('...done')


class SerialCommunicator(Communicator):
    """Communicator using a directly-connected RS232 serial device."""

    def __init__(self, address=None, baudrate=9600, data_bits=8, stop_bits=1,
                 parity='N', timeout=.05):
        """Initialize the serial link and create queues for commands and responses."""
        super(SerialCommunicator, self).__init__()
        self.serial_details = {'baudrate': baudrate,
                               'bytesize': data_bits,
                               'stopbits': stop_bits,
                               'parity': parity,
                               'timeout': timeout}
        self.address = address
        self.ser = serial.Serial(self.address, **self.serial_details)
    def write(self, message: str):
        """Write a message to the device."""
        self.ser.write(message.encode() + b'\r')

    def read(self, length: int):
        """Read a fixed number of bytes from the device."""
        return self.ser.read(length)

    def readline(self):
        """Read until a LF terminator."""
        self.ser.readline().strip()

    def write(self, message: str):
        """Write a message to the device."""
        self.ser.write(message.encode() + b'\r')

    def close(self):
        """Release resources."""
        self.ser.close()


class SocketCommunicator(Communicator):
    """Communicator using a TCP/IP<=>serial gateway."""

    def __init__(self, address, timeout=.1):
        """Initialize socket."""
        assert address.startswith('tcp://')
        super(SocketCommunicator, self).__init__()
        try:
            address, port = address.split(':')
        except ValueError:
            raise ValueError('address must be hostname:port')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((address, int(port)))
        self.timeout = timeout
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(address)

    def write(self, message: str):
        """Write a message to the device."""
        self.socket.send(message.encode() + b'\r')

    def read(self, length: int):
        """Read a fixed number of bytes from the device."""
        ready = select.select([self.socket], [], [], self.timeout)
        if ready[0]:
            return self.socket.recv(length).decode()
        return ''

    def readline(self):
        """Read until a LF terminator."""
        msg = ''
        t0 = time.time()
        while True:
            char = self.read(1)
            msg += char
            is_complete = char == '\n'
            is_timed_out = time.time() - t0 > self.timeout
            if is_complete or is_timed_out:
                break
        return msg.strip()

    def close(self):
        """Release resources."""
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class Mode(Enum):
    """Possible operating modes."""

    RPM = 'L'
    FLOWRATE = 'M'
    VOL_AT_RATE = 'O'
    VOL_OVER_TIME = 'G'
    VOL_PAUSE = 'Q'
    TIME = 'N'
    TIME_PAUSE = 'P'


class Setpoint(Enum):
    """Possible setpoint types."""

    RPM = '0'
    FLOWRATE = '1'


class Rotation(Enum):
    """Possible rotation directions."""

    CLOCKWISE = 'J'
    COUNTERCLOCKWISE = 'K'


def pack_time1(number, units='s') -> str:
    """Convert number to Ismatec Reglo ICC 'time type 1'.

    1-8 digits, 0 to 35964000 in units of 0.1s (0 to 999 hr)
    """
    unit_options = {
        's': 10,
        'm': 600,
        'h': 36000,
    }
    number = int(number * unit_options[units])
    return str(min(number, 35964000)).replace('.', '')


def pack_time2(number, units='s') -> str:
    """Convert number to Ismatec Reglo ICC 'time type 2'.

    8 digits, left padded, 0 to 35964000 in units of 0.1s (0 to 999 hr)
    """
    unit_options = {
        's': 10,
        'm': 600,
        'h': 36000,
    }
    number = int(number * unit_options[units])
    return str(min(number, 35964000)).replace('.', '').zfill(8)


def pack_volume1(number) -> str:
    """Convert number to Ismatec Reglo ICC 'volume type 1'.

    mmmmEse — Represents the scientific notation of m.mmm x 10se.
    For example, 1.200 x 10-2 is represented with 1200E-2. Note
    that the decimal point is inferred after the first character.
    """
    s = f'{abs(number):.3e}'
    return f'{s[0]}{s[2:5]}E{s[-3]}{s[-1]}'


def pack_volume2(number):
    """Convert number to Ismatec Reglo ICC 'volume type 2'.

    This is undocumented. It appears to be 'volume type 1' without
    the E, and can be mL or mL/min depending on use case.
    mmmmse — Represents the scientific notation of m.mmm x 10se.
    For example, 1.200 x 10-2 is represented with 1200-2. Note
    that the decimal point is inferred after the first character.
    """
    s = f'{abs(number):.3e}'
    return f'{s[0]}{s[2:5]}{s[-3]}{s[-1]}'


def pack_discrete2(number) -> str:
    """Convert number to Ismatec Reglo ICC 'discrete type 2'.

    Four characters representing a discrete integer value in base
    10. The value is right-justified. Unused digits to the left are
    zeros.
    """
    s = str(number).strip('0')
    whole, decimals = s.split('.')
    return '%04d' % int(whole + decimals)


def pack_discrete3(number) -> str:
    """Convert number to Ismatec Reglo ICC 'discrete type 3'.

    Six characters in base 10. The value is right-justified.
    Unused digits to the left are zeros.
    """
    assert 0 <= number < 1_000_000
    return str(number).zfill(6)


Tubing = [
    0.13, 0.19, 0.25, 0.38, 0.44, 0.51, 0.57, 0.64, 0.76, 0.89, 0.95, 1.02, 1.09,
    1.14, 1.22, 1.30, 1.43, 1.52, 1.65, 1.75, 1.85, 2.06, 2.29, 2.54, 2.79, 3.17
]
