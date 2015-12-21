from __future__ import unicode_literals
from prompt_toolkit.filters import Filter

__all__ = (
    'HasPrefix',
    'WaitsForConfirmation',
    'InCommandMode',
    'WaitsForPrompt',
    'InCopyMode',
    'InCopyModeNotSearching',
    'InCopyModeSearching',
)


class HasPrefix(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        return self.pymux.get_client_state(cli).has_prefix


class WaitsForConfirmation(Filter):
    """
    Waiting for a yes/no key press.
    """
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        return bool(self.pymux.get_client_state(cli).confirm_command)


class InCommandMode(Filter):
    """
    When ':' has been pressed.'
    """
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        client_state = self.pymux.get_client_state(cli)
        return client_state.command_mode and not client_state.confirm_command


class WaitsForPrompt(Filter):
    """
    Waiting for input for a "command-prompt" command.
    """
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        client_state = self.pymux.get_client_state(cli)
        return bool(client_state.prompt_command) and not client_state.confirm_command


class InCopyMode(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        pane = self.pymux.arrangement.get_active_pane(cli)
        return pane.copy_mode


class InCopyModeNotSearching(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        pane = self.pymux.arrangement.get_active_pane(cli)
        return pane.copy_mode and not pane.is_searching


class InCopyModeSearching(Filter):
    def __init__(self, pymux):
        self.pymux = pymux

    def __call__(self, cli):
        pane = self.pymux.arrangement.get_active_pane(cli)
        return pane.copy_mode and pane.is_searching
