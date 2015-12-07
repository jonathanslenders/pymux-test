from __future__ import unicode_literals

from .grammar import COMMAND_GRAMMAR
from .commands import has_command_handler, call_command_handler

import shlex

__all__ = ('handle_command', )


def handle_command(pymux, cli, input_string):
    " Handle command. "
    parts = shlex.split(input_string)
    call_command_handler(parts[0], pymux, cli, parts[1:])
