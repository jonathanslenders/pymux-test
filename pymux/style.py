from __future__ import unicode_literals
from prompt_toolkit.styles import default_style_extensions, PygmentsStyle, Style, Attrs
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.styles.default import DefaultStyle

import pygments.style
from pygments.token import Token

__all__ = (
    'PymuxStyle',
)

class PyMuxStyle(pygments.style.Style):
    styles = DefaultStyle.styles.copy()

    styles.update(default_style_extensions)
    styles.update({
        Token.Line:                    '#888888',
        Token.Line.Focussed:           '#448844',

        Token.TitleBar:                'bg:#888888 #dddddd italic',
        Token.TitleBar.Title:          '',
        Token.TitleBar.Line:           '#444444',
        Token.TitleBar.Line.Focussed:  'bg:#448844 #000000',
        Token.TitleBar.Focussed:       'bg:#448844 #ffffff bold',
        Token.TitleBar.Focussed.Title: '',
        Token.TitleBar.Focussed.Right: 'noitalic',
        Token.CommandLine:             'bg:#884444 #ffffff',
        Token.CommandLine.Executable:  '',
        Token.CommandLine.Command:     'bold',
        Token.StatusBar:               'bg:#444444 #ffffff',
        Token.StatusBar.Window:        'bg:#888888',
        Token.StatusBar.Window.Active: '#88ff88',
    })



class PymuxStyle(Style):
    _colors = {
        'black':   '000000',
        'red':     'aa0000',
        'green':   '00aa00',
        'brown':   'aaaa00',
        'blue':    '0000aa',
        'magenta': 'aa00aa',
        'cyan':    '00aaaa',
        'white':   'ffffff',
        'default':  '',
    }
    for i, (r,g,b) in enumerate(Terminal256Formatter().xterm_colors):
         _colors[1024 + i] = '%02x%02x%02x' % (r,g,b)

    def __init__(self):
        self.pygments_style = PygmentsStyle(PyMuxStyle)
        self._token_to_attrs_dict = None

    def get_attrs_for_token(self, token):
        if token and token[0] == 'C':
            c, fg, bg, bold, underline, italic, reverse = token


            fg = self._colors.get(fg, fg)
            bg = self._colors.get(bg, bg)

            return Attrs(fg, bg, bold, underline, italic, reverse)
        else:
            return self.pygments_style.get_attrs_for_token(token)

    def invalidation_hash(self):
        return None
