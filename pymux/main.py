from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.eventloop.callbacks import EventLoopCallbacks
from prompt_toolkit.eventloop.posix import PosixEventLoop
from prompt_toolkit.input import PipeInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.terminal.vt100_output import Vt100_Output, _get_size

from .arrangement import Arrangement, Pane
from .commands.completer import create_command_completer
from .commands.handler import handle_command
from .key_bindings import create_key_bindings
from .layout import LayoutManager
from .process import Process
from .server import ServerConnection, bind_socket
from .style import PymuxStyle

import getpass
import os
import pwd
import sys
import traceback

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
        self.has_prefix = False   # XXX: this should be for each client individually!!!!

        #: Error/info message
        self.message = None   # XXX: this should be for each client individually.

        # When no panes are available
        self.original_cwd = os.getcwd()

        #: List of clients.
        self._runs_standalone = False
        self.connections = []
        self.clis = {}  # Mapping from Connection to CommandLineInterface.

        # Socket information.
        self.socket = None
        self.socket_name = None

        # Create eventloop.
        self.eventloop = PosixEventLoop()

        self.registry = create_key_bindings(self)

        self.style = PymuxStyle()

    @property
    def active_process(self):
        return self.arrangement.active_process

    def get_title(self):
        if self.active_process:
            title = self.active_process.screen.title
        else:
            title = ''

        if title:
            return '{} - Pymux'.format(title)
        else:
            return 'Pymux'

    def get_window_size(self):
        rows = [c.size.rows for c in self.connections if c.cli]
        columns = [c.size.columns for c in self.connections if c.cli]

        if self._runs_standalone:
            r, c = _get_size(sys.stdout.fileno())
            rows.append(r)
            columns.append(c)

        if rows and columns:
            return Size(rows=min(rows) - 1, columns=min(columns))
        else:
            return Size(rows=20, columns=80)

    def _create_pane(self, command=None):
        def done_callback():
            # Remove pane from layout.
            self.arrangement.remove_pane(pane)
            self.layout_manager.update()

            # No panes left? -> Quit.
            if not self.arrangement.has_panes:
                self.eventloop.stop()

        # When the path of the active process is known,
        # start the new process at the same location.
        if self.active_process:
            path = self.active_process.get_cwd()
        else:
            path = None

        def before_exec():
            " Called in the process fork. "
            if path:
                os.chdir(path)
            else:
                os.chdir(self.original_cwd)

            # Make sure to set the PYMUX environment variable.
            if self.socket_name:
                os.environ['PYMUX'] = self.socket_name

        if command:
            command = command.split()
        else:
            command = [self._get_default_shell()]

        process = Process.from_command(
                self.eventloop, self.invalidate, command, done_callback,
                before_exec_func=before_exec)
        pane = Pane(process)

        return pane

    def invalidate(self):
        for c in self.clis.values():
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

    @classmethod
    def leave_command_mode(cls, cli, append_to_history=False):
        cli.buffers['COMMAND'].reset(append_to_history=append_to_history)
        cli.focus_stack.replace(DEFAULT_BUFFER)

    def handle_command(self, command):
        handle_command(self, command)

    def show_message(self, message):
        """
        Set a warning message. This will be shown at the bottom until a key has
        been pressed.
        """
        self.message = message

    def create_cli(self, connection, output):
        """
        Create `CommandLineInterface` instance for this connection.
        """
        def _handle_command(cli, buffer):
            " When text is accepted in the command line. "
            text = buffer.text

            # First leave command mode. We want to make sure that the working
            # pane is focussed again before executing the command handers.
            self.leave_command_mode(cli, append_to_history=True)

            # Execute command.
            self.handle_command(text)

        application = Application(
            layout=self.layout_manager.layout,
            key_bindings_registry=self.registry,
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
            style=self.style,
            get_title=self.get_title)

        cli = CommandLineInterface(
            application=application,
            output=output,
            eventloop=self.eventloop)

        # Hide message when a key has been pressed.
        def key_pressed():
            self.message = None
        cli.input_processor.beforeKeyPress += key_pressed

        cli._is_running = True

        self.clis[connection] = cli

        # Redraw all CLIs. (Adding a new client could mean that the others
        # change size, so everything has to be redrawn.)
        self.invalidate()

        return cli

    def get_connection_for_cli(self, cli):
        """
        Return the `CommandLineInterface` instance for this connection, if any.
        `None` otherwise.
        """
        for connection, c in self.clis.items():
            if c == cli:
                return connection

    def detach_client(self, cli):
        """
        Detach the client that belongs to this CLI.
        """
        connection = self.get_connection_for_cli(cli)

        if connection is not None:
            connection.detach_and_close()

        # Redraw all clients -> Maybe their size has to change.
        self.invalidate()

    def listen_on_socket(self, socket_name=None):
        """
        Listen for clients on a unix socket.
        Returns the socket name.
        """
        if self.socket is None:
            self.socket_name, self.socket = bind_socket(socket_name)
            self.socket.listen(0)
            self.socket.setblocking(0)
            self.eventloop.add_reader(self.socket.fileno(), self._socket_accept)

        return self.socket_name

    def _socket_accept(self):
        """
        Accept connection from client.
        """
        connection, client_address = self.socket.accept()
        connection.setblocking(0)

        connection = ServerConnection(self, connection, client_address)
        self.connections.append(connection)

    def run_server(self):
        # Run eventloop.

        # XXX: Both the PipeInput and DummyCallbacks are not used.
        #      This is a workaround to run the PosixEventLoop continiously
        #      without having a CommandLineInterface instance.
        #      A better API in prompt_toolkit is desired.
        try:
            self.eventloop.run(
                PipeInput(), DummyCallbacks())
        except:
            # When something bad happens, always dump the traceback.
            # (Otherwise, when running as a daemon, and stdout/stderr are not
            # available, it's hard to see what went wrong.)
            with open('/tmp/pymux.crash', 'wb') as f:
                f.write(traceback.format_exc().encode('utf-8'))
            raise

        # Clean up socket.
        os.remove(self.socket_name)

    def run_standalone(self):
        self._runs_standalone = True
        cli = self.create_cli(connection=None, output=Vt100_Output.from_pty(sys.stdout))
        cli._is_running = False
        cli.run()


class DummyCallbacks(EventLoopCallbacks):
    " Required in order to call eventloop.run() without having a CLI instance. "
    def terminal_size_changed(self): pass
    def input_timeout(self): pass
    def feed_key(self, key): pass
