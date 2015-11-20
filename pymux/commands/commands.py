from __future__ import unicode_literals
import signal

__all__ = (
    'has_command_handler',
    'call_command_handler',
)

COMMANDS_TO_HANDLERS = {}  # Global mapping of pymux commands to their handlers.


def has_command_handler(command):
    return command in COMMANDS_TO_HANDLERS


def call_command_handler(command, pymux, variables):
    """
    Execute command.
    """
    COMMANDS_TO_HANDLERS[command](pymux, variables)


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
        def command_wrapper(pymux, variables):
            func(pymux)

        return func
    return decorator

#
# The actual commands.
#

@_cmd('split')
def split(pymux, variables):
    executable = variables.get('executable')
    pymux.add_process(executable)


@_cmd('vsplit')
def vsplit(pymux, variables):
    executable = variables.get('executable')
    pymux.add_process(executable, vsplit=True)


@_cmd('new-window')
def new_window(pymux, variables):
    executable = variables.get('executable')
    pymux.create_window(executable)


@cmd('break-pane')
def break_pane(pymux):
    pymux.arrangement.break_pane()
    pymux.layout_manager.update()


@_cmd('rename-window')
def rename_window(pymux, variables):
    text = variables.get('text', '')
    pymux.arrangement.active_window.chosen_name = text


@_cmd('rename-pane')
def rename_pane(pymux, variables):
    text = variables.get('text', '')
    pymux.arrangement.active_pane.name = text


@_cmd('send-signal')
def send_signal(pymux, variables):
    try:
        signal = variables.get('signal', '')
    except ValueError:
        pass  # Invalid integer.
    else:
        value = SIGNALS.get(signal)
        if value:
            pymux.arrangement.active_pane.process.send_signal(value)
        else:
            pymux.show_message('Invalid signal')


SIGNALS = {
    'kill': signal.SIGKILL,
    'term': signal.SIGTERM,
    'usr1': signal.SIGUSR1,
    'usr2': signal.SIGUSR2,
    'hup': signal.SIGHUP,
}

