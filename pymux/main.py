from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.eventloop.callbacks import EventLoopCallbacks
from prompt_toolkit.eventloop.posix import PosixEventLoop
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import PipeInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.terminal.vt100_output import Vt100_Output, _get_size

from .arrangement import Arrangement, Pane
from .commands.completer import create_command_completer
from .commands.commands import handle_command, call_command_handler
from .enums import COMMAND, PROMPT
from .key_bindings import KeyBindingsManager
from .rc import STARTUP_COMMANDS
from .layout import LayoutManager
from .log import logger
from .process import Process
from .server import ServerConnection, bind_socket
from .style import PymuxStyle
from .options import ALL_OPTIONS

import getpass
import os
import pwd
import signal
import sys
import traceback
import weakref

__all__ = (
    'Pymux',
)


class ClientState(object):
    """
    State information that is independent for each client.
    """
    def __init__(self):
        #: True when the prefix key (Ctrl-B) has been pressed.
        self.has_prefix = False

        #: Error/info message.
        self.message = None

        # When a "confirm-before" command is running,
        # Show this text in the command bar. When confirmed, execute
        # confirm_command.
        self.confirm_text = None
        self.confirm_command = None

        # When a "command-prompt" command is running.
        self.prompt_text = None
        self.prompt_command = None


