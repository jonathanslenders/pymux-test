from __future__ import unicode_literals
from prompt_toolkit.styles import PygmentsStyle, Style, Attrs
from pygments.token import Token

__all__ = (
    'PymuxStyle',
)


ui_style = {
    Token.Line:                    '#888888',
    Token.Line.Focussed:           '#448844',

    Token.TitleBar:                'bg:#888888 #dddddd ',
    Token.TitleBar.Title:          '',
    Token.TitleBar.Name:           '#ffffff noitalic',
    Token.TitleBar.Name.Focussed:  'bg:#88aa44',
    Token.TitleBar.Line:           '#444444',
    Token.TitleBar.Line.Focussed:  '#448844 noinherit',
    Token.TitleBar.Focussed:       'bg:#448844 #ffffff bold',
    Token.TitleBar.Focussed.Title: '',
    Token.TitleBar.Zoom:           'bg:#884400 #ffffff',
    Token.TitleBar.PaneIndex:      '',
    Token.TitleBar.CopyMode:           'bg:#888888 #000000',
    Token.TitleBar.CopyMode.Position:  '',

    Token.TitleBar.Focussed.PaneIndex:         'bg:#88aa44 #ffffff',
    Token.TitleBar.Focussed.CopyMode:          'bg:#aaff44 #000000',
    Token.TitleBar.Focussed.CopyMode.Position: '#888888',

    Token.CommandLine:             'bg:#884444 #ffffff',
    Token.CommandLine.Command:     'bold',
    Token.CommandLine.Prompt:      'bold',
    Token.StatusBar:               'bg:#444444 #ffffff',
    Token.StatusBar.Window:        'bg:#888888',
    Token.StatusBar.Window.Active: '#88ff88 bold',
    Token.AutoSuggestion:          'bg:#884444 #ff8888',
    Token.Message:                 'bg:#bbee88 #222222',
    Token.Background:              '#888888',
    Token.Clock:                   'bg:#88aa00',
    Token.Terminated:              'bg:#aa0000 #ffffff',

    Token.ConfirmationToolbar:          'bg:#880000 #ffffff',
    Token.ConfirmationToolbar.Question: '',
    Token.ConfirmationToolbar.YesNo:    'bg:#440000',

    Token.Search:                  'bg:#888888 #000000',
    Token.Search.Text:             '',
    Token.Search.Focussed:         'bg:#aaff44 #444444',
    Token.Search.Focussed.Text:    'bold #000000',
}


class PymuxStyle(Style):
    def __init__(self):
        self.pygments_style = PygmentsStyle.from_defaults(style_dict=ui_style)
        self._token_to_attrs_dict = None

    def get_attrs_for_token(self, token):
        if token and token[0] == 'C':
            c, fg, bg, bold, underline, italic, blink, reverse = token
            return Attrs(fg, bg, bold, underline, italic, blink, reverse)
        else:
            return self.pygments_style.get_attrs_for_token(token)

    def invalidation_hash(self):
        return None
