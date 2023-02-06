"""Serial or Socket (serial gateway) interfaces for Ismatec Reglo ICC peristaltic pump."""
import threading
from queue import Queue
import serial
import socket
import time
import select


class Communicator(threading.Thread):
    """Class representing the hardware interface to the Ismatec Reglo ICC peristaltic pump.

    It handles the communication via direct serial or through a serial server, and keeps track
    of the messy mix of synchronous (command) and asynchronous (status) communication.
    """

    def __init__(self, debug=False, address=None,
                 baudrate=9600, data_bits=8, stop_bits=1, parity='N', timeout=.05):
        """Initialize the serial link and create queues for commands and responses."""
        super(Communicator, self).__init__()
        self._stop_event = threading.Event()

        # internal request and response queues
        self.req_q = Queue()
        self.res_q = Queue()

        # dictionary of channel running status
        self.running = {}

        # parse options
        self.do_debug = debug
        self.address = address
        self.serial_details = {'baudrate': baudrate,
                               'bytesize': data_bits,
                               'stopbits': stop_bits,
                               'parity': parity,
                               'timeout': timeout}

        # initialize communication
        self.init()

    def setRunningStatus(self, status, channel):
        """Manually set running status."""
        if type(channel) == list or type(channel) == tuple:
            self.debug('manually setting running status %s on channels %s' % (status, channel))
            for ch in channel:
                self.running[ch] = status
        elif channel == 0:
            self.debug('manually setting running status %s on all channels (found %s)' %
                       (status, list(self.running.keys())))
            for ch in list(self.running.keys()):
                self.running[ch] = status
        else:
            self.debug('manually setting running status %s on channel %d' % (status, channel))
            self.running[channel] = status

    def run(self):
        """Run continuously until threading.Event fires."""
        while not self._stop_event.isSet():
            self.loop()
        self.close()

    def command(self, cmd):
        """Place a command in the request queue and return the response."""
        self.debug("writing command '%s' to %s" % (cmd, self.address))
        self.req_q.put(cmd)
        result = self.res_q.get()
        if result == '*':
            return True
        else:
            self.debug('WARNING: command %s returned %s' % (cmd, result))
            return False

    def query(self, cmd):
        """Place a query in the request queue and return the response."""
        self.debug("writing query '%s' to %s" % (cmd, self.address))
        self.req_q.put(cmd)
        result = self.res_q.get().strip()
        self.debug("got response '%s'" % result)
        return result

    def init(self):
        """Override in subclass."""
        raise NotImplementedError

    def loop(self):
        """Override in subclass."""
        raise NotImplementedError

    def close(self):
        """Override in subclass."""
        raise NotImplementedError

    def join(self, timeout=None):
        """Stop the thread."""
        self.debug('joining communications thread...')
        self._stop_event.set()
        super(Communicator, self).join(timeout)
        self.debug('...done')

    def debug(self, msg):
        """Print debug info."""
        if self.do_debug:
            print(msg)


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
            self.ser.command(b'1xE0\r')
            self.ser.read(size=1)
            # empty the ingoing buffer
            flush = self.ser.read(100)
            if flush:
                self.debug('flushed garbage before query: "%s"' % flush)
            # write command and get result
            cmd = self.que_q.get()
            self.ser.command(cmd + b'\r')
            res = self.ser.readline().strip()
            self.res_q.put(res)
            # enable asynchronous communication again
            self.ser.command(b'1xE1\r')
            self.ser.read(size=1)
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
                self.debug('flushed garbage before query: "%s"' % flush)
            # write command and get result
            cmd = self.req_q.get()
            self.socket.send(cmd + b'\r')
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
                self.debug('received message: "%s"' % line)

    def close(self):
        """Release resources."""
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
