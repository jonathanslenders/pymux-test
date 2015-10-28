from __future__ import unicode_literals

#from prompt_toolkit.shortcuts import create_asyncio_eventloop
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit.interface import CommandLineInterface

from .style import PymuxStyle
from .layout import LayoutManager
from .process import Process
from .key_bindings import create_key_bindings


class PyMux(object):
    def __init__(self):
        self.pymux_layout = LayoutManager(self)

        registry = create_key_bindings(self)

        application = Application(
            layout=self.pymux_layout.layout,
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
            style=PymuxStyle())

        self.cli = CommandLineInterface(application=application,
                                        )#eventloop=create_asyncio_eventloop())

        self.processes = []
        self.focussed_process = None

    def add_process(self):
        process = Process(self.cli, self.cli.invalidate)
        self.focussed_process = process

        self.processes.append(process)
        self.pymux_layout.update()

        def wait_for_finished():
            " Wait for PID in executor. "
            process.waitpid()
            self.cli.eventloop.call_from_executor(done)

        def done():
            " PID received. Back in the main thread. "
            self.processes.remove(process)

            if self.processes:
                # Processes left.
                if self.focussed_process == process:
                    self.focussed_process = self.processes[-1]

                self.pymux_layout.update()

            else:
                # When no processes are left -> exit.
                self.cli.set_return_value(None)

        self.cli.eventloop.run_in_executor(wait_for_finished)

    def run(self):
        self.cli.run()

        #import asyncio
        #loop=asyncio.get_event_loop()
        #loop.run_until_complete(self.cli.run_async())

