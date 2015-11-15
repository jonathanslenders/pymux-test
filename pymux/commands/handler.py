from __future__ import unicode_literals

from .grammar import COMMAND_GRAMMAR
from .commands import has_command_handler, call_command_handler

__all__ = ('handle_command', )


def handle_command(pymux, input_string):
    " Handle command. "

    m = COMMAND_GRAMMAR.match(input_string)
    if m is None:
        return

    variables = m.variables()
    command = variables.get('command')

    if has_command_handler(command):
        call_command_handler(command, pymux, variables)
    else:
        pass  # TODO: show message
        #pymux.show_message('Invalid command: %s' % input_string)
