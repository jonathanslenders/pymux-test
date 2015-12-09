from __future__ import unicode_literals

from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.completers.filesystem import ExecutableCompleter
from prompt_toolkit.contrib.completers import WordCompleter

from .grammar import COMMAND_GRAMMAR
from .commands import COMMANDS_TO_HANDLERS, SIGNALS
from pymux.arrangement import LayoutTypes
from pymux.key_mappings import PYMUX_TO_PROMPT_TOOLKIT_KEYS

import shlex

__all__ = ( 'create_command_completer', )


def create_command_completer(pymux):
    return GrammarCompleter(COMMAND_GRAMMAR, {
        #'executable': ExecutableCompleter(),
        'command': WordCompleter(sorted(COMMANDS_TO_HANDLERS.keys()), ignore_case=True, WORD=True),
        'signal': WordCompleter(sorted(SIGNALS.keys()), ignore_case=True),
        'direction': WordCompleter(sorted(['-L', '-R', '-U', '-D']), WORD=True),
        'horizontal_or_vertical': WordCompleter(sorted(['-h', '-v']), WORD=True),
        'layout_type': WordCompleter(sorted(LayoutTypes._ALL), WORD=True),
        'key_name': WordCompleter(sorted(PYMUX_TO_PROMPT_TOOLKIT_KEYS.keys()), ignore_case=True, WORD=True),
    })
