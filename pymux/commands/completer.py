from __future__ import unicode_literals

from prompt_toolkit.completion import Completer
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.completers.filesystem import ExecutableCompleter
from prompt_toolkit.contrib.completers import WordCompleter
from pygments.token import Token

from .grammar import COMMAND_GRAMMAR
from .commands import COMMANDS_TO_HANDLERS, SIGNALS

__all__ = ( 'create_command_completer', )


def create_command_completer(pymux):
    return GrammarCompleter(COMMAND_GRAMMAR, {
        #'executable': ExecutableCompleter(),
        'command': WordCompleter(sorted(COMMANDS_TO_HANDLERS.keys())),
        'signal': WordCompleter(sorted(SIGNALS.keys())),
    })
