from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
import six

from .key_mappings import PYMUX_TO_PROMPT_TOOLKIT_KEYS, pymux_key_to_prompt_toolkit_key_sequence

__all__ = (
    'Option',
    'SetOptionError',
    'OnOffOption',
    'ALL_OPTIONS',
)


class Option(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def get_all_values(self):
        """ Return a list of strings, with all possible values. (For
        autocompletion.) """

    @abstractmethod
    def set_value(self):
        " Set option. This can raise SetOptionError. "


class SetOptionError(Exception):
    def __init__(self, message):
        self.message = message


class OnOffOption(Option):
    def __init__(self, attribute):
        self.attribute = attribute

    def get_all_values(self, pymux):
        return ['on', 'off']

    def set_value(self, pymux, value):
        value = value.lower()

        if value in ('on', 'off'):
            setattr(pymux, self.attribute, (value == 'on'))
        else:
            raise SetOptionError('Expecting "yes" or "no".')


class KeyPrefixOption(Option):
    def get_all_values(self, pymux):
        return PYMUX_TO_PROMPT_TOOLKIT_KEYS.keys()

    def set_value(self, pymux, value):
        # Translate prefix to prompt_toolkit
        keys = pymux_key_to_prompt_toolkit_key_sequence(value)
        pymux.key_bindings_manager.prefix = keys


class BaseIndexOption(Option):
    " Base index for window numbering. "
    def get_all_values(self, pymux):
        return ['0', '1']

    def set_value(self, pymux, value):
        try:
            value = int(value)
        except ValueError:
            raise SetOptionError('Expecting an integer.')
        else:
            pymux.arrangement.base_index = value


class KeysOption(Option):
    " Emacs or Vi mode. "
    def __init__(self, property_name):
        self.property_name = property_name

    def get_all_values(self, pymux):
        return ['emacs', 'vi']

    def set_value(self, pymux, value):
        if value in ('emacs', 'vi'):
            setattr(pymux, self.property_name, value == 'vi')
        else:
            raise SetOptionError('Expecting "vi" or "emacs".')


class HistoryLimitOption(Option):
    " Change the history limit. "
    def get_all_values(self, pymux):
        return ['200', '500', '1000', '2000', '5000', '10000']

    def set_value(self, pymux, value):
        try:
            pymux.history_limit = int(value)
        except ValueError:
            raise SetOptionError('Expecting an integer.')


class DefaultTerminalOption(Option):
    def get_all_values(self, pymux):
        return ['xterm', 'xterm-256color', 'screen']

    def set_value(self, pymux, value):
        pymux.default_terminal = value


ALL_OPTIONS = {
    'base-index': BaseIndexOption(),
    'bell': OnOffOption('enable_bell'),
    'history-limit': HistoryLimitOption(),
    'mouse': OnOffOption('enable_mouse_support'),
    'prefix': KeyPrefixOption(),
    'remain-on-exit': OnOffOption('remain_on_exit'),
    'status': OnOffOption('enable_status'),
    'status-keys': KeysOption('status_keys_vi_mode'),
    'mode-keys': KeysOption('mode_keys_vi_mode'),
    'default-terminal': DefaultTerminalOption(),
}
