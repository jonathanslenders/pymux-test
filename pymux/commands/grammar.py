from __future__ import unicode_literals

from prompt_toolkit.contrib.regular_languages.compiler import compile


# The grammar for the command line.
# This is only used for autocompletion and syntax highlighting.
COMMAND_GRAMMAR = compile(r"""
    # Allow leading whitespace.
    \s*
    (
        # Commands accepting a location.
        new-window \s+ (?P<executable>.+)     |

        # Commands accepting a text.
        (rename-window|rename-pane) \s+ (?P<text>.+)  |

        # split:  -h/-v
        split-window \s+ ((?P<horizontal_or_vertical>-[hv]+) \s+)? (?P<executable>[^-].*)? |

        # select-pane:  -R/-L/-U/-D.
        select-pane \s+ (?P<direction>-[LRUD]+)     |
        resize-pane \s+ (?P<direction>-[LRUD]+)     |

        # select-layout
        select-layout \s+ (?P<layout_type>[^\s]+)   |

        # Commands accepting signals.
        send-signal \s+ (?P<signal>[^\s]+)          |

        # bind-key
        bind-key \s+ (?P<key_name>[^\s]+)             |
        bind-key \s+ [^\s]+ \s+ (?P<command>[^\s]+)   |

        # send-keys
        send-keys \s+ (?P<key_name>[^\s]+)             |

        # Any other normal command.
        (?P<command>[^\s]+) \s+  ([^\s]*)                        |
        (?P<command>[^\s]+)
    )

    # Allow trailing space.
    \s*
""")
