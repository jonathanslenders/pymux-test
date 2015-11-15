from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit.interface import CommandLineInterface

from .style import PymuxStyle
from .layout import LayoutManager
from .process import Process
from .key_bindings import create_key_bindings
from .arrangement import Arrangement, Pane

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
            if self.focussed_process:
                title = self.focussed_process.screen.title
            else:
                title = ''

            if title:
                return '{} - Pymux'.format(title)
            else:
                return 'Pymux'

        application = Application(
            layout=self.layout_manager.layout,
            key_bindings_registry=registry,
            buffers={
                'COMMAND': Buffer(
                    complete_while_typing=True,
                    completer=WordCompleter([
                    'new-window', 'kill-pane', 'rename-window'
                    'list-buffers', 'last-pane', 'list-sessions',
                    'kill-server', 'break-pane', 'rename-session',
                    'refresh-client', 'next-layout',
                ]))
            },
            mouse_support=True,
            use_alternate_screen=True,
            style=PymuxStyle(),
            get_title=get_title)

        self.cli = CommandLineInterface(application=application)

    @property
    def focussed_process(self):
        return self.arrangement.active_process

    def _create_pane(self):
        def done_callback():
            # Remove pane from layout.
            self.arrangement.remove_pane(pane)
#            self.arrangement.remove_dead_panes()
            self.layout_manager.update()

            # No panes left? -> Quit.
            if not self.arrangement.has_panes:
                self.cli.set_return_value(None)

        process = Process(self.cli, done_callback)
        pane = Pane(process)

        return pane

    def create_window(self):
        pane = self._create_pane()

        self.arrangement.create_window(pane)
        self.layout_manager.update()

    def add_process(self, vsplit=False):
        pane = self._create_pane()
        self.arrangement.active_window.add_pane(pane, vsplit=vsplit)
        self.layout_manager.update()

    def run(self):
        self.cli.run()
