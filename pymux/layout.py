#!/usr/bin/env python
# encoding: utf-8
"""
"""
from __future__ import unicode_literals

from prompt_toolkit.filters import HasFocus
from prompt_toolkit.layout.containers import VSplit, HSplit, Window, FloatContainer, Float, ConditionalContainer, Container
from prompt_toolkit.layout.controls import TokenListControl, FillControl, UIControl, BufferControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import BeforeInput, AppendAutoSuggestion
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.filters import Condition
from prompt_toolkit.mouse_events import MouseEventTypes

from pygments.token import Token
import datetime
import six
import os

from .process import Process
from .commands.lexer import create_command_lexer
import pymux.arrangement as arrangement

__all__ = (
    'LayoutManager',
)


class PaneContainer(UIControl):
    def __init__(self, pymux, pane):
        self.pane = pane
        self.process = pane.process
        self.pymux = pymux

    def create_screen(self, cli, width, height):
        process = self.process
        process.set_size(width, height)
        return process.screen.pt_screen

    def has_focus(self, cli):
        return self.pymux.arrangement.active_pane == self.pane

    def mouse_handler(self, cli, mouse_event):
        process = self.process
        x = mouse_event.position.x
        y = mouse_event.position.y

        if not self.has_focus(cli):
            # Focus this process when the mouse has been clicked.
            self.pymux.arrangement.active_window.active_pane = self.pane
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


class LayoutManager(object):
    def __init__(self, pymux):
        self.pymux = pymux
        self.body = VSplit([
            Window(TokenListControl(lambda cli: []))
        ])
        self.layout = self._create_layout()
        self.active_pane_write_position = None

    def _create_layout(self):
        def get_status_tokens(cli):
            result = []

            for i, w in enumerate(self.pymux.arrangement.windows):
                if w == self.pymux.arrangement.active_window:
                    result.extend([
                        (Token.StatusBar, ' '),
                        (Token.StatusBar.Window.Active, '%i:%s*' % (i, w.name)),
                        (Token.StatusBar, ' '),
                    ])
                else:
                    result.extend([
                        (Token.StatusBar, ' '),
                        (Token.StatusBar.Window, '%i:%s ' % (i, w.name)),
                        (Token.StatusBar, ' '),
                    ])

            return result

        def get_time_tokens(cli):
            return [
                (Token.StatusBar,
                datetime.datetime.now().strftime('%H:%M %d-%b-%y')),
                (Token.StatusBar, ' '),
            ]

        return HighlightBorders(FloatContainer(
            content=HSplit([
                self.body,
                ConditionalContainer(
                    content=Window(
                        height=D.exact(1),
                        content=BufferControl(
                            buffer_name='COMMAND',
                            default_char=Char(' ', Token.CommandLine),
                            lexer=create_command_lexer(self.pymux),
                            input_processors=[
                                BeforeInput.static(':', Token.CommandLine),
                                AppendAutoSuggestion(),
                            ])
                    ),
                    filter=HasFocus('COMMAND'),
                ),
                ConditionalContainer(
                    content=VSplit([
                        Window(
                            height=D.exact(1),
                            content=TokenListControl(get_status_tokens,
                                default_char=Char(' ', Token.StatusBar))),
                        Window(
                            height=D.exact(1), width=D.exact(20),
                            content=TokenListControl(get_time_tokens,
                                align_right=True,
                                default_char=Char(' ', Token.StatusBar)))
                    ]),
                    filter=~HasFocus('COMMAND'),
                )
            ]),
            floats=[
                Float(xcursor=True,
                      ycursor=True,
                      content=CompletionsMenu(max_height=12))
            ]
        ), self)

    def update(self):
        content = _create_split(self.pymux, self.pymux.arrangement.active_window.root,
                                left_edge=True, right_edge=True)

        self.body.children = [content]

        self.pymux.cli.invalidate()