class Pymux(object):
    """
    The main Pymux application class.

    Usage:

        p = Pymux()
        p.listen_on_socket()
        p.run_server()

    Or:

        p = Pymux()
        p.run_standalone()
    """
    def __init__(self, source_file=None, startup_command=None):
        self.arrangement = Arrangement()
        self.layout_manager = LayoutManager(self)

        self._client_states = weakref.WeakKeyDictionary()  # Mapping from CLI to ClientState.

        # Options
        self.enable_mouse_support = True
        self.enable_status = True
        self.remain_on_exit = False

        self.options = ALL_OPTIONS

        # When no panes are available.
        self.original_cwd = os.getcwd()

        #: List of clients.
        self._runs_standalone = False
        self.connections = []
        self.clis = {}  # Mapping from Connection to CommandLineInterface.

        self._startup_done = False
        self.source_file = source_file
        self.startup_command = startup_command

        # Socket information.
        self.socket = None
        self.socket_name = None

        # Create eventloop.
        self.eventloop = PosixEventLoop()

        # Key bindings manager.
        self.key_bindings_manager = KeyBindingsManager(self)

        self.style = PymuxStyle()

    def active_process_for_cli(self, cli):
        w = self.arrangement.get_active_window(cli)
        if w:
            return w.active_process

    def get_client_state(self, cli):
        """
        Return the ClientState instance for this CommandLineInterface.
        """
        try:
            return self._client_states[cli]
        except KeyError:
            s = ClientState()
            self._client_states[cli] = s
            return s

    def get_title(self, cli):
        p = self.active_process_for_cli(cli)
        if p:
            title = p.screen.title
        else:
            title = ''

        if title:
            return '{} - Pymux'.format(title)
        else:
            return 'Pymux'

    def get_window_size(self, cli):
        """
        Get the size to be used for the DynamicBody.
        This will be the smallest size of all clients.
        """
        get_active_window = self.arrangement.get_active_window
        active_window = get_active_window(cli)

        # Get connections watching the same window.
        connections = [c for c in self.connections if
                       c.cli and get_active_window(c.cli) == active_window]

        rows = [c.size.rows for c in connections]
        columns = [c.size.columns for c in connections]

        if self._runs_standalone:
            r, c = _get_size(sys.stdout.fileno())
            rows.append(r)
            columns.append(c)

        if rows and columns:
            return Size(rows=min(rows) - (1 if self.enable_status else 0),
                        columns=min(columns))
        else:
            return Size(rows=20, columns=80)

    def _create_pane(self, window=None, command=None, start_directory=None):
        def done_callback():
            if not self.remain_on_exit:
                # Remove pane from layout.
                self.arrangement.remove_pane(pane)

                # No panes left? -> Quit.
                if not self.arrangement.has_panes:
                    self.eventloop.stop()

            self.invalidate()

        def bell():
            " Sound bell on all clients. "
            for c in self.clis.values():
                c.output.bell()

        # Start directory.
        if start_directory:
            path = start_directory
        elif window and window.active_process:
            # When the path of the active process is known,
            # start the new process at the same location.
            path = window.active_process.get_cwd()
        else:
            path = None

        def before_exec():
            " Called in the process fork. "
            try:
                os.chdir(path or self.original_cwd)
            except OSError:
                pass  # No such file or directory.

            # Make sure to set the PYMUX environment variable.
            if self.socket_name:
                os.environ['PYMUX'] = '%s,%i' % (
                    self.socket_name, pane.pane_id)

        if command:
            command = command.split()
        else:
            command = [self._get_default_shell()]

        process = Process.from_command(
                self.eventloop, self.invalidate, command, done_callback,
                bell_func=bell,
                before_exec_func=before_exec)
        pane = Pane(process)

        logger.info('Created process %r.', command)
        process.start()

        return pane

    def invalidate(self):
        for c in self.clis.values():
            c.invalidate()

    def _get_default_shell(self):
        username = getpass.getuser()
        shell = pwd.getpwnam(username).pw_shell
        return shell

    def create_window(self, cli=None, command=None, start_directory=None):
        pane = self._create_pane(None, command, start_directory=start_directory)

        self.arrangement.create_window(cli, pane)
        self.invalidate()

    def add_process(self, cli, command=None, vsplit=False, start_directory=None):
        window = self.arrangement.get_active_window(cli)

        pane = self._create_pane(window, command, start_directory=start_directory)
        window.add_pane(pane, vsplit=vsplit)
        self.invalidate()

    def kill_pane(self, pane):
        assert isinstance(pane, Pane)

        # Send kill signal.
        if not pane.process.is_terminated:
            pane.process.send_signal(signal.SIGKILL)

        # Remove from layout.
        self.arrangement.remove_pane(pane)

        # No panes left? -> Quit.
        if not self.arrangement.has_panes:
            self.eventloop.stop()

    @classmethod
    def leave_command_mode(cls, cli, append_to_history=False):
        cli.buffers[COMMAND].reset(append_to_history=append_to_history)
        cli.buffers[PROMPT].reset(append_to_history=True)

        cli.focus_stack.replace(DEFAULT_BUFFER)

    def handle_command(self, cli, command):
        handle_command(self, cli, command)

    def show_message(self, cli, message):
        """
        Set a warning message. This will be shown at the bottom until a key has
        been pressed.
        """
        self.get_client_state(cli).message = message

    def create_cli(self, connection, output, input=None):
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
            self.handle_command(cli, text)

        def _handle_prompt_command(cli, buffer):
            " When a command-prompt command is accepted. "
            text = buffer.text

            self.leave_command_mode(cli, append_to_history=True)

            client_state = self.get_client_state(cli)
            self.handle_command(cli, client_state.prompt_command.replace('%%', text))

        def get_title():
            return self.get_title(cli)

        application = Application(
            layout=self.layout_manager.layout,
            key_bindings_registry=self.key_bindings_manager.registry,
            buffers={
                COMMAND: Buffer(
                    complete_while_typing=True,
                    completer=create_command_completer(self),
                    accept_action=AcceptAction(handler=_handle_command),
                    auto_suggest=AutoSuggestFromHistory(),
                ),
                PROMPT: Buffer(
                    accept_action=AcceptAction(handler=_handle_prompt_command),
                    auto_suggest=AutoSuggestFromHistory(),
                ),
            },
            mouse_support=Condition(lambda cli: self.enable_mouse_support),
            use_alternate_screen=True,
            style=self.style,
            get_title=get_title)

        cli = CommandLineInterface(
            application=application,
            output=output,
            input=input,
            eventloop=self.eventloop)

        # Hide message when a key has been pressed.
        def key_pressed():
            self.get_client_state(cli).message = None
        cli.input_processor.beforeKeyPress += key_pressed

        cli._is_running = True

        self.clis[connection] = cli

        # Redraw all CLIs. (Adding a new client could mean that the others
        # change size, so everything has to be redrawn.)
        self.invalidate()

        # Handle start-up comands.
        # (Does initial key bindings.)
        if not self._startup_done:
            self._startup_done = True

            # Execute default config.
            for cmd in STARTUP_COMMANDS.splitlines():
                self.handle_command(cli, cmd)

            # Source the given file.
            if self.source_file:
                call_command_handler('source-file', self, cli, [self.source_file])

            # Make sure that there is one window created.
            self.create_window(cli, command=self.startup_command)

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
        Listen for clients on a Unix socket.
        Returns the socket name.
        """
        if self.socket is None:
            self.socket_name, self.socket = bind_socket(socket_name)
            self.socket.listen(0)
            self.eventloop.add_reader(self.socket.fileno(), self._socket_accept)

        logger.info('Listening on %r.' % self.socket_name)
        return self.socket_name

    def _socket_accept(self):
        """
        Accept connection from client.
        """
        logger.info('Client attached.')

        connection, client_address = self.socket.accept()
        # Note: We don't have to put this socket in non blocking mode.
        #       This can cause crashes when sending big packets on OS X.

        connection = ServerConnection(self, connection, client_address)
        self.connections.append(connection)

    def run_server(self):
        # Ignore keyboard. (When people run "pymux server" and press Ctrl-C.)
        # Pymux has to be terminated by termining all the processes running in
        # its panes.
        def handle_sigint(*a):
            print('Ignoring keyboard interrupt.')

        signal.signal(signal.SIGINT, handle_sigint)

        # Run eventloop.

        # XXX: Both the PipeInput and DummyCallbacks are not used.
        #      This is a workaround to run the PosixEventLoop continuously
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
        """
        Run pymux standalone, rather than using a client/server architecture.
        This is mainly useful for debugging.
        """
        self._runs_standalone = True
        cli = self.create_cli(connection=None, output=Vt100_Output.from_pty(sys.stdout))
        cli._is_running = False
        cli.run()


class DummyCallbacks(EventLoopCallbacks):
    " Required in order to call eventloop.run() without having a CLI instance. "
    def terminal_size_changed(self): pass
    def input_timeout(self): pass
    def feed_key(self, key): pass
