from __future__ import unicode_literals
import getpass
import json
import socket
import logging

from prompt_toolkit.layout.screen import Size
from prompt_toolkit.terminal.vt100_input import InputStream
from prompt_toolkit.terminal.vt100_output import Vt100_Output

__all__ = (
    'ServerConnection',
    'bind_socket',
)


class ServerConnection(object):
    def __init__(self, pymux, connection, client_address):
        self.pymux = pymux
        self.connection = connection
        self.client_address = client_address
        self.size = Size(rows=20, columns=80)
        self._closed = False

        self._recv_buffer = b''
        self.cli = None
        self._inputstream = InputStream(
            lambda key: self.cli.input_processor.feed_key(key))

        pymux.eventloop.add_reader(
            connection.fileno(), self._recv)

    def _recv(self):
        # Read next chunk.
        data = self.connection.recv(1024)

        if data == b'':
            # End of file. Close connection.
            self.detach_and_close()
        else:
            # Receive and process packets.
            self._recv_buffer += data

            while b'\0' in self._recv_buffer:
                pos = self._recv_buffer.index(b'\0')
                self._process(self._recv_buffer[:pos])
                self._recv_buffer = self._recv_buffer[pos + 1:]

    def _process(self, data):
        """
        Process packet received from client.
        """
        packet = json.loads(data.decode('utf-8'))

        # Handle commands.
        if packet['cmd'] == 'run-command':
            self.pymux.handle_command(packet['data'])  # XXX: pass "cli"

        # Handle stdin.
        elif packet['cmd'] == 'in':
            self._inputstream.feed(packet['data'])

        # Set size
        elif packet['cmd'] == 'size':
            data = packet['data']
            self.size = Size(rows=data[0], columns=data[1])
            self.pymux.invalidate()

        # Start GUI. (Create CommandLineInterface front-end for pymux.)
        elif packet['cmd'] == 'start-gui':
            output = Vt100_Output(_SocketStdout(self._send_packet),
                                  lambda: self.size)
            self.cli = self.pymux.create_cli(self, output)

    def _send_packet(self, data):
        try:
            self.connection.send(json.dumps(data).encode('utf-8') + b'\0')
        except socket.error:
            if not self._closed:
                self.detach_and_close()

    def detach_and_close(self):
        # Remove from Pymux.
        self.pymux.connections.remove(self)
        if self in self.pymux.clis:
            del self.pymux.clis[self]

        # Remove from eventloop.
        self.pymux.eventloop.remove_reader(self.connection.fileno())
        self.connection.close()

        self._closed = True


def bind_socket(socket_name=None):
    """
    Find a socket to listen on and return it.
    """
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    if socket_name:
        s.bind(socket_name)
        return socket_name, s
    else:
        i = 0
        while True:
            try:
                socket_name = '/tmp/pymux.sock.%s.%i' % (getpass.getuser(), i)
                s.bind(socket_name)
                return socket_name, s
            except (OSError, socket.error):
                i += 1

                # When 100 times failed, cancel server
                if i == 100:
                    logging.warning('100 times failed to listen on posix socket. Please clean up old sockets.') # XXXX
                    raise


class _SocketStdout(object):
    """
    Stdout-like object that writes everything through the unix socket to the
    client.
    """
    def __init__(self, send_packet):
        self.send_packet = send_packet
        self._buffer = []

    def write(self, data):
        self._buffer.append(data)

    def flush(self):
        data = {'cmd': 'out', 'data': ''.join(self._buffer)}
        self.send_packet(data)
        self._buffer = []
