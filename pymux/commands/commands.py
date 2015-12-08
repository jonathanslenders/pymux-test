from __future__ import unicode_literals
import signal
import docopt

from prompt_toolkit.document import Document

from pymux.arrangement import LayoutTypes
from pymux.enums import COMMAND, PROMPT

__all__ = (
    'has_command_handler',
    'call_command_handler',
    'get_documentation_for_command',
)

COMMANDS_TO_HANDLERS = {}  # Global mapping of pymux commands to their handlers.
COMMANDS_TO_HELP = {}


def has_command_handler(command):
    return command in COMMANDS_TO_HANDLERS


def get_documentation_for_command(command):
    """ Return the help text for this command, or None if the command is not
    known. """
    if command in COMMANDS_TO_HELP:
        return 'Usage: %s %s' % (command, COMMANDS_TO_HELP.get(command, ''))


def call_command_handler(command, pymux, cli, parameters):
    """
    Execute command.

    :param parameters: List of options.
    """
    assert isinstance(parameters, list)

    try:
        handler = COMMANDS_TO_HANDLERS[command]
    except KeyError:
        pymux.show_message(cli, 'Invalid command: %s' % command)
    else:
        try:
            handler(pymux, cli, parameters)
        except CommandException as e:
            pymux.show_message(cli, e.message)


def cmd(name, options=''):
    """
    Decorator for commands that don't take parameters.
    """
    # Validate options.
    if options:
        try:
            docopt.docopt('Usage:\n    %s %s' % (name, options, ), [])
        except SystemExit:
            pass

    def decorator(func):
        def command_wrapper(pymux, cli, parameters):
            # Parse options.
            try:
                received_options = docopt.docopt(
                    'Usage:\n    %s %s' % (name, options),
                    parameters,
                    help=False)  # Don't interpret the '-h' option as help.
            except SystemExit:
                raise CommandException('Usage: %s %s' % (name, options))

            # Call handler.
            func(pymux, cli, received_options)

        COMMANDS_TO_HANDLERS[name] = command_wrapper
        COMMANDS_TO_HELP[name] = options

        return func
    return decorator


class CommandException(Exception):
    " When raised from a command handler, this message will be shown. "
    def __init__(self, message):
        self.message = message

#
# The actual commands.
#

@cmd('break-pane')
def break_pane(pymux, cli, variables):
    pymux.arrangement.break_pane(cli)
    pymux.invalidate()


@cmd('select-pane', options='(-L|-R|-U|-D|-t <pane-id>)')
def select_pane(pymux, cli, variables):
    from pymux.layout import focus_right, focus_left, focus_up, focus_down

    if variables['-t']:
        pane_id = variables['<pane-id>']
        w = pymux.arrangement.get_active_window(cli)

        if pane_id == ':.+':
            # Select the next pane.
            w.focus_next()
        else:
            # Select pane by index.
            try:
                pane_id = int(pane_id[1:])
                w.active_pane = w.panes[pane_id]
            except (IndexError, ValueError):
                raise CommandException('Invalid pane.')

    else:
        if variables['-L']: h = focus_left
        if variables['-U']: h = focus_up
        if variables['-D']: h = focus_down
        if variables['-R']: h = focus_right

        h(pymux, cli)


@cmd('select-window', options='(-t <window-id>)')
def select_window(pymux, cli, variables):
    """
    Select a window. E.g:  select-window -t :3
    """
    window_id = variables['<window-id>']

    def invalid_window():
        raise CommandException('Invalid window: %s' % window_id)

    if window_id.startswith(':'):
        try:
            number = int(window_id[1:])
        except ValueError:
            invalid_window()
        else:
            try:
                w = pymux.arrangement.windows[number]
            except IndexError:
                invalid_window()
            else:
                pymux.arrangement.set_active_window(cli, w)
    else:
        invalid_window()


@cmd('rotate-window', options='[-D|-U]')
def rotate_window(pymux, cli, variables):
    if variables['-D']:
        pymux.arrangement.rotate_window(cli, count=-1)
    else:
        pymux.arrangement.rotate_window(cli)


@cmd('swap-pane', options='(-U|-D)')
def swap_pane(pymux, cli, variables):
    if variables['-U']:
        pymux.arrangement.get_active_window(cli).rotate(with_pane_after_only=True)
    else:
        pymux.arrangement.get_active_window(cli).rotate(with_pane_before_only=True)


@cmd('kill-pane')
def kill_pane(pymux, cli, variables):
    pymux.arrangement.get_active_pane(cli).process.send_signal(signal.SIGKILL)


@cmd('suspend-client')
def suspend_client(pymux, cli, variables):
    connection = pymux.get_connection_for_cli(cli)

    if connection:
        connection.suspend_client_to_background()


