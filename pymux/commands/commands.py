from __future__ import unicode_literals

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

@cmd('split')
def split(pymux):
    pymux.add_process()


@cmd('vsplit')
def vsplit(pymux):
    pymux.add_process(vsplit=True)


@cmd('new-window')
def new_window(pymux):
    pymux.create_window()


@_cmd('rename-window')
def rename_window(pymux, variables):
    text = variables.get('text', '')
    pymux.arrangement.active_window.chosen_name = text
