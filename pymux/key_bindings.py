from __future__ import unicode_literals
from prompt_toolkit.document import Document
from prompt_toolkit.filters import HasFocus, Filter, Condition
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys

from .layout import focus_right, focus_left, focus_up, focus_down
from .enums import COMMAND

__all__ = (
    'create_key_bindings',
)

class HasPrefix(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        return self.pymux.get_client_state(cli).has_prefix


def create_key_bindings(pymux):
    has_prefix = HasPrefix(pymux)

    manager = KeyBindingManager(
        enable_all=HasFocus(COMMAND) & ~has_prefix,
        enable_auto_suggest_bindings=True)
    registry = manager.registry

    @registry.add_binding(Keys.Any, filter=~HasFocus(COMMAND) & ~has_prefix, invalidate_ui=False)
    def _(event):
        # NOTE: we don't invalidate the UI, because for pymux itself, nothing
        #       in the output changes yet. It's the application in the pane
        #       that will probably echo back the typed characters. When we
        #       receive them, they are draw to the UI and it's invalidated.
        data = event.data
        pane = pymux.arrangement.get_active_pane(event.cli)

        if pane.clock_mode:
            # Leave clock mode on key press.
            pane.clock_mode = False
            pymux.invalidate()
        else:
            process = pane.process

            # Applications like htop with run in application mode require the
            # following input.
            if process.screen.in_application_mode:
                data = {
                        Keys.Up: '\x1bOA',
                        Keys.Left: '\x1bOD',
                        Keys.Right: '\x1bOC',
                        Keys.Down: '\x1bOB',
                }.get(event.key_sequence[0].key, data)

            data = data.replace('\n', '\r')
            process.write_input(data)

    @registry.add_binding(Keys.BracketedPaste, filter=~HasFocus(COMMAND) & ~has_prefix, invalidate_ui=False)
    def _(event):
        " Pasting to active pane. "
        p = pymux.active_process_for_cli(event.cli)

        if p.screen.bracketed_paste_enabled:
            # When the process running in this pane understands bracketing paste.
            p.write_input('\x1b[200~' + event.data + '\x1b[201~')
        else:
            p.write_input(event.data)

    @registry.add_binding(Keys.ControlB, filter=~has_prefix)
    def _(event):
        " Enter prefix mode. "
        pymux.get_client_state(event.cli).has_prefix = True

    def prefix_binding(*a):
        def decorator(func):
            @registry.add_binding(*a, filter=has_prefix)
            def _(event):
                func(event)
                pymux.invalidate()  # Invalidate all clients, not just the current CLI.
                pymux.get_client_state(event.cli).has_prefix = False
            return func
        return decorator

    @prefix_binding(Keys.ControlB)
    def _(event):
        " Send Ctrl-B to active process. "
        pymux.active_process_for_cli(event.cli).write_input(event.data)

    @prefix_binding('"')
    def _(event):
        " Split horizontally. "
        pymux.add_process(event.cli)

    @prefix_binding('%')
    def _(event):
        " Split vertically. "
        pymux.add_process(event.cli, vsplit=True)

    @prefix_binding('c')
    def _(event):
        " Create window. "
        pymux.create_window(event.cli)

    @prefix_binding('n')
    def _(event):
        " Focus next window. "
        pymux.arrangement.focus_next_window(event.cli)

    @prefix_binding('p')
    def _(event):
        " Focus previous window. "
        pymux.arrangement.focus_previous_window(event.cli)

    @prefix_binding('o')
    def _(event):
        " Focus next pane. "
        pymux.arrangement.get_active_window(event.cli).focus_next()

    @prefix_binding('z')
    def _(event):
        " Zoom pane. "
        w = pymux.arrangement.get_active_window(event.cli)
        w.zoom = not w.zoom

    @prefix_binding(Keys.ControlL)
    @prefix_binding(Keys.Right)
    def _(event):
        " Focus right pane. "
        focus_right(pymux, event.cli)

    @prefix_binding(Keys.ControlH)
    @prefix_binding(Keys.Left)
    def _(event):
        " Focus left pane. "
        focus_left(pymux, event.cli)

    @prefix_binding(Keys.ControlJ)
    @prefix_binding(Keys.Down)
    def _(event):
        " Focus down. "
        focus_down(pymux, event.cli)

    @prefix_binding(Keys.ControlK)
    @prefix_binding(Keys.Up)
    def _(event):
        " Focus up. "
        focus_up(pymux, event.cli)

    @prefix_binding(':')
    def _(event):
        " Enter command mode. "
        event.cli.focus_stack.replace(COMMAND)

    @prefix_binding(';')
    def _(event):
        " Go to previous active pane. "
        w = pymux.arrangement.get_active_window(event.cli)
        prev_active_pane = w.previous_active_pane

        if prev_active_pane:
            w.active_pane = prev_active_pane

    @prefix_binding('l')
    def _(event):
        " Go to previous active window. "
        w = pymux.arrangement.get_previous_active_window(event.cli)

        if w:
            pymux.arrangement.set_active_window(event.cli, w)

    @prefix_binding(',')
    def _(event):
        " Rename window. "
        event.cli.focus_stack.replace(COMMAND)
        event.cli.buffers[COMMAND].document = Document(
            'rename-window %s' % pymux.arrangement.get_active_window(event.cli).name)

    @prefix_binding("'")
    def _(event):
        " Rename pane. "
        event.cli.focus_stack.replace(COMMAND)
        event.cli.buffers[COMMAND].document = Document(
            'rename-pane %s' % (pymux.arrangement.active_pane.name or ''))

    @prefix_binding("x")
    def _(event):
        " Kill pane. "
        event.cli.focus_stack.replace(COMMAND)
        event.cli.buffers[COMMAND].document = Document('send-signal kill')

    @prefix_binding('!')
    def _(event):
        " Break pane. "
        pymux.arrangement.break_pane(event.cli)

    @prefix_binding('d')
    def _(event):
        " Detach client. "
        pymux.detach_client(event.cli)

    @prefix_binding('t')
    def _(event):
        " Toggle clock mode. "
        pane = pymux.arrangement.get_active_pane(event.cli)
        if pane:
            pane.clock_mode = not pane.clock_mode

    @prefix_binding(' ')
    def _(event):
        " Select next layout. "
        w = pymux.arrangement.get_active_window(event.cli)
        if w:
            w.select_next_layout()

    @prefix_binding(Keys.ControlO)
    def _(event):
        " Rotate window. "
        pymux.arrangement.rotate_window(event.cli)

    @prefix_binding(Keys.Escape, 'o')
    def _(event):
        " Rotate window backwards. "
        pymux.arrangement.rotate_window(event.cli, count=-1)

    @prefix_binding(Keys.ControlZ)
    def _(event):
        " Suspend client. "
        connection = pymux.get_connection_for_cli(event.cli)
        if connection:
            connection.suspend_client_to_background()

    def create_focus_window_number_func(i):
        @prefix_binding('%s' % i)
        def _(event):
            " Focus window with this number. "
            try:
                pymux.arrangement.set_active_window(event.cli, pymux.arrangement.windows[i])
            except IndexError:
                pass

    for i in range(10):
        create_focus_window_number_func(i)

    @registry.add_binding(Keys.ControlC, filter=HasFocus(COMMAND) & ~has_prefix)
    @registry.add_binding(Keys.ControlG, filter=HasFocus(COMMAND) & ~has_prefix)
    @registry.add_binding(Keys.Backspace, filter=HasFocus(COMMAND) & ~has_prefix &
                          Condition(lambda cli: cli.buffers[COMMAND].text == ''))
    def _(event):
        " Leave command mode. "
        pymux.leave_command_mode(event.cli, append_to_history=False)

#    @registry.add_binding(Keys.F6)  # XXX: remove: this is for debugging only.
#    def _(event):
#        p = pymux.active_process_for_cli(event.cli)
#        p.slow_motion = not p.slow_motion

    @prefix_binding('k')
    def _(event):
        w = pymux.arrangement.get_active_window(event.cli)
        w.change_size_for_active_pane(up=2)

    @prefix_binding('j')
    def _(event):
        w = pymux.arrangement.get_active_window(event.cli)
        w.change_size_for_active_pane(down=2)

    @prefix_binding('h')
    def _(event):
        w = pymux.arrangement.get_active_window(event.cli)
        w.change_size_for_active_pane(left=2)

    @prefix_binding('l')
    def _(event):
        w = pymux.arrangement.get_active_window(event.cli)
        w.change_size_for_active_pane(right=2)

    @prefix_binding(Keys.Any)
    def _(event):
        " Ignore unknown Ctrl-B prefixed key sequences. "

    return registry
