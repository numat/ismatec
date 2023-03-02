"""Transports and Protocol for Ismatec Reglo ICC peristaltic pump.

Distributed under the GNU General Public License v3
Copyright (C) 2022 NuMat Technologies
"""
import logging
import select
import socket
import threading
import time
from abc import abstractmethod
from queue import Queue

import serial

logger = logging.getLogger('ismatec')


class Communicator(threading.Thread):
    """Interface to the Ismatec Reglo ICC peristaltic pump.

    It handles the communication via direct serial or through a serial
    server, and keeps track of the messy mix of synchronous (command)
    and asynchronous (status) communication.
    """

    def __init__(self, address=None, baudrate=9600, data_bits=8, stop_bits=1,
                 parity='N', timeout=.05):
        """Initialize the serial link and create queues for commands and responses."""
        super(Communicator, self).__init__()
        self._stop_event = threading.Event()

        # internal request and response queues
        self.req_q = Queue()
        self.res_q = Queue()

        # dictionary of channel running status
        self.running = {}

        # parse options
        self.address = address
        self.serial_details = {'baudrate': baudrate,
                               'bytesize': data_bits,
                               'stopbits': stop_bits,
                               'parity': parity,
                               'timeout': timeout}

        # initialize communication
        self.init()

    def set_running_status(self, status, channel):
        """Manually set running status."""
        if type(channel) == list or type(channel) == tuple:
            logger.debug(f'manually setting running status {status} on channels {channel}')
            for ch in channel:
                self.running[ch] = status
        elif channel == 0:
            logger.debug(f'manually setting running status {status} on all channels (found %s)' %
                         list(self.running.keys()))
            for ch in list(self.running.keys()):
                self.running[ch] = status
        else:
            logger.debug(f'manually setting running status {status} on channel {channel}')
            self.running[channel] = status

    def run(self):
        """Run continuously until threading.Event fires."""
        while not self._stop_event.is_set():
            self.loop()
        self.close()

    def command(self, cmd):
        """Place a command in the request queue and return the response."""
        logger.debug(f"writing command '{cmd}' to {self.address}")
        self.req_q.put(cmd)
        if len(cmd) > 1 and cmd[-1] in ['H']:
            time.sleep(0.5)
        result = self.res_q.get()
        if result == '*':
            return True
        else:
            logger.debug(f'WARNING: command {cmd} returned {result}')
            return False

    def query(self, cmd):
        """Place a query in the request queue and return the response."""
        logger.debug(f"writing query '{cmd}' to {self.address}")
        self.req_q.put(cmd)
        result = self.res_q.get().strip()
        logger.debug(f"got response '{result}'")
        return result

    @abstractmethod
    def init(self):
        """Override in subclass."""
        pass

    @abstractmethod
    def loop(self):
        """Override in subclass."""
        pass

    @abstractmethod
    def close(self):
        """Override in subclass."""
        pass

    def join(self, timeout=None):
        """Stop the thread."""
        logger.debug('joining communications thread...')
        self._stop_event.set()
        super(Communicator, self).join(timeout)
        logger.debug('...done')


class SerialCommunicator(Communicator):
    """Communicator using a directly-connected RS232 serial device."""

    def init(self):
        """Initialize serial port."""
        assert type(self.address) == str
        self.ser = serial.Serial(self.address, **self.serial_details)

    def loop(self):
        """Do the repetitive work."""
        # deal with commands and queries found in the request queue
        if self.req_q.qsize():
            # disable asynchronous communication
            self.command(b'1xE0\r')
            self.ser.read(1)
            # empty the ingoing buffer
            flush = self.ser.read(100)
            if flush:
                logger.debug(f'flushed garbage before query: "{flush!r}"')
            # write command and get result
            cmd = self.req_q.get()
            self.command(cmd.encode() + b'\r')
            res = self.ser.readline().strip()
            self.res_q.put(res)
            # enable asynchronous communication again
            self.command(b'1xE1\r')
            self.ser.read(1)
        line = self.ser.readline()
        if len(line):
            # check for running message
            if line[:2] == '^U':
                ch = int(line[2])
                self.running[ch] = True
            elif line[:2] == '^X':
                ch = int(line[2])
                self.running[ch] = False

    def close(self):
        """Release resources."""
        self.ser.close()


