from __future__ import unicode_literals

from prompt_toolkit.contrib.regular_languages.compiler import compile


#: The compiled grammar for the Vim command line.
COMMAND_GRAMMAR = compile(r"""
    # Allow leading whitespace.
    \s*
    (
        # Commands accepting a location.
        (vsplit|split) \s+ (?P<executable>[^\s]+)     |

        # Any other normal command.
        (?P<command>[^\s]+) \s+  ([^\s]*)             |
        (?P<command>[^\s]+)
    )

    # Allow trailing space.
    \s*
""")
