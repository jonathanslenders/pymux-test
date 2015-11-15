from __future__ import unicode_literals
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import HasFocus
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys
from .layout import focus_right, focus_left, focus_up, focus_down

__all__ = (
    'create_key_bindings',
)


def create_key_bindings(pymux):
    manager = KeyBindingManager(
        enable_all=HasFocus('COMMAND'),
        enable_auto_suggest_bindings=True)
    registry = manager.registry

    @registry.add_binding(Keys.Any, filter=~HasFocus('COMMAND'), invalidate_ui=False)
    def _(event):
        # NOTE: we don't invalidate the UI, because for pymux itself, nothing
        #       in the output changes yet. It's the application in the pane
        #       that will probably echo back the typed characters. When we
        #       receive them, they are draw to the UI and it's invalidated.
        data = event.data

        # Applications like htop with run in application mode require the
        # following input.
        if pymux.active_process.screen.in_application_mode:
            data = {
                    Keys.Up: '\x1bOA',
                    Keys.Left: '\x1bOD',
                    Keys.Right: '\x1bOC',
                    Keys.Down: '\x1bOB',
            }.get(event.key_sequence[0].key, data)

        pymux.active_process.write_input(data)

    @registry.add_binding(Keys.ControlB, Keys.ControlB)
    def _(event):
        " Send Ctrl-B to active process. "
        pymux.active_process.write_input(event.data)

    @registry.add_binding(Keys.ControlB, '"')
    def _(event):
        " Split horizontally. "
        pymux.add_process()

    @registry.add_binding(Keys.ControlB, '%')
    def _(event):
        " Split vertically. "
        pymux.add_process(vsplit=True)

    @registry.add_binding(Keys.ControlB, 'c')
    def _(event):
        " Create window. "
        pymux.create_window()

    @registry.add_binding(Keys.ControlB, 'n')
    def _(event):
        " Focus next window. "
        pymux.arrangement.focus_next_window()
        pymux.layout_manager.update()

    @registry.add_binding(Keys.ControlB, 'p')
    def _(event):
        " Focus previous window. "
        pymux.arrangement.focus_previous_window()
        pymux.layout_manager.update()

    @registry.add_binding(Keys.ControlB, 'o')
    def _(event):
        " Focus next pane. "
        pymux.arrangement.active_window.focus_next()


    @registry.add_binding(Keys.ControlB, 'z')
    def _(event):
        " Zoom pane. "
        w = pymux.arrangement.active_window
        w.zoom = not w.zoom
        pymux.layout_manager.update()

    @registry.add_binding(Keys.ControlB, Keys.ControlL)
    @registry.add_binding(Keys.ControlB, Keys.Right)
    def _(event):
        " Focus right pane. "
        focus_right(pymux)

    @registry.add_binding(Keys.ControlB, Keys.ControlH)
    @registry.add_binding(Keys.ControlB, Keys.Left)
    def _(event):
        " Focus left pane. "
        focus_left(pymux)

    @registry.add_binding(Keys.ControlB, Keys.ControlJ)
    @registry.add_binding(Keys.ControlB, Keys.Down)
    def _(event):
        " Focus down. "
        focus_down(pymux)

    @registry.add_binding(Keys.ControlB, Keys.ControlK)
    @registry.add_binding(Keys.ControlB, Keys.Up)
    def _(event):
        " Focus up. "
        focus_up(pymux)

    @registry.add_binding(Keys.ControlB, ':')
    def _(event):
        " Enter command mode. "
        pymux.cli.focus_stack.replace('COMMAND')

    @registry.add_binding(Keys.ControlB, ';')
    def _(event):
        " Go to previous active pane. "
        w = pymux.arrangement.active_window
        prev_active_pane = w.previous_active_pane

        if prev_active_pane:
            w.active_pane = prev_active_pane

    @registry.add_binding(Keys.ControlB, ',')
    def _(event):
        " Rename window. "
        pymux.cli.focus_stack.replace('COMMAND')
        pymux.cli.buffers['COMMAND'].document = Document(
            'rename-window %s' % pymux.arrangement.active_window.name)

    def create_focus_window_number_func(i):
        @registry.add_binding(Keys.ControlB, '%s' % i)
        def _(event):
            " Focus window with this number. "
            try:
                pymux.arrangement.active_window = pymux.arrangement.windows[i]
            except IndexError:
                pass

    for i in range(10):
        create_focus_window_number_func(i)

    @registry.add_binding(Keys.ControlC, filter=HasFocus('COMMAND'))
    @registry.add_binding(Keys.ControlG, filter=HasFocus('COMMAND'))
    def _(event):
        " Leave command mode. "
        pymux.leave_command_mode(append_to_history=False)

    @registry.add_binding(Keys.ControlB, Keys.Any)
    def _(event):
        " Ignore unknown Ctrl-B prefixed key sequences. "

    return registry
