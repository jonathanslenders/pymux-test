#!/usr/bin/env python
# encoding: utf-8
"""
"""
from __future__ import unicode_literals

from prompt_toolkit.filters import HasFocus
from prompt_toolkit.layout.containers import VSplit, HSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import TokenListControl, FillControl, UIControl, BufferControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.filters import Condition
from prompt_toolkit.mouse_events import MouseEventTypes

from pygments.token import Token
import datetime
import six

from .process import Process
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

        if not self.has_focus:
            # Focus this process when the mouse has been clicked.
            self.pymux.arrangement.active_pane = self.pane
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

        return FloatContainer(
            content=HSplit([
                self.body,
                ConditionalContainer(
                    content=Window(
                        height=D.exact(1),
                        content=BufferControl(
                            buffer_name='COMMAND',
                            default_char=Char(' ', Token.CommandBar),
                            lexer=SimpleLexer(Token.CommandBar),
                            input_processors=[BeforeInput.static(':', Token.CommandBar)])
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
        )

    def update(self):
        content = _create_split(self.pymux, self.pymux.arrangement.active_window.root)

        self.body.children = [content]

        self.pymux.cli.invalidate()


def _create_split(pymux, split):
    """
    Create a prompt_toolkit `Container` instance for the given pymux split.
    """
    assert isinstance(split, (arrangement.HSplit, arrangement.VSplit))

    is_vsplit = isinstance(split, arrangement.VSplit)

    def create_condition(p1, p2):
        " True when one of the given processes has the focus. "
        def has_focus(cli):
            return True
#            return pymux.focussed_process in (p1, p2)
        return Condition(has_focus)

    content = []

    for i, item in enumerate(split):
        if isinstance(item, (arrangement.VSplit, arrangement.HSplit)):
            content.append(_create_split(pymux, item))
        elif isinstance(item, arrangement.Pane):
            content.append(_create_container_for_process(pymux, item))
        else:
            raise TypeError('Got %r' % (item,))

        # Draw a vertical line between windows. (In case of a vsplit)
        if is_vsplit:
            if i != len(split) - 1:  # TODO
                # Visible condition.
                condition = create_condition(None, None)#pymux.processes[i], pymux.processes[i+1])

                for titlebar_token, body_token, condition, char in [
                        (Token.TitleBar.Line, Token.Line, ~condition, '│'),
                        (Token.TitleBar.Line.Focussed, Token.Line.Focussed, condition, '┃')]:

                    content.append(ConditionalContainer(
                        HSplit([
                            Window(
                               width=D.exact(1), height=D.exact(1),
                               content=FillControl(char, token=titlebar_token)),
                            Window(width=D.exact(1),
                                   content=FillControl(char, token=body_token))
                        ]), condition))

    # Create prompt_toolkit Container.
    return_cls = VSplit if is_vsplit else HSplit
    return return_cls(content)


def _create_container_for_process(pymux, arrangement_pane):
    """
    Create a container with a titlebar for a process.
    """
    assert isinstance(arrangement_pane, arrangement.Pane)
    process = arrangement_pane.process

    def has_focus():
        return pymux.arrangement.active_pane == arrangement_pane

    def get_titlebar_token(cli):
        if has_focus():
            return Token.TitleBar.Focussed
        else:
            return Token.TitleBar

    def get_left_title_tokens(cli):
        token = get_titlebar_token(cli)
        return [(token, ' '), (token.Title, ' %s ' % process.screen.title), (token, ' ')]

    def get_right_title_tokens(cli):
        token = get_titlebar_token(cli)
        if has_focus():
            return [(token.Right, '[%s]' % process.pid)]
        else:
            return []

    return HSplit([
        VSplit([
            Window(
                height=D.exact(1),
                content=TokenListControl(
                    get_left_title_tokens,
                    get_default_char=lambda cli: Char(' ', get_titlebar_token(cli)))
            ),
            Window(
                height=D.exact(1), width=D.exact(8),
                content=TokenListControl(
                    get_right_title_tokens,
                    align_center=True,
                    get_default_char=lambda cli: Char(' ', get_titlebar_token(cli)))),
        ]),
        Window(
            PaneContainer(pymux, arrangement_pane),
            get_vertical_scroll=
                lambda window: process.screen.line_offset,
            allow_scroll_beyond_bottom=True,
        )
    ])

