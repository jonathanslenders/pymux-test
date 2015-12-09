from __future__ import unicode_literals

__all__ = (
    'format_pymux_string',
)


def format_pymux_string(pymux, cli, string):
    """
    Apply pymux sting formatting. (Similar to tmux.)
    E.g.  #P is replaced by the index of the active pane.
    """
    def index_of_pane():
        try:
            w = pymux.arrangement.get_active_window(cli)
            return '%s' % (w.get_pane_index(w.active_pane), )
        except ValueError:
            return '/'

    def name_of_window():
        return pymux.arrangement.get_active_window(cli).name

    format_table = {
        '#P': index_of_pane,
        '#W': name_of_window,
    }

    for symbol, f in format_table.items():
        if symbol in string:
            string = string.replace(symbol, f())

    return string
