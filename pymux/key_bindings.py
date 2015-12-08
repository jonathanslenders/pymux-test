from __future__ import unicode_literals
from prompt_toolkit.document import Document
from prompt_toolkit.filters import HasFocus, Filter, Condition
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys

from .enums import COMMAND
from .commands.handler import handle_command

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


    pymux_commands = {
            '"': 'split-window -v',
            '%': 'split-window -h',
            'c': 'new-window',
            'z': 'resize-pane -Z',
            Keys.Right: 'select-pane -R',
            Keys.Left: 'select-pane -L',
            Keys.Down: 'select-pane -D',
            Keys.Up: 'select-pane -U',
            Keys.ControlL: 'select-pane -R',
            Keys.ControlH: 'select-pane -L',
            Keys.ControlJ: 'select-pane -D',
            Keys.ControlK: 'select-pane -U',
            ';': 'last-pane',
            '!': 'break-pane',
            'd': 'detach-client',
            't': 'clock-mode',
            ' ': 'next-layout',
            Keys.ControlZ: 'suspend-client',
            'k': 'resize-pane -U 5',
            'j': 'resize-pane -D 5',
            'h': 'resize-pane -L 5',
            'l': 'resize-pane -R 5',
            ':': 'command-prompt',
            '0': 'select-window -t :0',
            '1': 'select-window -t :1',
            '2': 'select-window -t :2',
            '3': 'select-window -t :3',
            '4': 'select-window -t :4',
            '5': 'select-window -t :5',
            '6': 'select-window -t :6',
            '7': 'select-window -t :7',
            '8': 'select-window -t :8',
            '9': 'select-window -t :9',
            'n': 'next-window',
            'p': 'previous-window',
            'o': 'select-pane -t :.+',  # Focus next pane.
            '{': 'swap-pane -U',
            '}': 'swap-pane -D',
            Keys.ControlO: 'rotate-window',
            (Keys.Escape, 'o'): 'rotate-window -D',

            (Keys.Escape, '1'): 'select-layout even-horizontal',
            (Keys.Escape, '2'): 'select-layout even-vertical',
            (Keys.Escape, '3'): 'select-layout main-horizontal',
            (Keys.Escape, '4'): 'select-layout main-vertical',
            (Keys.Escape, '5'): 'select-layout tiled',
    }

    def bind_command(keys, command):
        @prefix_binding(*keys)
        def _(event):
            handle_command(pymux, event.cli, command)

    for keys, command in pymux_commands.items():
        if not isinstance(keys, tuple):
            keys = (keys,)
        bind_command(keys, command)

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
            'rename-pane %s' % (pymux.arrangement.get_active_pane(event.cli).name or ''))

    @prefix_binding("x")
    def _(event):
        " Kill pane. "
        event.cli.focus_stack.replace(COMMAND)
        event.cli.buffers[COMMAND].document = Document('send-signal kill')

    @registry.add_binding(Keys.ControlC, filter=HasFocus(COMMAND) & ~has_prefix)
    @registry.add_binding(Keys.ControlG, filter=HasFocus(COMMAND) & ~has_prefix)
    @registry.add_binding(Keys.Backspace, filter=HasFocus(COMMAND) & ~has_prefix &
                          Condition(lambda cli: cli.buffers[COMMAND].text == ''))
    def _(event):
        " Leave command mode. "
        pymux.leave_command_mode(event.cli, append_to_history=False)

    @prefix_binding(Keys.Any)
    def _(event):
        " Ignore unknown Ctrl-B prefixed key sequences. "

    return registry
