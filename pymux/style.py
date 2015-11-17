from __future__ import unicode_literals
from prompt_toolkit.styles import PygmentsStyle, Style, Attrs
from pygments.token import Token

__all__ = (
    'PymuxStyle',
)


ui_style = {
    Token.Line:                    '#888888',
    Token.Line.Focussed:           '#448844',

    Token.TitleBar:                'bg:#888888 #dddddd italic',
    Token.TitleBar.Title:          '',
    Token.TitleBar.Name:           '#ffffff noitalic',
    Token.TitleBar.Name.Focussed:  'bg:#44aa44',
    Token.TitleBar.Line:           '#444444',
    Token.TitleBar.Line.Focussed:  'bg:#448844 #000000',
    Token.TitleBar.Focussed:       'bg:#448844 #ffffff bold',
    Token.TitleBar.Focussed.Title: '',
    Token.TitleBar.Zoom:           'bg:#884400 #ffffff',

    Token.CommandLine:             'bg:#884444 #ffffff',
    Token.CommandLine.Command:     'bold',
    Token.CommandLine.Executable:  'bg:#ffbbbb #000000',
    Token.CommandLine.Text:        'bg:#bbffbb #000000',
    Token.StatusBar:               'bg:#444444 #ffffff',
    Token.StatusBar.Window:        'bg:#888888',
    Token.StatusBar.Window.Active: '#88ff88 bold',
    Token.AutoSuggestion:          'bg:#884444 #ff8888',
}


class PymuxStyle(Style):
    def __init__(self):
        self.pygments_style = PygmentsStyle.from_defaults(style_dict=ui_style)
        self._token_to_attrs_dict = None

    def get_attrs_for_token(self, token):
        if token and token[0] == 'C':
            c, fg, bg, bold, underline, italic, reverse = token
            return Attrs(fg, bg, bold, underline, italic, reverse)
        else:
            return self.pygments_style.get_attrs_for_token(token)

    def invalidation_hash(self):
        return None
