# encoding: utf-8
"""
"""
from __future__ import unicode_literals

from prompt_toolkit.filters import HasFocus, Condition
from prompt_toolkit.layout.containers import VSplit, HSplit, Window, FloatContainer, Float, ConditionalContainer, Container
from prompt_toolkit.layout.controls import TokenListControl, FillControl, UIControl, BufferControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import BeforeInput, AppendAutoSuggestion
from prompt_toolkit.layout.screen import Char, Screen
from prompt_toolkit.layout.toolbars import TokenListToolbar
from prompt_toolkit.mouse_events import MouseEventTypes

from pygments.token import Token

import pymux.arrangement as arrangement
import datetime
import six
import weakref

from .enums import COMMAND, PROMPT
from .filters import WaitsForConfirmation
from .log import logger
from .screen import DEFAULT_TOKEN

__all__ = (
    'LayoutManager',
)


class Background(Container):
    """
    Generate the background of dots, which becomes visible when several clients
    are attached and not all of them have the same size.
    """
    def reset(self):
        pass

    def preferred_width(self, cli, max_available_width):
        return D()

    def preferred_height(self, cli, width):
        return D()

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        " Fill the whole area of write_position with dots. "
        default_char = Char(' ', Token.Background)
        dot = Char('.', Token.Background)

        ypos = write_position.ypos
        xpos = write_position.xpos

        for y in range(ypos, ypos + write_position.height):
            row = screen.data_buffer[y]

            for x in range(xpos, xpos + write_position.width):
                row[x] = dot if (x + y) % 3 == 0 else default_char

    def walk(self):
        return []


