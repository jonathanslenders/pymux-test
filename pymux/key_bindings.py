from __future__ import unicode_literals
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import HasFocus, Condition
from prompt_toolkit.key_binding.manager import KeyBindingManager as pt_KeyBindingManager
from prompt_toolkit.keys import Keys

from .enums import COMMAND, PROMPT
from .filters import WaitsForConfirmation, HasPrefix
from .key_mappings import pymux_key_to_prompt_toolkit_key_sequence
from .commands.commands import call_command_handler

import six

__all__ = (
    'KeyBindingsManager',
)

has_pane_buffer_focus = Condition(lambda cli: cli.focus_stack.current.startswith('pane-'))


class KeyBindingsManager(object):
    """
    Pymux key binding manager.
    """
    def __init__(self, pymux):
        self.pymux = pymux

        # Start from this KeyBindingManager from prompt_toolkit, to have basic
        # editing functionality for the command line. These key binding are
        # however only active when the following `enable_all` condition is met.
        self.pt_key_bindings_manager = pt_KeyBindingManager(
            enable_vi_mode=Condition(lambda cli: pymux.status_keys_vi_mode),
            enable_all=(HasFocus(COMMAND) | HasFocus(PROMPT) | has_pane_buffer_focus) & ~HasPrefix(pymux),
            enable_auto_suggest_bindings=True,
            enable_extra_page_navigation=True)

        self.registry = self.pt_key_bindings_manager.registry

        self._prefix = (Keys.ControlB, )
        self._prefix_binding = None

        # Load initial bindings.
        self._load_builtins()
        self._load_prefix_binding()

        # Custom user configured key bindings.
        # { (needs_prefix, key) -> (command, handler) }
        self.custom_bindings = {}

    def _load_prefix_binding(self):
        """
        Load the prefix key binding.
        """
        pymux = self.pymux
        registry = self.registry

        # Remove previous binding.
        if self._prefix_binding:
            self.registry.remove_binding(self._prefix_binding)

        # Create new Python binding.
        @registry.add_binding(*self._prefix, filter=
            ~(HasPrefix(pymux) | HasFocus(COMMAND) | HasFocus(PROMPT) | WaitsForConfirmation(pymux)))
        def enter_prefix_handler(event):
            " Enter prefix mode. "
            pymux.get_client_state(event.cli).has_prefix = True

        self._prefix_binding = enter_prefix_handler

    def set_prefix(self, keys):
        """
        Set a new prefix key.
        """
        assert isinstance(keys, tuple)

        self._prefix = keys
        self._load_prefix_binding()

    def _load_builtins(self):
        """
        Fill the Registry with the hard coded key bindings.
        """
        pymux = self.pymux
        registry = self.registry

        # Create filters.
        has_prefix = HasPrefix(pymux)
        waits_for_confirmation = WaitsForConfirmation(pymux)
        prompt_or_command_focus = HasFocus(COMMAND) | HasFocus(PROMPT)
        display_pane_numbers = Condition(lambda cli: pymux.display_pane_numbers)
        pane_input_allowed = ~(prompt_or_command_focus | has_prefix |
                               waits_for_confirmation | display_pane_numbers |
                               has_pane_buffer_focus)

        @registry.add_binding(Keys.Any, filter=pane_input_allowed, invalidate_ui=False)
        def _(event):
            """
            When a pane has the focus, key bindings are redirected to the
            process running inside the pane.
            """
            # NOTE: we don't invalidate the UI, because for pymux itself,
            #       nothing in the output changes yet. It's the application in
            #       the pane that will probably echo back the typed characters.
            #       When we receive them, they are draw to the UI and it's
            #       invalidated.
            data = event.data
            pane = pymux.arrangement.get_active_pane(event.cli)

            if pane.clock_mode:
                # Leave clock mode on key press.
                pane.clock_mode = False
                pymux.invalidate()
            else:
                process = pane.process

                # Applications like htop with run in application mode require
                # the following input.
                if process.screen.in_application_mode:
                    data = {
                        Keys.Up: '\x1bOA',
                        Keys.Left: '\x1bOD',
                        Keys.Right: '\x1bOC',
                        Keys.Down: '\x1bOB',
                    }.get(event.key_sequence[0].key, data)

                data = data.replace('\n', '\r')
                process.write_input(data)

        @registry.add_binding(Keys.BracketedPaste, filter=pane_input_allowed, invalidate_ui=False)
        def _(event):
            """
            Pasting to the active pane. (Using bracketed paste.)
            """
            p = pymux.active_process_for_cli(event.cli)

            if p.screen.bracketed_paste_enabled:
                # When the process running in this pane understands bracketing paste.
                p.write_input('\x1b[200~' + event.data + '\x1b[201~')
            else:
                p.write_input(event.data)

        @registry.add_binding(Keys.Any, filter=has_prefix)
        def _(event):
            " Ignore unknown Ctrl-B prefixed key sequences. "
            pymux.get_client_state(event.cli).has_prefix = False

        @registry.add_binding(Keys.ControlC, filter=prompt_or_command_focus & ~has_prefix)
        @registry.add_binding(Keys.ControlG, filter=prompt_or_command_focus & ~has_prefix)
        @registry.add_binding(Keys.Backspace, filter=HasFocus(COMMAND) & ~has_prefix &
                              Condition(lambda cli: cli.buffers[COMMAND].text == ''))
        def _(event):
            " Leave command mode. "
            pymux.leave_command_mode(event.cli, append_to_history=False)

        @registry.add_binding('y', filter=waits_for_confirmation)
        @registry.add_binding('Y', filter=waits_for_confirmation)
        def _(event):
            """
            Confirm command.
            """
            client_state = pymux.get_client_state(event.cli)

            command = client_state.confirm_command
            client_state.confirm_command = None
            client_state.confirm_text = None

            pymux.handle_command(event.cli, command)

        @registry.add_binding('n', filter=waits_for_confirmation)
        @registry.add_binding('N', filter=waits_for_confirmation)
        @registry.add_binding(Keys.ControlC, filter=waits_for_confirmation)
        def _(event):
            """
            Cancel command.
            """
            client_state = pymux.get_client_state(event.cli)
            client_state.confirm_command = None
            client_state.confirm_text = None

        @registry.add_binding(Keys.ControlC, filter=has_pane_buffer_focus)
        def _(event):
            " Exit scroll buffer. "
            pane = pymux.arrangement.get_active_pane(event.cli)
            pane.copy_mode = False
            event.cli.focus_stack.replace(DEFAULT_BUFFER)

        @registry.add_binding(Keys.Any, filter=display_pane_numbers)
        def _(event):
            " When the pane numbers are shown. Any key press should hide them. "
            pymux.display_pane_numbers = False

        return registry

    def add_custom_binding(self, key_name, command, arguments, needs_prefix=False):
        """
        Add custom binding (for the "bind-key" command.)

        :param key_name: Pymux key name, for instance "C-a" or "M-x".
        """
        assert isinstance(key_name, six.text_type)
        assert isinstance(command, six.text_type)
        assert isinstance(arguments, list)

        # Unbind previous key.
        self.remove_custom_binding(key_name, needs_prefix=needs_prefix)

        # Translate the pymux key name into a prompt_toolkit key sequence.
        keys_sequence = pymux_key_to_prompt_toolkit_key_sequence(key_name)

        # Create handler and add to Registry.
        if needs_prefix:
            filter = HasPrefix(self.pymux)
        else:
            filter = ~HasPrefix(self.pymux)

        filter = filter & ~(WaitsForConfirmation(self.pymux) |
                             HasFocus(COMMAND) | HasFocus(PROMPT))

        def key_handler(event):
            " The actual key handler. "
            call_command_handler(command, self.pymux, event.cli, arguments)
            self.pymux.get_client_state(event.cli).has_prefix = False

        self.registry.add_binding(*keys_sequence, filter=filter)(key_handler)

        # Store key in `custom_bindings` in order to be able to call
        # "unbind-key" later on.
        k = (needs_prefix, key_name)
        self.custom_bindings[k] = CustomBinding(key_handler, command, arguments)

    def remove_custom_binding(self, key_name, needs_prefix=False):
        """
        Remove custom key binding for a key.

        :param key_name: Pymux key name, for instance "C-A".
        """
        k = (needs_prefix, key_name)

        if k in self.custom_bindings:
            self.registry.remove_binding(self.custom_bindings[k].handler)
            del self.custom_bindings[k]


class CustomBinding(object):
    def __init__(self, handler, command, arguments):
        self.handler = handler
        self.command = command
        self.arguments = arguments
