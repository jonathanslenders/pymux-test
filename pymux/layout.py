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

from pygments.token import Token
import datetime

__all__ = (
    'LayoutManager',
)


class Pane(UIControl):
    def __init__(self, pymux, process):
        self.process = process
        self.pymux = pymux

    def create_screen(self, cli, width, height):
        process = self.process
        process.set_size(width, height)
        return process.screen.pt_screen

    def has_focus(self, cli):
        return self.pymux.focussed_process == self.process


class LayoutManager(object):
    def __init__(self, pymux):
        self.pymux = pymux
        self.body = VSplit([
            Window(TokenListControl(lambda cli: []))
        ])
        self.layout = self._create_layout()

    def _create_layout(self):
        def get_time_tokens(cli):
            return [
                    (Token.StatusBar,
                    datetime.datetime.now().strftime('%H:%M %d-%b-%y'))
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
                            content=TokenListControl(lambda cli: [(Token.StatusBar, ' pymux')],
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
        content = []

        def container_for_process(process):
            def has_focus():
                return self.pymux.focussed_process == process

            def get_left_title_tokens(cli):
                if has_focus():
                    token = Token.TitleBar.Focussed
                else:
                    token = Token.TitleBar

                return [(token, ' '), (token, process.screen.title), (token, ' ')]

            def get_right_title_tokens(cli):
                if has_focus():
                    return [(Token.TitleBar.Right, '[%s]' % process.pid)]
                else:
                    return []

            return HSplit([
                VSplit([
                    Window(
                        height=D.exact(1),
                        content=TokenListControl(get_left_title_tokens,
                                                 default_char=Char(' ', Token.TitleBar))
                    ),
                    Window(
                        height=D.exact(1), width=D.exact(11),
                        content=TokenListControl(get_right_title_tokens,
                                                 align_center=True,
                                                 default_char=Char(' ', Token.TitleBar))),
                ]),
                Window(
                    Pane(self.pymux, process),
                )
            ])

        for i, process in enumerate(self.pymux.processes):
            content.append(container_for_process(process))

            # Draw a vertical line between windows.
            if i != len(self.pymux.processes) - 1:
                content.append(
                    HSplit([
                        Window(
                           width=D.exact(1), height=D.exact(1),
                           content=FillControl('│', token=Token.TitleBar.Line)
                        ),
                    Window(width=D.exact(1),
                           content=FillControl('│', token=Token.Line))
                ]))

        self.body.children = content
        self.pymux.cli.invalidate()