class BigClock(UIControl):
    """
    Display a big clock.
    """
    WIDTH = 28
    HEIGHT = 5

    _numbers = [
        ['xxxxx', 'x   x', 'x   x', 'x   x', 'xxxxx'], # 0
        ['    x', '    x', '    x', '    x', '    x'], # 1
        ['xxxxx', '    x', 'xxxxx', 'x    ', 'xxxxx'], # 2
        ['xxxxx', '    x', 'xxxxx', '    x', 'xxxxx'], # 3
        ['x   x', 'x   x', 'xxxxx', '    x', '    x'], # 4
        ['xxxxx', 'x    ', 'xxxxx', '    x', 'xxxxx'], # 5
        ['xxxxx', 'x    ', 'xxxxx', 'x   x', 'xxxxx'], # 6
        ['xxxxx', '    x', '    x', '    x', '    x'], # 7
        ['xxxxx', 'x   x', 'xxxxx', 'x   x', 'xxxxx'], # 8
        ['xxxxx', 'x   x', 'xxxxx', '    x', 'xxxxx'], # 9
    ]

    def create_screen(self, cli, width, height):
        screen = Screen(initial_width=width)

        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                screen.data_buffer[y][x] = Char(' ', Token)

        def draw_number(x_offset, number):
            " Write number at position. "
            for y, row in enumerate(self._numbers[number]):
                screen_row = screen.data_buffer[y]
                for x, n in enumerate(row):
                    token = Token.Clock if n == 'x' else Token
                    screen_row[x + x_offset] = Char(' ', token)

        # Display time.
        now = datetime.datetime.now()
        draw_number(0, now.hour // 10)
        draw_number(6, now.hour % 10)
        draw_number(16, now.minute // 10)
        draw_number(23, now.minute % 10)

        # Add a colon
        screen.data_buffer[1][13] = Char(' ', Token.Clock)
        screen.data_buffer[3][13] = Char(' ', Token.Clock)

        screen.width = self.WIDTH
        screen.height = self.HEIGHT
        return screen


class PaneContainer(UIControl):
    """
    User control that takes the Screen from a pymux pane/process.
    This also handles mouse support.
    """
    def __init__(self, pymux, pane):
        self.pane = pane
        self.process = pane.process
        self.pymux = pymux

    def create_screen(self, cli, width, height):
        process = self.process
        process.set_size(width, height)
        return process.screen.pt_screen

    def has_focus(self, cli):
        return (cli.current_buffer_name != COMMAND and
            self.pymux.arrangement.get_active_pane(cli) == self.pane)

    def mouse_handler(self, cli, mouse_event):
        process = self.process
        x = mouse_event.position.x
        y = mouse_event.position.y

        # The containing Window translates coordinates to the absolute position
        # of the whole screen, but in this case, we need the relative
        # coordinates of the visible area.
        y -= self.process.screen.line_offset

        if not self.has_focus(cli):
            # Focus this process when the mouse has been clicked.
            self.pymux.arrangement.get_active_window(cli).active_pane = self.pane
            self.pymux.invalidate()
        else:
            # Already focussed, send event to application when it requested
            # mouse support.
            if process.screen.sgr_mouse_support_enabled:
                # Xterm SGR mode.
                ev, m = {
                    MouseEventTypes.MOUSE_DOWN: ('0', 'M'),
                    MouseEventTypes.MOUSE_UP: ('0', 'm'),
                    MouseEventTypes.SCROLL_UP: ('64', 'M'),
                    MouseEventTypes.SCROLL_DOWN: ('65', 'M'),
                }.get(mouse_event.event_type)

                self.process.write_input(
                    '\x1b[<%s;%s;%s%s' % (ev, x + 1, y + 1, m))

            elif process.screen.urxvt_mouse_support_enabled:
                # Urxvt mode.
                ev = {
                    MouseEventTypes.MOUSE_DOWN: 32,
                    MouseEventTypes.MOUSE_UP: 35,
                    MouseEventTypes.SCROLL_UP: 96,
                    MouseEventTypes.SCROLL_DOWN: 97,
                }.get(mouse_event.event_type)

                self.process.write_input(
                    '\x1b[%s;%s;%sM' % (ev, x + 1, y + 1))

            elif process.screen.mouse_support_enabled:
                # Fall back to old mode.
                if x < 96 and y < 96:
                    ev = {
                            MouseEventTypes.MOUSE_DOWN: 32,
                            MouseEventTypes.MOUSE_UP: 35,
                            MouseEventTypes.SCROLL_UP: 96,
                            MouseEventTypes.SCROLL_DOWN: 97,
                    }.get(mouse_event.event_type)

                    self.process.write_input('\x1b[M%s%s%s' % (
                        six.unichr(ev),
                        six.unichr(x + 33),
                        six.unichr(y + 33)))


class PaneWindow(Window):
    def __init__(self, pymux, arrangement_pane, process):
        self._process = process
        super(PaneWindow, self).__init__(
            content=PaneContainer(pymux, arrangement_pane),
            get_vertical_scroll=lambda window: process.screen.line_offset,
            allow_scroll_beyond_bottom=True,
        )

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        super(PaneWindow, self).write_to_screen(cli, screen, mouse_handlers, write_position)

        # If reverse video is enabled for the whole screen.
        if self._process.screen.has_reverse_video:
            data_buffer = screen.data_buffer

            for y in range(write_position.ypos, write_position.ypos + write_position.height):
                row = data_buffer[y]

                for x in range(write_position.xpos, write_position.xpos + write_position.width):
                    char = row[x]
                    token = list(char.token or DEFAULT_TOKEN)

                    # The token looks like ('C', *attrs). Replace the value of the reverse flag.
                    if token and token[0] == 'C':
                        token[-1] = not token[-1] # Invert reverse value.
                        row[x] = Char(char.char, tuple(token))


class MessageToolbar(TokenListToolbar):
    """
    Pop-up (at the bottom) for showing error/status messages.
    """
    def __init__(self, pymux):
        def get_message(cli):
            # If there is a message to be shown for this client, show that.
            client_state = pymux.get_client_state(cli)

            if client_state.message:
                return client_state.message
            else:
                return ''

        def get_tokens(cli):
            message = get_message(cli)
            if message:
                return [(Token.Message, message)]
            else:
                return []

        super(MessageToolbar, self).__init__(
                get_tokens,
                filter=Condition(lambda cli: get_message(cli) is not None))


class LayoutManager(object):
    def __init__(self, pymux):
        self.pymux = pymux
        self.layout = self._create_layout()

        # Keep track of render information.
        self.pane_write_positions = {}
        self.body_write_position = None

    def _create_select_window_handler(self, window):
        " Return a mouse handler that selects the given window when clicking. "
        def handler(cli, mouse_event):
            if mouse_event.event_type == MouseEventTypes.MOUSE_DOWN:
                self.pymux.arrangement.set_active_window(cli, window)
                self.pymux.invalidate()
            else:
                return NotImplemented  # Event not handled here.
        return handler

    def _get_status_tokens(self, cli):
        result = []
        previous_window = self.pymux.arrangement.get_previous_active_window(cli)

        for i, w in enumerate(self.pymux.arrangement.windows):
            result.append((Token.StatusBar, ' '))
            handler = self._create_select_window_handler(w)

            if w == self.pymux.arrangement.get_active_window(cli):
                result.append((Token.StatusBar.Window.Active, '%i:%s*' % (i, w.name), handler))

            elif w == previous_window:
                result.append((Token.StatusBar.Window, '%i:%s-' % (i, w.name), handler))

            else:
                result.append((Token.StatusBar.Window, '%i:%s ' % (i, w.name), handler))

        return result

    def _get_time_tokens(self, cli):
        return [
            (Token.StatusBar,
            datetime.datetime.now().strftime('%H:%M %d-%b-%y')),
            (Token.StatusBar, ' '),
        ]

    def _before_prompt_command_tokens(self, cli):
        client_state = self.pymux.get_client_state(cli)
        if client_state.prompt_command:
            return [
                (Token.CommandLine, '(%s) ' % client_state.prompt_command.split()[0])
            ]
        else:
            return []

    def _create_layout(self):
        return FloatContainer(
            content=HSplit([
                # The main window.
                HighlightBorders(self, self.pymux, FloatContainer(
                    Background(),
                    floats=[
                        Float(get_width=lambda cli: self.pymux.get_window_size(cli).columns,
                              get_height=lambda cli: self.pymux.get_window_size(cli).rows,
                              content=TraceBodyWritePosition(self.pymux, DynamicBody(self.pymux)))
                    ])),

                # Bottom toolbars.
                ConditionalContainer(
                    content=Window(
                        height=D.exact(1),
                        content=BufferControl(
                            buffer_name=COMMAND,
                            default_char=Char(' ', Token.CommandLine),
                            lexer=SimpleLexer(Token.CommandLine),
                            input_processors=[
                                BeforeInput.static(':', Token.CommandLine),
                                AppendAutoSuggestion(),
                            ])
                    ),
                    filter=HasFocus(COMMAND),
                ),
                ConditionalContainer(
                    content=Window(
                        height=D.exact(1),
                        content=BufferControl(
                            buffer_name=PROMPT,
                            default_char=Char(' ', Token.CommandLine),
                            input_processors=[
                                BeforeInput(self._before_prompt_command_tokens),
                                AppendAutoSuggestion(),
                            ])
                    ),
                    filter=HasFocus(PROMPT),
                ),
                ConditionalContainer(
                    content=VSplit([
                        Window(
                            height=D.exact(1),
                            content=TokenListControl(self._get_status_tokens,
                                default_char=Char(' ', Token.StatusBar))),
                        Window(
                            height=D.exact(1), width=D.exact(20),
                            content=TokenListControl(self._get_time_tokens,
                                align_right=True,
                                default_char=Char(' ', Token.StatusBar)))
                    ]),
                    filter=~HasFocus(COMMAND) & ~HasFocus(PROMPT),
                )
            ]),
            floats=[
                Float(bottom=1, left=0, content=MessageToolbar(self.pymux)),
                Float(xcursor=True, ycursor=True, content=CompletionsMenu(max_height=12)),
                Float(content=ConditionalContainer(
                    content=ConfirmationWindow(self.pymux),
                    filter=WaitsForConfirmation(self.pymux),
                ))
            ]
        )


class ConfirmationWindow(HSplit):
    """
    Window that displays the yes/no confirmation dialog.
    """
    def __init__(self, pymux):
        token = Token.ConfirmationDialog

        def get_tokens(cli):
            client_state = pymux.get_client_state(cli)
            return [(token.Question, ' %s ' % (client_state.confirm_text, ))]

        def get_tokens2(cli):
            client_state = pymux.get_client_state(cli)
            return [
                (token.YesNo, '  y/n'),
                (Token.SetCursorPosition, ''),
                (token.YesNo, '  '),
            ]

        default_char1 = Char(' ', token.Question)
        default_char2 = Char(' ', token.YesNo)

        super(ConfirmationWindow, self).__init__(
            [
                TokenListToolbar(get_tokens, default_char=default_char1),
                TokenListToolbar(get_tokens2, default_char=default_char2, align_right=True,
                                 has_focus=WaitsForConfirmation(pymux)),
            ])


class DynamicBody(Container):
    """
    The dynamic part, which is different for each CLI (for each client). It
    depends on which window/pane is active.
    """
    def __init__(self, pymux):
        self.pymux = pymux
        self._bodies_for_clis = weakref.WeakKeyDictionary()  # Maps CLI to (hash, Container)

    def _get_body(self, cli):
        " Return the Container object for the current CLI. "
        new_hash = self.pymux.arrangement.invalidation_hash(cli)

        # Return existing layout if nothing has changed to the arrangement.
        if cli in self._bodies_for_clis:
            existing_hash, container = self._bodies_for_clis[cli]
            if existing_hash == new_hash:
                return container

        # The layout changed. Build a new layout when the arrangement changed.
        new_layout = self._build_layout(cli)
        self._bodies_for_clis[cli] = (new_hash, new_layout)
        return new_layout

    def _build_layout(self, cli):
        " Rebuild a new Container object and return that. "
        logger.info('Rebuilding layout.')
        active_window = self.pymux.arrangement.get_active_window(cli)

        # When zoomed, only show the current pane, otherwise show all of them.
        if active_window.zoom:
            return _create_container_for_process(self.pymux, active_window.active_pane, zoom=True)
        else:
            return _create_split(self.pymux, self.pymux.arrangement.get_active_window(cli).root)

    def reset(self):
        for invalidation_hash, body in self._bodies_for_clis.values():
            body.reset()

    def preferred_width(self, cli, max_available_width):
        body = self._get_body(cli)
        return body.preferred_width(cli, max_available_width)

    def preferred_height(self, cli, width):
        body = self._get_body(cli)
        return body.preferred_height(cli, width)

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        body = self._get_body(cli)
        body.write_to_screen(cli, screen, mouse_handlers, write_position)

    def walk(self):
        return []  # We don't need this.


def _create_split(pymux, split):
    """
    Create a prompt_toolkit `Container` instance for the given pymux split.
    """
    assert isinstance(split, (arrangement.HSplit, arrangement.VSplit))

    is_vsplit = isinstance(split, arrangement.VSplit)

    content = []

    def vertical_line():
        " Draw a vertical line between windows. (In case of a vsplit) "
        char = '│'
        content.append(HSplit([
                Window(
                   width=D.exact(1), height=D.exact(1),
                   content=FillControl(char, token=Token.TitleBar.Line)),
                Window(width=D.exact(1),
                       content=FillControl(char, token=Token.Line))
            ]))

    for i, item in enumerate(split):
        if isinstance(item, (arrangement.VSplit, arrangement.HSplit)):
            content.append(_create_split(pymux, item))
        elif isinstance(item, arrangement.Pane):
            content.append(_create_container_for_process(pymux, item))
        else:
            raise TypeError('Got %r' % (item,))

        if is_vsplit and i != len(split) - 1:
            vertical_line()

    def get_average_weight():
        """ Calculate average weight of the children. Return 1 if none of
        the children has a weight specified yet. """
        weights = 0
        count = 0

        for i in split:
            if i in split.weights:
                weights += split.weights[i]
                count += 1

        if weights:
            return max(1, weights // count)
        else:
            return 1

    def get_dimensions(cli):
        """
        Return a list of LayoutDimension instances for this split.
        These dimensions will take the weight from the
        arrangement.VSplit/HSplit instances.
        """
        average_weight = get_average_weight()

        # Make sure that weight is distributed

        result = []
        for i, item in enumerate(split):
            result.append(D(weight=split.weights.get(item) or average_weight))

            # Add dimension for the vertical border.
            if is_vsplit and i != len(split) - 1:
                result.append(D.exact(1))

        return result

    def report_dimensions_callback(cli, dimensions):
        """
        When the layout is rendered, store the actial dimensions as
        weights in the arrangement.VSplit/HSplit classes.

        This is required because when a pane is resized with an increase of +1,
        we want to be sure that this corresponds exactly with one row or
        column. So, that updating weights corresponds exactly 1/1 to updating
        the size of the panes.
        """
        sizes = []
        for i, size in enumerate(dimensions):
            if not (is_vsplit and i % 2 != 0):
                sizes.append(size)

        for c, size in zip(split, sizes):
            split.weights[c] = size

    # Create prompt_toolkit Container.
    return_cls = VSplit if is_vsplit else HSplit

    return return_cls(content, get_dimensions=get_dimensions,
                      report_dimensions_callback=report_dimensions_callback)


def _create_container_for_process(pymux, arrangement_pane, zoom=False):
    """
    Create a `Container` with a titlebar for a process.
    """
    assert isinstance(arrangement_pane, arrangement.Pane)
    process = arrangement_pane.process

    def has_focus(cli):
        return pymux.arrangement.get_active_pane(cli) == arrangement_pane

    def get_titlebar_token(cli):
        return Token.TitleBar.Focussed if has_focus(cli) else Token.TitleBar

    def get_titlebar_name_token(cli):
        return Token.TitleBar.Name.Focussed if has_focus(cli) else Token.TitleBar.Name

    def get_title_tokens(cli):
        token = get_titlebar_token(cli)
        name_token = get_titlebar_name_token(cli)
        result = []

        if zoom:
            result.append((Token.TitleBar.Zoom, ' Z '))

        if arrangement_pane.name:
            result.append((name_token, ' %s ' % arrangement_pane.name))
            result.append((token, ' '))

        return result + [
            (token.Title, ' %s' % process.screen.title),
        ]

    def get_pane_index(cli):
        token = get_titlebar_token(cli)

        try:
            w = pymux.arrangement.get_active_window(cli)
            index = w.get_pane_index(arrangement_pane)
        except ValueError:
            index = '/'

        return [(token.PaneIndex, '%3s ' % index)]


    clock_is_visible = Condition(lambda cli: arrangement_pane.clock_mode)

    return TracePaneWritePosition(pymux, arrangement_pane,
        content=HSplit([
            # The title bar.
            VSplit([
                Window(
                    height=D.exact(1),
                    content=TokenListControl(
                        get_title_tokens,
                        get_default_char=lambda cli: Char(' ', get_titlebar_token(cli)))
                ),
                Window(
                    height=D.exact(1),
                    width=D.exact(4),
                    content=TokenListControl(
                        get_pane_index,
                        )#get_default_char=lambda cli: Char(' ', get_titlebar_token(cli)))
                )
            ]),
            # The pane content.
            ConditionalContainer(
                content=PaneWindow(pymux, arrangement_pane, process),
                filter=~clock_is_visible,
            ),
            # The clock.
            ConditionalContainer(
                # Add a dummy VSplit/HSplit around the BigClock in order to center it.
                # (Using a FloatContainer to do the centering doesn't work well, because
                # the boundaries are not clipt when the parent is smaller.)
                content=VSplit([
                    Window(FillControl()),
                    HSplit([
                        Window(FillControl()),
                        Window(BigClock(), height=D.exact(BigClock.HEIGHT)),
                        Window(FillControl()),
                    ]),
                    Window(FillControl()),
                ], get_dimensions=lambda cli: [None, D.exact(BigClock.WIDTH), None]),

                filter=clock_is_visible,
            ),
        ]),
    )


class _ContainerProxy(Container):
    def __init__(self, content):
        self.content = content

    def reset(self):
        self.content.reset()

    def preferred_width(self, cli, max_available_width):
        return self.content.preferred_width(cli, max_available_width)

    def preferred_height(self, cli, width):
        return self.content.preferred_height(cli, width)

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        self.content.write_to_screen(cli, screen, mouse_handlers, write_position)

    def walk(self):
        return self.content.walk()


_focussed_border_titlebar = Char('┃', Token.TitleBar.Line.Focussed)
_focussed_border_vertical = Char('┃', Token.Line.Focussed)
_focussed_border_horizontal = Char('━', Token.Line.Focussed)
_focussed_border_left_top = Char('┏', Token.Line.Focussed)
_focussed_border_right_top = Char('┓', Token.Line.Focussed)
_focussed_border_left_bottom = Char('┗', Token.Line.Focussed)
_focussed_border_right_bottom = Char('┛', Token.Line.Focussed)

_border_vertical = Char('│', Token.Line)
_border_horizontal = Char('─', Token.Line)
_border_left_bottom = Char('└', Token.Line)
_border_right_bottom = Char('┘', Token.Line)
_border_left_top = Char('┌', Token.Line)
_border_right_top = Char('┐', Token.Line)


class HighlightBorders(_ContainerProxy):
    """
    Highlight the active borders. Happens post rendering.

    (We highlight the active pane when the rendering of everything else is
    done, otherwise, rendering of panes on the right will replace the result of
    this one.
    """
    def __init__(self, layout_manager, pymux, content):
        _ContainerProxy.__init__(self, content)
        self.pymux = pymux
        self.layout_manager = layout_manager

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        # Clear previous list of pane coordinates.
        self.layout_manager.pane_write_positions = {}   # XXX: Should be for each CLI individually!
        self.layout_manager.body_write_position = None

        # Render everything.
        _ContainerProxy.write_to_screen(self, cli, screen, mouse_handlers, write_position)

        # When rendering is done. Draw borders and highlight the borders of the
        # active pane.
        self._draw_borders(screen, write_position)

        try:
            pane_wp = self.layout_manager.pane_write_positions[
                self.pymux.arrangement.get_active_pane(cli)]
        except KeyError:
            pass
        else:
            self._highlight_active_pane(screen, pane_wp, write_position)

    def _draw_borders(self, screen, write_position):
        """
        Draw borders around the whole window. (When there is space.)
        """
        data_buffer = screen.data_buffer

        if self.layout_manager.body_write_position:
            wp = self.layout_manager.body_write_position

            # Bottom line.
            if wp.ypos + wp.height < write_position.ypos + write_position.height:
                row = data_buffer[wp.ypos + wp.height]

                for x in range(wp.xpos, wp.xpos + wp.width):
                    row[x] = _border_horizontal

                # Left/right bottom.
                data_buffer[wp.ypos + wp.height][wp.xpos - 1] = _border_left_bottom
                data_buffer[wp.ypos + wp.height][wp.xpos + wp.width] = _border_right_bottom

            # Left and right line.
            for y in range(wp.ypos + 1, wp.ypos + wp.height):
                data_buffer[y][wp.xpos - 1] = _border_vertical
                data_buffer[y][wp.xpos + wp.width] = _border_vertical

            # Left/right top
            data_buffer[wp.ypos][wp.xpos - 1] = _border_left_top
            data_buffer[wp.ypos][wp.xpos + wp.width] = _border_right_top

    def _highlight_active_pane(self, screen, pane_wp, write_position):
        " Highlight the current, active pane. "
        data_buffer = screen.data_buffer
        xpos, ypos, width, height = pane_wp.xpos, pane_wp.ypos, pane_wp.width, pane_wp.height

        xleft = xpos - 1
        xright = xpos + width

        # First line.
        row = data_buffer[ypos]

        if row[xleft].token == Token.Line:
            row[xleft] = _focussed_border_left_top
        else:
            row[xleft] = _focussed_border_titlebar

        if row[xright].token == Token.Line:
            row[xright] = _focussed_border_right_top
        else:
            row[xright] = _focussed_border_titlebar

        # Every following line.
        for y in range(ypos + 1, ypos + height):
            row = data_buffer[y]
            row[xleft] = row[xright] = _focussed_border_vertical

        # Draw the bottom line. (Only when there is space.)
        if ypos + height < write_position.ypos + write_position.height:
            row = data_buffer[ypos + height]

            for x in range(xpos, xpos + width):
                # Don't overwrite the titlebar of a pane below.
                if row[x].token == Token.Line:
                    row[x] = _focussed_border_horizontal

            # Bottom corners.
            row[xpos - 1] = _focussed_border_left_bottom
            row[xpos + width] = _focussed_border_right_bottom


class TracePaneWritePosition(_ContainerProxy):
    " Trace the write position of this pane. "
    def __init__(self, pymux, arrangement_pane, content):
        _ContainerProxy.__init__(self, content)

        self.pymux = pymux
        self.arrangement_pane = arrangement_pane

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        _ContainerProxy.write_to_screen(self, cli, screen, mouse_handlers, write_position)

        self.pymux.layout_manager.pane_write_positions[self.arrangement_pane] = write_position


class TraceBodyWritePosition(_ContainerProxy):
    " Trace the write position of the whole body. "
    def __init__(self, pymux, content):
        _ContainerProxy.__init__(self, content)
        self.pymux = pymux

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        _ContainerProxy.write_to_screen(self, cli, screen, mouse_handlers, write_position)
        self.pymux.layout_manager.body_write_position = write_position


def focus_left(pymux, cli):
    " Move focus to the left. "
    _move_focus(pymux, cli,
                lambda wp: wp.xpos - 2,  # 2 in order to skip over the border.
                lambda wp: wp.ypos)


def focus_right(pymux, cli):
    " Move focus to the right. "
    _move_focus(pymux, cli,
                lambda wp: wp.xpos + wp.width + 1,
                lambda wp: wp.ypos)


def focus_down(pymux, cli):
    " Move focus down. "
    _move_focus(pymux, cli,
                lambda wp: wp.xpos,
                lambda wp: wp.ypos + wp.height + 1)


def focus_up(pymux, cli):
    " Move focus up. "
    _move_focus(pymux, cli,
                lambda wp: wp.xpos,
                lambda wp: wp.ypos - 1)


def _move_focus(pymux, cli, get_x, get_y):
    " Move focus of the active window. "
    window = pymux.arrangement.get_active_window(cli)

    try:
        write_pos = pymux.layout_manager.pane_write_positions[window.active_pane]
    except KeyError:
        pass
    else:
        x = get_x(write_pos)
        y = get_y(write_pos)

        # Look for the pane at this position.
        for pane, wp in pymux.layout_manager.pane_write_positions.items():
            if (wp.xpos <= x < wp.xpos + wp.width and
                    wp.ypos <= y < wp.ypos + wp.height):
                window.active_pane = pane
                return
