from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.interface import CommandLineInterface

from .arrangement import Arrangement, Pane
from .commands.completer import create_command_completer
from .commands.handler import handle_command
from .key_bindings import create_key_bindings
from .layout import LayoutManager
from .process import Process
from .style import PymuxStyle

import os
import getpass
import pwd

__all__ = (
    'Pymux',
)


class Pymux(object):
    """
    The main Pymux application class.
    """
    def __init__(self):
        self.arrangement = Arrangement()
        self.layout_manager = LayoutManager(self)

        #: True when the prefix key (Ctrl-B) has been pressed.
        self.has_prefix = False

        #: Error/info message
        self.message = None

        #: List of clients.
        self.connections = []

        # Create eventloop.
        self.eventloop = PosixEventLoop()

        registry = create_key_bindings(self)

        def get_title():
            if self.active_process:
                title = self.active_process.screen.title
            else:
                title = ''

            if title:
                return '{} - Pymux'.format(title)
            else:
                return 'Pymux'

        def _handle_command(cli, buffer):
            " When text is accepted in the command line. "
            text = buffer.text

            # First leave command mode. We want to make sure that the working
            # pane is focussed again before executing the command handers.
            self.leave_command_mode(append_to_history=True)

            # Execute command.
            self.handle_command(text)

        self.application = Application(
            layout=self.layout_manager.layout,
            key_bindings_registry=registry,
            buffers={
                'COMMAND': Buffer(
                    complete_while_typing=True,
                    completer=create_command_completer(self),
                    accept_action=AcceptAction(handler=_handle_command),
                    auto_suggest=AutoSuggestFromHistory(),
                )
            },
            mouse_support=True,
            use_alternate_screen=True,
            style=PymuxStyle(),
            get_title=get_title)

        self.cli = CommandLineInterface(application=self.application)

        # Hide message when a key has been pressed.
        def key_pressed():
            self.message = None
        self.cli.input_processor.beforeKeyPress += key_pressed

    @property
    def active_process(self):
        return self.arrangement.active_process

    def _create_pane(self, command=None):
        def done_callback():
            # Remove pane from layout.
            self.arrangement.remove_pane(pane)
            self.layout_manager.update()

            # No panes left? -> Quit.
            if not self.arrangement.has_panes:
                self.cli.set_return_value(None)

        # When the path of the active process is known,
        # start the new process at the same location.
        if self.active_process:
            path = self.active_process.get_cwd()
            if path:
                os.chdir(path)

        if command:
            command = command.split()
        else:
            command = [self._get_default_shell()]

        process = Process.from_command(
                self.eventloop, self.invalidate, command, done_callback)
        pane = Pane(process)

        return pane

    def invalidate(self):
        for c in self.connections:
            c.invalidate()

    def _get_default_shell(self):
        username = getpass.getuser()
        shell = pwd.getpwnam(username).pw_shell
        return shell

    def create_window(self, command=None):
        pane = self._create_pane(command)

        self.arrangement.create_window(pane)
        self.layout_manager.update()

    def add_process(self, command=None, vsplit=False):
        pane = self._create_pane(command)
        self.arrangement.active_window.add_pane(pane, vsplit=vsplit)
        self.layout_manager.update()

    def leave_command_mode(self, append_to_history=False):
        self.cli.buffers['COMMAND'].reset(append_to_history=append_to_history)
        self.cli.focus_stack.replace(DEFAULT_BUFFER)

    def handle_command(self, command):
        handle_command(self, command)

    def show_message(self, message):
        """
        Set a warning message. This will be shown at the bottom until a key has
        been pressed.
        """
        self.message = message

    def run(self):
        self.cli.run()

    # ---

    def run(self):
        # Add socket interface to eventloop.
        self._socket_name, self._socket = bind_socket('/tmp/test8.sock')
        self._socket.listen(5)  # Listen for incoming connections.
        self._socket.setblocking(0)
        self.eventloop.add_reader(self._socket.fileno(), self._socket_accept)

        # Run eventloop.
        self.eventloop.run(StdinInput(sys.stdin), DummyCallbacks())  # XXX: don't pass stdin here.

    def _socket_accept(self):
        connection, client_address = self._socket.accept()
        connection.setblocking(0)

        connection = ServerConnection(self, connection, client_address)
        self.connections.append(connection)

    def create_cli(self, output):
        """
        Run front-end. (There can be several CommandLineInterface instances
        active. -- One for each client.)
        """
        cli = CommandLineInterface(
            application=self.application,
            output=output,
            eventloop=self.eventloop)

        # Hide message when a key has been pressed.
        def key_pressed():
            self.message = None
        cli.input_processor.beforeKeyPress += key_pressed

        cli._is_running = True
        cli.invalidate()

        return cli



import socket
import json
import sys
from prompt_toolkit.eventloop.callbacks import EventLoopCallbacks
from prompt_toolkit.eventloop.posix import PosixEventLoop
from prompt_toolkit.input import StdinInput
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.terminal.vt100_input import InputStream
from prompt_toolkit.terminal.vt100_output import Vt100_Output


class DummyCallbacks(EventLoopCallbacks):
    " Required in order to call eventloop.run() without CLI instance. "
    def terminal_size_changed(self): pass
    def input_timeout(self): pass
    def feed_key(self, key): pass


class ServerConnection(object):
    def __init__(self, pymux, connection, client_address):
        self.pymux = pymux
        self.connection = connection
        self.client_address = client_address
        self.size = Size(rows=20, columns=80)

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
            self.pymux.cli.eventloop.remove_reader(self.connection.fileno())
            self.connection.close()
        else:
            # Receive and process packets.
            self._recv_buffer += data

            while b'\0' in self._recv_buffer:
                pos = self._recv_buffer.index(b'\0')
                self._process(self._recv_buffer[:pos])
                self._recv_buffer = self._recv_buffer[pos + 1:]

    def invalidate(self):
        " Invalidate client. "
        if self.cli:
            self.cli.invalidate()

    def _process(self, data):
        """
        Process packet received from client.
        """
        packet = json.loads(data.decode('utf-8'))

        # Handle commands.
        if packet['cmd'] == 'run-command':
            self.pymux.handle_command(packet['data'])

        # Handle stdin.
        elif packet['cmd'] == 'in':
            self._inputstream.feed(packet['data'])

        # Set size
        elif packet['cmd'] == 'size':
            data = packet['data']
            self.size = Size(rows=data[0], columns=data[1])
            self.cli.invalidate()

        # Start GUI. (Create CommandLineInterface front-end for pymux.)
        elif packet['cmd'] == 'start-gui':
            output = Vt100_Output(SocketStdout(self.connection),
                                  lambda: self.size)
            self.cli = self.pymux.create_cli(output)


def bind_socket(socket_name=None):
    """
    Find a socket to listen on.
    Returns the socket.
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
            except OSError:
                i += 1

                # When 100 times failed, cancel server
                if i == 100:
                    logging.warning('100 times failed to listen on posix socket. Please clean up old sockets.') # XXXX
                    raise


class SocketStdout(object):
    def __init__(self, socket):
        self.socket = socket
        self._buffer = []

    def write(self, data):
        self._buffer.append(data)

    def flush(self):
        data = {'cmd': 'out', 'data': ''.join(self._buffer)}
        self.socket.send(json.dumps(data).encode('utf-8') + b'\0')
        self._buffer = []
