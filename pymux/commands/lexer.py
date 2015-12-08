#from __future__ import unicode_literals
#
#from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
#from prompt_toolkit.layout.lexers import SimpleLexer
#from pygments.token import Token
#
#from .grammar import COMMAND_GRAMMAR
#
#__all__ = ('create_command_lexer',)
#
#
#def create_command_lexer(pymux):
#    return GrammarLexer(COMMAND_GRAMMAR, default_token=Token.CommandLine, lexers={
#        'executable': SimpleLexer(Token.CommandLine.Executable),
#        'text': SimpleLexer(Token.CommandLine.Text),
#        'command': SimpleLexer(Token.CommandLine.Command),
#    })
