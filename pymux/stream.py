from __future__ import unicode_literals
from pyte.streams import Stream

__all__ = (
    'BetterStream',
)


class BetterStream(Stream):
    """
    Extension to the Pyte `Stream` class that also handles "Esc]<num>...BEL"
    sequences. This is used by xterm to set the terminal title.
    """
    csi = {
        'n': 'cpr',
    }
    csi.update(Stream.csi)

    def __init__(self):
        super(BetterStream, self).__init__()
        self.handlers['square_close'] = self._square_close
        self.handlers['escape'] = self._escape
        self._square_close_data = []

    def _escape(self, char):
        if char == ']':
            self.state = 'square_close'
        else:
            super(BetterStream, self)._escape(char)

    def _square_close(self, char):
        " Parse ``Esc]<num>...BEL``sequence. "
        if char == '\07':
            self.dispatch('square_close', ''.join(self._square_close_data))
            self._square_close_data = []
            self.state = "stream"
        else:
            self._square_close_data.append(char)
