from __future__ import unicode_literals

from .grammar import COMMAND_GRAMMAR
from .commands import has_command_handler, call_command_handler

__all__ = ('handle_command', )


def handle_command(pymux, cli, input_string):
    " Handle command. "

    m = COMMAND_GRAMMAR.match(input_string)
    if m is None:
        return

    variables = m.variables()
    command = variables.get('command')

    if has_command_handler(command):
        call_command_handler(command, pymux, cli, variables)
    else:
        pymux.show_message(cli, 'Invalid command: %s' % input_string)
