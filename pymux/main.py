from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.buffer_mapping import BufferMapping
from prompt_toolkit.enums import DUMMY_BUFFER
from prompt_toolkit.eventloop.callbacks import EventLoopCallbacks
from prompt_toolkit.eventloop.posix import PosixEventLoop
from prompt_toolkit.filters import Condition
from prompt_toolkit.focus_stack import FocusStack
from prompt_toolkit.input import PipeInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.vi_state import InputMode, ViState
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.terminal.vt100_output import Vt100_Output, _get_size
from prompt_toolkit.utils import Callback

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

        # True when the command prompt is visible.
        self.command_mode = False

        # When a "confirm-before" command is running,
        # Show this text in the command bar. When confirmed, execute
        # confirm_command.
        self.confirm_text = None
        self.confirm_command = None

        # When a "command-prompt" command is running.
        self.prompt_text = None
        self.prompt_command = None

        # Vi state. (Each client has its own state.)
        self.vi_state = ViState()


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
        self.enable_bell = True
        self.remain_on_exit = False
        self.status_keys_vi_mode = False
        self.mode_keys_vi_mode = False
        self.history_limit = 2000

        self.options = ALL_OPTIONS

        # When no panes are available.
        self.original_cwd = os.getcwd()

        self.display_pane_numbers = False

        #: List of clients.
        self._runs_standalone = False
        self.connections = []
        self.clis = {}  # Mapping from Connection to CommandLineInterface.

        self._startup_done = False
        self.source_file = source_file
        self.startup_command = startup_command

        # Keep track of all the panes, by ID. (For quick lookup.)
        self.panes_by_id = weakref.WeakValueDictionary()

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
            if self.enable_bell:
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

        # Keep track of panes. This is a WeakKeyDictionary, we only add, but
        # don't remove.
        self.panes_by_id[pane.pane_id] = pane

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

    def leave_command_mode(self, cli, append_to_history=False):
        cli.buffers[COMMAND].reset(append_to_history=append_to_history)
        cli.buffers[PROMPT].reset(append_to_history=True)

        client_state = self.get_client_state(cli)
        client_state.command_mode = False
        client_state.prompt_command = ''  # TODO: is this the right place to do this??
        client_state.confirm_command = ''

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
        def get_title():
            return self.get_title(cli)

        def on_focus_changed():
            """ When the focus changes to a read/write buffer, make sure to go
            to insert mode. This happens when the ViState was set to NAVIGATION
            in the copy buffer. """
            vi_state = self.key_bindings_manager.pt_key_bindings_manager.get_vi_state(cli)

            if cli.current_buffer.read_only():
                vi_state.input_mode = InputMode.NAVIGATION
            else:
                vi_state.input_mode = InputMode.INSERT

        application = Application(
            layout=self.layout_manager.layout,
            key_bindings_registry=self.key_bindings_manager.registry,
            buffers=_BufferMapping(self),
            focus_stack=_FocusStack(self, on_focus_changed=Callback(on_focus_changed)),
            mouse_support=Condition(lambda cli: self.enable_mouse_support),
            use_alternate_screen=True,
            style=self.style,
            get_title=get_title)

        cli = CommandLineInterface(
            application=application,
            output=output,
            input=input,
            eventloop=self.eventloop)

        application.focus_stack._cli = cli  # Tell _FocusStack about the CLI.

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


class _BufferMapping(BufferMapping):
    """
    Container for all the Buffer objects in a CommandLineInterface.
    """
    def __init__(self, pymux):
        self.pymux = pymux

        def _handle_command(cli, buffer):
            " When text is accepted in the command line. "
            text = buffer.text

            # First leave command mode. We want to make sure that the working
            # pane is focussed again before executing the command handers.
            pymux.leave_command_mode(cli, append_to_history=True)

            # Execute command.
            pymux.handle_command(cli, text)

        def _handle_prompt_command(cli, buffer):
            " When a command-prompt command is accepted. "
            text = buffer.text

            client_state = pymux.get_client_state(cli)
            pymux.handle_command(cli, client_state.prompt_command.replace('%%', text))

            pymux.leave_command_mode(cli, append_to_history=True)

        super(_BufferMapping, self).__init__({
            COMMAND: Buffer(
                complete_while_typing=True,
                completer=create_command_completer(pymux),
                accept_action=AcceptAction(handler=_handle_command),
                auto_suggest=AutoSuggestFromHistory(),
            ),
            PROMPT: Buffer(
                accept_action=AcceptAction(handler=_handle_prompt_command),
                auto_suggest=AutoSuggestFromHistory(),
            ),
        })

    def __getitem__(self, name):
        " Override __getitem__ to make lookup of pane- buffers dynamic. "
        if name.startswith('pane-'):
            try:
                id = int(name[len('pane-'):])
                return self.pymux.panes_by_id[id].copy_buffer
            except (ValueError, KeyError):
                raise KeyError
        elif name.startswith('search-'):
            try:
                id = int(name[len('search-'):])
                return self.pymux.panes_by_id[id].search_buffer
            except (ValueError, KeyError):
                raise KeyError
        else:
            return super(_BufferMapping, self).__getitem__(name)


class _FocusStack(FocusStack):
    def __init__(self, pymux, on_focus_changed=None):
        super(_FocusStack, self).__init__(on_focus_changed=on_focus_changed)

        self._cli = None
        self.pymux = pymux

    def _get_real_buffer_name(self):
        if self._cli:
            client_state = self.pymux.get_client_state(self._cli)

            # Confirm.
            if client_state.confirm_text:
                return DUMMY_BUFFER

            # Custom prompt.
            if client_state.prompt_command:
                return PROMPT

            # Command mode.
            if client_state.command_mode:
                return COMMAND

            # Copy/search mode.
            pane = self.pymux.arrangement.get_active_pane(self._cli)

            if pane and pane.copy_mode:
                if pane.is_searching:
                    return 'search-%i' % pane.pane_id
                else:
                    return 'pane-%i' % pane.pane_id

        return DUMMY_BUFFER

    @property
    def current(self):
        return self._get_real_buffer_name()

    @property
    def previous(self):
        return DUMMY_BUFFER

    def __contains__(self, value):  # XXX: cleanup. (We don't use this.)
        # When the copy/search buffer is in the stack.
        if self._cli:
            pane = self.pymux.arrangement.get_active_pane(self._cli)
            if pane and pane.copy_mode and value == 'pane-%i' % pane.pane_id:
                return True
            if pane and pane.is_searching and value == 'search-%i' % pane.pane_id:
                return True

        return super(_FocusStack, self).__contains__(value)

    def push(self, buffer_name, replace=False):  # XXX: cleanup: (We don't use this.)
        self._focus(buffer_name)
        super(_FocusStack, self).push(buffer_name, replace=replace)

    def _focus(self, buffer_name):
        if buffer_name.startswith('pane-') and self._cli:
            id = int(buffer_name[len('pane-'):])
            pane = self.pymux.panes_by_id[id]

            w = self.pymux.arrangement.get_active_window(self._cli)
            w.active_pane = pane


class DummyCallbacks(EventLoopCallbacks):
    " Required in order to call eventloop.run() without having a CLI instance. "
    def terminal_size_changed(self): pass
    def input_timeout(self): pass
    def feed_key(self, key): pass
