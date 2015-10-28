from __future__ import unicode_literals
import array
import fcntl
import termios

__all__ = (
    'set_size',
)


def set_size(stdout_fileno, rows, cols):
    """
    Set terminal size.

    (This is also mainly for internal use. Setting the terminal size
    automatically happens when the window resizes. However, sometimes the
    process that created a pseudo terminal, and the process that's attached to
    the output window are not the same, e.g. in case of a telnet connection, or
    unix domain socket, and then we have to sync the sizes by hand.)
    """
    # Buffer for the C call
    # (The first parameter of 'array.array' needs to be 'str' on both Python 2
    # and Python 3.)
    buf = array.array(str('h'), [rows, cols, 0, 0 ])

    # Do: TIOCSWINSZ (Set)
    fcntl.ioctl(stdout_fileno, termios.TIOCSWINSZ, buf)