def _create_split(pymux, split, left_edge=False, right_edge=False):
    """
    Create a prompt_toolkit `Container` instance for the given pymux split.

    :param left_edge: True when this split touches the left edge.
    :param right_edge: True when this split touches the right edge.
    """
    assert isinstance(split, (arrangement.HSplit, arrangement.VSplit))

    is_vsplit = isinstance(split, arrangement.VSplit)
    is_hsplit = not is_vsplit

    content = []

    for i, item in enumerate(split):
        le = left_edge and ((is_vsplit and i == 0) or is_hsplit)
        re = right_edge and ((is_vsplit and i == len(split) - 1) or is_hsplit)

        if isinstance(item, (arrangement.VSplit, arrangement.HSplit)):
            content.append(_create_split(pymux, item, left_edge=le, right_edge=re))
        elif isinstance(item, arrangement.Pane):
            content.append(_create_container_for_process(pymux, item, left_edge=le, right_edge=re))
        else:
            raise TypeError('Got %r' % (item,))

        # Draw a vertical line between windows. (In case of a vsplit)
        if is_vsplit and i != len(split) - 1:
            char = '│'
            content.append(HSplit([
                    Window(
                       width=D.exact(1), height=D.exact(1),
                       content=FillControl(char, token=Token.TitleBar.Line)),
                    Window(width=D.exact(1),
                           content=FillControl(char, token=Token.Line))
                ]))

    # Create prompt_toolkit Container.
    return_cls = VSplit if is_vsplit else HSplit
    return return_cls(content)


def _create_container_for_process(pymux, arrangement_pane, left_edge=False, right_edge=False):
    """
    Create a container with a titlebar for a process.
    """
    assert isinstance(arrangement_pane, arrangement.Pane)
    process = arrangement_pane.process

    def has_focus():
        return pymux.arrangement.active_pane == arrangement_pane

    def get_titlebar_token(cli):
        return Token.TitleBar.Focussed if has_focus() else Token.TitleBar

    def get_titlebar_name_token(cli):
        return Token.TitleBar.Name.Focussed if has_focus() else Token.TitleBar.Name

    def get_left_title_tokens(cli):
        token = get_titlebar_token(cli)
        name_token = get_titlebar_name_token(cli)
        result = [(token, ' ')]

        if arrangement_pane.name:
            result.append((name_token, ' %s ' % arrangement_pane.name))
            result.append((token, ' '))

        return result + [
            (token.Title, '%s' % process.screen.title),
        ]

    return TraceBorders(pymux, HSplit([
            Window(
                height=D.exact(1),
                content=TokenListControl(
                    get_left_title_tokens,
                    get_default_char=lambda cli: Char(' ', get_titlebar_token(cli)))
            ),
            Window(
                PaneContainer(pymux, arrangement_pane),
                get_vertical_scroll=lambda window: process.screen.line_offset,
                allow_scroll_beyond_bottom=True,
            )
            ]), Condition(lambda cli: has_focus()))

    return VSplit(result)


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


_focussed_border_char = Char('┃', Token.Line.Focussed)
_focussed_border_char_titlebar = Char('┃', Token.TitleBar.Line.Focussed)


class HighlightBorders(_ContainerProxy):
    """
    Highlight the active borders. Happens post rendering.

    (We highlight the active pane when the rendering of everything else is
    done, otherwise, rendering of panes on the right will replace the result of
    this one.
    """
    def __init__(self, content, layout_manager):
        _ContainerProxy.__init__(self, content)
        self.layout_manager = layout_manager

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        # Clear previous list of forder coordinates.
        self.layout_manager.active_pane_write_position = None

        # Render everything.
        _ContainerProxy.write_to_screen(self, cli, screen, mouse_handlers, write_position)

        # When rendering is done. Highlight the borders of the active pane.
        if self.layout_manager.active_pane_write_position:
            data_buffer = screen.data_buffer

            xpos, ypos, width, height = self.layout_manager.active_pane_write_position

            xleft = xpos - 1
            xright = xpos + width

            # First line.
            if xleft > 0:
                data_buffer[ypos][xleft] = _focussed_border_char_titlebar
            if xright < screen.width:
                data_buffer[ypos][xright] = _focussed_border_char_titlebar

            # Every following line.
            for y in range(ypos + 1, ypos + height):
                if xleft > 0:
                    data_buffer[y][xleft] = _focussed_border_char
                if xright < screen.width:
                    data_buffer[y][xright] = _focussed_border_char


class TraceBorders(_ContainerProxy):
    """
    Trace the location of the active pane.
    """
    def __init__(self, pymux, content, filter):
        _ContainerProxy.__init__(self, content)

        self.pymux = pymux
        self.filter = filter

    def write_to_screen(self, cli, screen, mouse_handlers, write_position):
        _ContainerProxy.write_to_screen(self, cli, screen, mouse_handlers, write_position)
        active_pane_write_position = self.pymux.layout_manager.active_pane_write_position

        # When this pane is the active pane, register write position.
        if self.filter(cli):
            ypos = write_position.ypos
            xpos = write_position.xpos
            width = write_position.width
            height = write_position.height

            self.pymux.layout_manager.active_pane_write_position = (xpos, ypos, width, height)
