from __future__ import unicode_literals
from prompt_toolkit.filters import HasFocus, Condition
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys

from .enums import COMMAND, PROMPT
from .filters import WaitsForConfirmation, HasPrefix

__all__ = (
    'create_key_bindings',
)


def create_key_bindings(pymux):
    has_prefix = HasPrefix(pymux)
    waits_for_confirmation = WaitsForConfirmation(pymux)

    manager = KeyBindingManager(
        enable_all=(HasFocus(COMMAND) | HasFocus(PROMPT)) & ~has_prefix,
        enable_auto_suggest_bindings=True)
    registry = manager.registry

    @registry.add_binding(Keys.Any, filter=~HasFocus(COMMAND) & ~HasFocus(PROMPT) & ~has_prefix & ~waits_for_confirmation, invalidate_ui=False)
    def _(event):
        # NOTE: we don't invalidate the UI, because for pymux itself, nothing
        #       in the output changes yet. It's the application in the pane
        #       that will probably echo back the typed characters. When we
        #       receive them, they are draw to the UI and it's invalidated.
        data = event.data
        pane = pymux.arrangement.get_active_pane(event.cli)

        if pane.clock_mode:
            # Leave clock mode on key press.
            pane.clock_mode = False
            pymux.invalidate()
        else:
            process = pane.process

            # Applications like htop with run in application mode require the
            # following input.
            if process.screen.in_application_mode:
                data = {
                        Keys.Up: '\x1bOA',
                        Keys.Left: '\x1bOD',
                        Keys.Right: '\x1bOC',
                        Keys.Down: '\x1bOB',
                }.get(event.key_sequence[0].key, data)

            data = data.replace('\n', '\r')
            process.write_input(data)

    @registry.add_binding(Keys.BracketedPaste,
        filter=~HasFocus(COMMAND) & ~HasFocus(PROMPT) & ~has_prefix & ~waits_for_confirmation, invalidate_ui=False)
    def _(event):
        " Pasting to active pane. "
        p = pymux.active_process_for_cli(event.cli)

        if p.screen.bracketed_paste_enabled:
            # When the process running in this pane understands bracketing paste.
            p.write_input('\x1b[200~' + event.data + '\x1b[201~')
        else:
            p.write_input(event.data)

    @registry.add_binding(Keys.ControlB, filter=~has_prefix & ~waits_for_confirmation)
    def _(event):
        " Enter prefix mode. "
        pymux.get_client_state(event.cli).has_prefix = True

    @registry.add_binding(Keys.Any, filter=has_prefix)
    def _(event):
        " Ignore unknown Ctrl-B prefixed key sequences. "
        pymux.get_client_state(event.cli).has_prefix = False

    @registry.add_binding(Keys.ControlC, filter=(HasFocus(COMMAND) | HasFocus(PROMPT)) & ~has_prefix)
    @registry.add_binding(Keys.ControlG, filter=(HasFocus(COMMAND) | HasFocus(PROMPT)) & ~has_prefix)
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

    return registry
