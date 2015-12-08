from __future__ import unicode_literals
from prompt_toolkit.filters import Filter

__all__ = (
    'HasPrefix',
    'WaitsForConfirmation',
)


class HasPrefix(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        return self.pymux.get_client_state(cli).has_prefix


class WaitsForConfirmation(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        return bool(self.pymux.get_client_state(cli).confirm_command)