@cmd('clock-mode')
def clock_mode(pymux, cli, variables):
    pane = pymux.arrangement.get_active_pane(cli)
    if pane:
        pane.clock_mode = not pane.clock_mode


@cmd('last-pane')
def last_pane(pymux, cli, variables):
    w = pymux.arrangement.get_active_window(cli)
    prev_active_pane = w.previous_active_pane

    if prev_active_pane:
        w.active_pane = prev_active_pane


@cmd('next-layout')
def next_layout(pymux, cli, variables):
    " Select next layout. "
    pane = pymux.arrangement.get_active_window(cli)
    if pane:
        pane.select_next_layout()


@cmd('previous-layout')
def previous_layout(pymux, cli, variables):
    " Select previous layout. "
    pane = pymux.arrangement.get_active_window(cli)
    if pane:
        pane.select_previous_layout()


@cmd('new-window', options='[<executable>]')
def new_window(pymux, cli, variables):
    executable = variables['<executable>']
    pymux.create_window(cli, executable)


@cmd('next-window')
def next_window(pymux, cli, variables):
    " Focus the next window. "
    pymux.arrangement.focus_next_window(cli)


@cmd('previous-window')
def previous_window(pymux, cli, variables):
    " Focus the previous window. "
    pymux.arrangement.focus_previous_window(cli)


@cmd('select-layout', options='<layout-type>')
def select_layout(pymux, cli, variables):
    layout_type = variables['<layout-type>']

    if layout_type in LayoutTypes._ALL:
        pymux.arrangement.get_active_window(cli).select_layout(layout_type)
    else:
        raise CommandException('Invalid layout type.')


@cmd('rename-window', options='<name>')
def rename_window(pymux, cli, variables):
    """
    Rename the active window.
    """
    pymux.arrangement.get_active_window(cli).chosen_name = variables['<name>']


@cmd('rename-pane', options='<name>')
def rename_pane(pymux, cli, variables):
    """
    Rename the active pane.
    """
    pymux.arrangement.get_active_pane(cli).name = variables['<name>']


@cmd('send-signal', options='<signal>')
def send_signal(pymux, cli, variables):
    try:
        signal = variables['<signal>']
    except ValueError:
        pass  # Invalid integer.
    else:
        value = SIGNALS.get(signal)
        if value:
            pymux.arrangement.get_active_pane(cli).process.send_signal(value)
        else:
            raise CommandException('Invalid signal')


@cmd('split-window', options='[-v|-h] [<executable>]')
def split_window(pymux, cli, variables):
    """
    Split horizontally or vertically.
    """
    executable = variables['<executable>']

    # The tmux definition of horizontal is the opposite of prompt_toolkit.
    pymux.add_process(cli, executable, vsplit=variables['-h'])


@cmd('resize-pane', options="[(-L <left>)] [(-U <up>)] [(-D <down>)] [(-R <right>)] [-Z]")
def resize_pane(pymux, cli, variables):
    """
    Resize/zoom the active pane.
    """
    try:
        left = int(variables['<left>'] or 0)
        right = int(variables['<right>'] or 0)
        up = int(variables['<up>'] or 0)
        down = int(variables['<down>'] or 0)
    except ValueError:
        raise CommandException('Expecting an integer.')

    w = pymux.arrangement.get_active_window(cli)

    if w:
        w.change_size_for_active_pane(up=up, right=right, down=down, left=left)

        # Zoom in/out.
        if variables['-Z']:
            w.zoom = not w.zoom


@cmd('command-prompt')
def command_prompt(pymux, cli, variables):
    """
    Enter command prompt.
    """
    cli.focus_stack.replace(COMMAND)


@cmd('detach-client')
def detach_client(pymux, cli, variables):
    """
    Detach client.
    """
    pymux.detach_client(cli)


@cmd('confirm-before', options='[(-p <message>)] <command>')
def confirm_before(pymux, cli, variables):
    client_state = pymux.get_client_state(cli)

    client_state.confirm_text = variables['<message>'] or ''
    client_state.confirm_command = variables['<command>']


@cmd('command-prompt', options='[(-I <default>)] <command>')
def confirm_before(pymux, cli, variables):
    client_state = pymux.get_client_state(cli)

    client_state.prompt_command = variables['<command>']

    cli.focus_stack.replace(PROMPT)
    cli.buffers[PROMPT].reset(Document(variables['<default>']))


@cmd('send-prefix')
def send_prefix(pymux, cli, variables):
    """
    Send prefix to active pane.
    """
    # XXX: This is still a hard coded Control-B. Fix this when
    #      the prefix key becomes configurable.
    pymux.active_process_for_cli(cli).write_input('\x02')


SIGNALS = {
    'kill': signal.SIGKILL,
    'term': signal.SIGTERM,
    'usr1': signal.SIGUSR1,
    'usr2': signal.SIGUSR2,
    'hup': signal.SIGHUP,
}
