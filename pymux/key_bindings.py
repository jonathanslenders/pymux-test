from __future__ import unicode_literals
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import HasFocus
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys

__all__ = (
    'create_key_bindings',
)


def create_key_bindings(pymux):
    manager = KeyBindingManager(enable_all=HasFocus('COMMAND'))
    registry = manager.registry

    @registry.add_binding(Keys.Any, filter=~HasFocus('COMMAND'), invalidate_ui=False)
    def _(event):
        data = event.data

        # Applications like htop with run in application mode require the
        # following input.
        if pymux.focussed_process.screen.in_application_mode:
            data = {
                    Keys.Up: '\x1bOA',
                    Keys.Left: '\x1bOD',
                    Keys.Right: '\x1bOC',
                    Keys.Down: '\x1bOB',
            }.get(event.key_sequence[0].key, data)

        pymux.focussed_process.write_input(data)

    @registry.add_binding(Keys.ControlB, Keys.ControlB)
    def _(event):
        " Send Ctrl-B to active process. "
        pymux.focussed_process.write_input(event.data)

    @registry.add_binding(Keys.ControlB, '%')
    def _(event):
        " Split vertically. "
        pymux.add_process()

    @registry.add_binding(Keys.ControlB, Keys.ControlL)
    def _(event):
        " Focus next pane. "
        new_index = (pymux.processes.index(pymux.focussed_process) + 1) % len(pymux.processes)
        pymux.focussed_process = pymux.processes[new_index]

    @registry.add_binding(Keys.ControlB, Keys.ControlH)
    def _(event):
        " Focus previous pane. "
        new_index = (pymux.processes.index(pymux.focussed_process) - 1) % len(pymux.processes)
        pymux.focussed_process = pymux.processes[new_index]

    @registry.add_binding(Keys.ControlB, ':')
    def _(event):
        " Enter command mode. "
        pymux.cli.focus_stack.replace('COMMAND')

    @registry.add_binding(Keys.ControlC, filter=HasFocus('COMMAND'))
    @registry.add_binding(Keys.ControlG, filter=HasFocus('COMMAND'))
    def _(event):
        " Leave command mode. "
        pymux.cli.buffers['COMMAND'].document = Document()
        pymux.cli.focus_stack.replace(DEFAULT_BUFFER)

    @registry.add_binding(Keys.ControlB, Keys.Any)
    def _(event):
        " Ignore unknown Ctrl-B prefixed key sequences. "

    return registry
