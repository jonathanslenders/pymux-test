from __future__ import unicode_literals

from prompt_toolkit.terminal.vt100_input import raw_mode
from prompt_toolkit.eventloop.posix import _select, call_on_sigwinch
from prompt_toolkit.terminal.vt100_output import _get_size, Vt100_Output

import fcntl
import getpass
import glob
import json
import os
import socket
import sys


__all__ = (
    'Client',
    'list_clients',
)


class Client(object):
    def __init__(self, socket_name):
        self.socket_name = socket_name

        # Connect to socket.
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(socket_name)
        self.socket.setblocking(0)

    def run_command(self, command):
        self._send_packet({
            'cmd': 'run-command',
            'data': command,
        })

    def attach(self):
        """
        Attach client user interface.
        """
        self._send_size()
        self._send_packet({
            'cmd': 'start-gui',
            'data': ''
        })

        with raw_mode(sys.stdin.fileno()):
            data_buffer = b''

            stdin_fd = sys.stdin.fileno()
            socket_fd = self.socket.fileno()

            with call_on_sigwinch(lambda: self._send_size()):
                while True:
                    r, w, x = _select([stdin_fd, socket_fd], [], [])

                    if socket_fd in r:
                        data = self.socket.recv(1024)

                        if data == b'':
                            # End of file. Connection closed.
                            # Reset terminal
                            o = Vt100_Output.from_pty(sys.stdout)
                            o.quit_alternate_screen()
                            o.disable_mouse_support()
                            o.reset_attributes()
                            o.flush()
                            return
                        else:
                            data_buffer += data

                            while b'\0' in data_buffer:
                                pos = data_buffer.index(b'\0')
                                self._process(data_buffer[:pos])
                                data_buffer = data_buffer[pos + 1:]

                    elif stdin_fd in r:
                        self._process_stdin()

    def _process(self, data_buffer):
        packet = json.loads(data_buffer.decode('utf-8'))
        if packet['cmd'] == 'out':
            sys.stdout.write(packet['data'])
            sys.stdout.flush()

    def _process_stdin(self):
        with nonblocking(sys.stdin.fileno()):
            data = sys.stdin.read()

        self._send_packet({
            'cmd': 'in',
            'data': data,
        })

    def _send_packet(self, data):
        " Send to server. "
        data = json.dumps(data).encode('utf-8')

        self.socket.send(data + b'\0')

    def _send_size(self):
        rows, cols = _get_size(sys.stdout.fileno())
        self._send_packet({
            'cmd': 'size',
            'data': [rows, cols]
        })


class nonblocking(object):
    """
    Make fd non blocking.
    """
    def __init__(self, fd):
        self.fd = fd

    def __enter__(self):
        self.orig_fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)

    def __exit__(self, *args):
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl)


def list_clients():
    """
    List all the servers that are running.
    """
    for path in glob.glob('/tmp/pymux.sock.%s.*' % getpass.getuser()):
        try:
            yield Client(path)
        except socket.error:
            pass
