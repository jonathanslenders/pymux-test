from __future__ import unicode_literals

from prompt_toolkit.contrib.regular_languages.compiler import compile


#: The compiled grammar for the Vim command line.
COMMAND_GRAMMAR = compile(r"""
    # Allow leading whitespace.
    \s*
    (
        # Commands accepting a location.
        (?P<command>vsplit|split) \s+ (?P<executable>[^\s]+)     |

        # Commands accepting a text.
        (?P<command>rename-window) \s+ (?P<text>.+)          |

        # Any other normal command.
        (?P<command>[^\s]+) \s+  ([^\s]*)             |
        (?P<command>[^\s]+)
    )

    # Allow trailing space.
    \s*
""")