class SocketCommunicator(Communicator):
    """Communicator using a TCP/IP<=>serial gateway."""

    def init(self):
        """Initialize socket."""
        assert type(self.address) == tuple
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(self.address)

    def timeout_recv(self, size):
        """Receive <size> characters from the socket, with a timeout."""
        ready = select.select([self.socket], [], [], self.serial_details['timeout'])
        if ready[0]:
            # decode from bytes to str (default ASCII)
            return self.socket.recv(size).decode()
        return ''

    def readline(self):
        r"""Read serial characters continuously until \r\n or *."""
        msg = ''
        t0 = time.time()
        while True:
            char = self.timeout_recv(1)
            msg += char
            if msg.endswith('\r\n') or msg.endswith('*'):
                break
            if time.time() - t0 > self.serial_details['timeout']:
                break
        return msg

    def loop(self):
        """Do the repetitive work."""
        # deal with commands and queries found in the request queue
        if self.req_q.qsize():
            # disable asynchronous communication
            self.socket.send(b'1xE0\r')
            self.timeout_recv(1)
            # empty the ingoing buffer
            flush = self.timeout_recv(100)
            if flush:
                logger.debug(f'flushed garbage before query: "{flush}"')
            # write command and get result
            cmd = self.req_q.get()
            self.socket.send(cmd.encode() + b'\r')
            res = self.readline().strip()
            self.res_q.put(res)
            # enable asynchronous communication again
            self.socket.send(b'1xE1\r')
            self.timeout_recv(1)
        line = self.readline()
        if line:
            # check for running message
            try:
                if line[:2] == '^U':
                    ch = int(line[2])
                    self.running[ch] = True
                elif line[:2] == '^X':
                    ch = int(line[2])
                    self.running[ch] = False
            except IndexError:
                logger.debug(f'received message: "{line}"')

    def close(self):
        """Release resources."""
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class Protocol:
    """Convert to various (dumb) datatypes used for the protocol."""

    requests = {
        'pump version': '1#',
        'protocol version': '1x!',
        'set flow rate': '{channel}f{flow_v2}',
        'get flow rate': '{channel}f',
        'get mode': '{channel}xM',
        'set mode': ...

    }
    responses = {
        'setpoint': {
            '0': 'rpm',
            '1': 'flow rate',
        },
        'rotation': {
            'J': 'clockwise',
            'K': 'counterclockwise',
        },
        'mode': {
            'G': 'vol over time',
            'L': 'rpm',
            'M': 'flow rate',
            'N': 'time',
            'O': 'vol at rate',
            'P': 'time pause',
            'Q': 'vol pause',
        },
    }
    tubing = [
        0.13, 0.19, 0.25, 0.38, 0.44, 0.51, 0.57, 0.64, 0.76, 0.89, 0.95, 1.02, 1.09,
        1.14, 1.22, 1.30, 1.43, 1.52, 1.65, 1.75, 1.85, 2.06, 2.29, 2.54, 2.79, 3.17
    ]

    def _time1(self, number, units='s'):
        """Convert number to 'time type 1'.

        1-8 digits, 0 to 35964000 in units of 0.1s (0 to 999 hr)
        """
        unit_options = {
            's': 10,
            'm': 600,
            'h': 36000,
        }
        number = int(number * unit_options[units])
        return str(min(number, 35964000)).replace('.', '')

    def _time2(self, number, units='s'):
        """Convert number to 'time type 2'.

        This is an 8-digit left-padded version of `_time1`.
        """
        return self._time1(number, units).zfill(8)

    def _volume1(self, number):
        """Convert number to 'volume type 1'.

        mmmmEse — Represents the scientific notation of m.mmm x 10se.
        For example, 1.200 x 10-2 is represented with 1200E-2. Note
        that the decimal point is inferred after the first character.
        """
        s = f'{abs(number):.3e}'
        return f'{s[0]}{s[2:5]}E{s[-3]}{s[-1]}'

    def _volume2(self, number):
        """Convert number to 'volume type 2'.

        This is undocumented. It appears to be 'volume type 1' without
        the E, and can be mL or mL/min depending on use case.
        """
        return self._volume1(number).replace('E', '')

    def _discrete2(self, number):
        """Convert number to 'discrete type 2'.

        Four characters representing a discrete integer value in base
        10. The value is right-justified. Unused digits to the left are
        zeros.
        """
        assert 0 <= number < 10_000
        return str(number).zfill(4)

    def _discrete3(self, number):
        """Convert number to 'discrete type 3'.

        Six characters in base 10. The value is right-justified.
        Unused digits to the left are zeros.
        """
        assert 0 <= number < 1_000_000
        return str(number).zfill(6)
