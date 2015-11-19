from __future__ import unicode_literals

from prompt_toolkit.terminal.vt100_input import raw_mode
from prompt_toolkit.eventloop.posix import _select, call_on_sigwinch
from prompt_toolkit.terminal.vt100_output import _get_size

import socket
import select
import json
import sys
import os
import fcntl
import signal


stdin = os.fdopen(0, 'rb', 0)

class Client(object):
    def __init__(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect('/tmp/test8.sock')
        s.setblocking(0)

        s.send(json.dumps({
            #'cmd': 'run-command',
            #'data': 'vsplit',
            #'cmd': 'c',
            #'data': 'vsplit',
            'cmd': 'start-gui',
            'data': '',
        }).encode('utf-8'))
        s.send(b'\0')

        self.socket = s

    def run(self):
        data_buffer = b''
        print('running')

        stdin_fd = stdin.fileno()
        socket_fd = self.socket.fileno()
        self.sigwinch()

        with call_on_sigwinch(self.sigwinch):
            while True:
                r, w, x = _select([stdin_fd, socket_fd], [], [])

                if socket_fd in r:
                    data = self.socket.recv(1024)

                    if data == b'':
                        # End of file. Connection closed.
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
        data = stdin.read()
        self._send_packet({
            'cmd': 'in',
            'data': data.decode('utf-8')
        })

    def _send_packet(self, data):
        " Send to server. "
        data = json.dumps(data).encode('utf-8')
        assert b'\0' not in data

        self.socket.send(data)
        self.socket.send(b'\0')

    def sigwinch(self, *a):
        rows, cols = _get_size(sys.stdout.fileno())
        self._send_packet({
            'cmd': 'size',
            'data': [rows, cols]
        })

class nonblocking(object):
    def __init__(self, stream):
        self.stream = stream
        self.fd = self.stream.fileno()
    def __enter__(self):
        self.orig_fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)
    def __exit__(self, *args):
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl)

import os



with raw_mode(sys.stdin.fileno()):
        with nonblocking(sys.stdin):
            Client().run()
