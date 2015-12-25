from __future__ import unicode_literals
import socket

__all__ = (
    'format_pymux_string',
)


def format_pymux_string(pymux, cli, string):
    """
    Apply pymux sting formatting. (Similar to tmux.)
    E.g.  #P is replaced by the index of the active pane.
    """
    arrangement = pymux.arrangement
    window = arrangement.get_active_window(cli)
    pane = window.active_pane

    def id_of_pane():
        return '%s' % (pane.pane_id, )

    def index_of_pane():
        try:
            return '%s' % (window.get_pane_index(pane), )
        except ValueError:
            return '/'

    def name_of_window():
        return window.name

    def title_of_pane():
        return pane.process.screen.title

    def hostname():
        return socket.gethostname()

    def literal():
        return '#'

    format_table = {
        '#D': id_of_pane,
        '#P': index_of_pane,
        '#T': title_of_pane,
        '#W': name_of_window,
        '#h': hostname,
        '##': literal,
    }

    for symbol, f in format_table.items():
        if symbol in string:
            string = string.replace(symbol, f())

    return string
