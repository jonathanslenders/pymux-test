from __future__ import unicode_literals
import signal

from pymux.layout import focus_right, focus_left, focus_up, focus_down
from pymux.arrangement import LayoutTypes

__all__ = (
    'has_command_handler',
    'call_command_handler',
)

COMMANDS_TO_HANDLERS = {}  # Global mapping of pymux commands to their handlers.


def has_command_handler(command):
    return command in COMMANDS_TO_HANDLERS


def call_command_handler(command, pymux, cli, variables):
    """
    Execute command.
    """
    COMMANDS_TO_HANDLERS[command](pymux, cli, variables)


def _cmd(name):
    " Base decorator for registering a command. "
    def decorator(func):
        COMMANDS_TO_HANDLERS[name] = func
        return func
    return decorator

def cmd(name):
    " Decorator for commands that don't take parameters. "
    def decorator(func):
        @_cmd(name)
        def command_wrapper(pymux, cli, variables):
            func(pymux, cli)

        return func
    return decorator

#
# The actual commands.
#

@_cmd('split')
def split(pymux, cli, variables):
    executable = variables.get('executable')
    pymux.add_process(cli, executable)


@_cmd('vsplit')
def vsplit(pymux, cli, variables):
    executable = variables.get('executable')
    pymux.add_process(cli, executable, vsplit=True)


@_cmd('new-window')
def new_window(pymux, cli, variables):
    executable = variables.get('executable')
    pymux.create_window(cli, executable)


@cmd('break-pane')
def break_pane(pymux, cli):
    pymux.arrangement.break_pane(cli)
    pymux.invalidate()


@_cmd('rename-window')
def rename_window(pymux, cli, variables):
    text = variables.get('text', '')
    pymux.arrangement.get_active_window(cli).chosen_name = text


@_cmd('rename-pane')
def rename_pane(pymux, cli, variables):
    text = variables.get('text', '')
    pymux.arrangement.get_active_pane(cli).name = text


@_cmd('select-pane')
def select_pane(pymux, cli, variables):
    direction = variables.get('direction', '')
    handlers = {
        '-L': focus_left,
        '-R': focus_right,
        '-U': focus_up,
        '-D': focus_down
    }
    if direction in handlers:
        handlers[direction](pymux, cli)
    else:
        pymux.show_message(cli, 'select-pane requires -R, -L, -U or -D as argument.')


@_cmd('rotate-window')
def rotate_window(pymux, cli, variables):
    pymux.arrangement.rotate_window(cli)


@_cmd('select-layout')
def select_layout(pymux, cli, variables):
    layout_type = variables.get('layout_type', '')

    if layout_type in LayoutTypes._ALL:
        pymux.arrangement.get_active_window(cli).select_layout(layout_type)
    else:
        pymux.show_message(cli, 'Invalid layout type.')


@_cmd('send-signal')
def send_signal(pymux, cli, variables):
    try:
        signal = variables.get('signal', '')
    except ValueError:
        pass  # Invalid integer.
    else:
        value = SIGNALS.get(signal)
        if value:
            pymux.arrangement.get_active_pane(cli).process.send_signal(value)
        else:
            pymux.show_message(cli, 'Invalid signal')


@_cmd('suspend-client')
def suspend_client(pymux, cli, variables):
    connection = pymux.get_connection_for_cli(cli)

    if connection:
        connection.suspend_client_to_background()

@_cmd('clock-mode')
def clock_mode(pymux, cli, variables):
    pane = pymux.arrangement.get_active_pane(cli)
    if pane:
        pane.clock_mode = not pane.clock_mode

@_cmd('next-layout')
def next_layout(pymux, cli, variables):
    " Select next layout. "
    pane = pymux.arrangement.get_active_window(cli)
    if pane:
        pane.select_next_layout()


SIGNALS = {
    'kill': signal.SIGKILL,
    'term': signal.SIGTERM,
    'usr1': signal.SIGUSR1,
    'usr2': signal.SIGUSR2,
    'hup': signal.SIGHUP,
}

