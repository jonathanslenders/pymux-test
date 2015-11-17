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

        application = Application(
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

        self.cli = CommandLineInterface(application=application)

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
            self.cli, command, done_callback)
        pane = Pane(process)

        return pane

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

    def run(self):
        self.cli.run()
