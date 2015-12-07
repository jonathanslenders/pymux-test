from __future__ import unicode_literals

from .grammar import COMMAND_GRAMMAR
from .commands import has_command_handler, call_command_handler

import shlex

__all__ = ('handle_command', )


def handle_command(pymux, cli, input_string):
    " Handle command. "
    try:
        parts = shlex.split(input_string)
    except ValueError as e:
        # E.g. missing closing quote.
        pymux.show_message(cli, 'Invalid command: %s' % e)
    else:
        call_command_handler(parts[0], pymux, cli, parts[1:])
