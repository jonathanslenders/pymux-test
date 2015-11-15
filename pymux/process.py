"""
"""
from __future__ import unicode_literals

from prompt_toolkit.eventloop.posix_utils import PosixStdinReader

from .screen import BetterScreen
from .stream import BetterStream
from .pexpect_utils import pty_make_controlling_tty
from .utils import set_size

import getpass
import os
import os
import pwd
import resource
import signal
import sys
import time
import traceback

__all__ = (
    'Process',
)


class Process(object):
    def __init__(self, cli, done_callback=None):
        self.cli = cli
        self.done_callback = done_callback
        self.pid = None
        self.is_terminated = False

        # Create pseudo terminal for this pane.
        self.master, self.slave = os.openpty()

        # Create output stream and attach to screen
        self.sx = 120
        self.sy = 24

        self.screen = BetterScreen(self.sx, self.sy, self.write_input)
        self.stream = BetterStream()
        self.stream.attach(self.screen)

        self.set_size(self.sx, self.sy)
        self._start()
        self._process_pty_output()
        self._waitpid()

    def _start(self):
        os.environ['TERM'] = 'screen'
        pid = os.fork()

        if pid == 0:
            self._in_child()
        elif pid > 0:
            # In parent.
            os.close(self.slave)
            self.slave = None

            # We wait a very short while, to be sure the child had the time to
            # call _exec. (Otherwise, we are still sharing signal handlers and
            # FDs.) Resizing the pty, when the child is still in our Python
            # code and has the signal handler from prompt_toolkit, but closed
            # the 'fd' for 'call_from_executor', will cause OSError.
            time.sleep(0.1)

            self.pid = pid

    def _waitpid(self):
        def wait_for_finished():
            " Wait for PID in executor. "
            os.waitpid(self.pid, 0)
            self.cli.eventloop.remove_reader(self.master)

            self.cli.eventloop.call_from_executor(done)

        def done():
            " PID received. Back in the main thread. "
            self.is_terminated = True
            self.done_callback()

        self.cli.eventloop.run_in_executor(wait_for_finished)

    def set_size(self, width, height):
        set_size(self.master, height, width)
        self.screen.resize(lines=height, columns=width)

        self.screen.lines = height
        self.screen.columns = width

    def _in_child(self):
        os.close(self.master)

        # Remove signal handler for SIGWINCH as early as possible.
        # (We don't want this to be triggered when execv has not been called
        # yet.)
        signal.signal(signal.SIGWINCH, 0)

        # Set terminal variable. (We emulate xterm.)
        os.environ['TERM'] = 'xterm-256color'

        pty_make_controlling_tty(self.slave)

        # In the fork, set the stdin/out/err to our slave pty.
        os.dup2(self.slave, 0)
        os.dup2(self.slave, 1)
        os.dup2(self.slave, 2)

        # Execute in child.
        try:
            self._close_file_descriptors()
            username = getpass.getuser()
            shell = pwd.getpwnam(username).pw_shell
            os.execv(shell, [shell])
        except Exception:
            traceback.print_exc()
            time.sleep(5)

            os._exit(1)
        os._exit(0)

    def _close_file_descriptors(self):
        # Do not allow child to inherit open file descriptors from parent.
        # (In case that we keep running Python code. We shouldn't close them.
        # because the garbage collector is still active, and he will close them
        # eventually.)
        max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[-1]

        try:
            os.closerange(3, max_fd)
        except OverflowError:
            # On OS X, max_fd can return very big values, than closerange
            # doesn't understand, e.g. 9223372036854775807. In this case, just
            # use 4096. This is what Linux systems report, and should be
            # sufficient. (I hope...)
            os.closerange(3, 4096)

    def write_input(self, data):
        " Write user key strokes to the input. "
        while True:
            try:
                os.write(self.master, data.encode('utf-8'))
            except OSError as e:
                # This happens when the window resizes and a SIGWINCH was received.
                # We get 'Error: [Errno 4] Interrupted system call'
                if e.errno == 4:
                    continue
            return

    def _process_pty_output(self):
        # Master side -> attached to terminal emulator.
        reader = PosixStdinReader(self.master)

        def read():
            d = reader.read()
            self.stream.feed(d)
            self.cli.invalidate()

        # Connect read pipe.
        self.cli.eventloop.add_reader(self.master, read)

    def get_cwd(self):
        return get_cwd_for_pid(self.pid)

    def get_name(self):
        # TODO: Cache for short time.
        return get_name_for_fd(self.master)


def get_cwd_for_pid(pid):
    if sys.platform == 'linux':
        try:
            return os.readlink('/proc/%s/cwd' % pid)
        except OSError:
            pass

def get_name_for_fd(fd):
    if sys.platform == 'linux':
        pgrp = os.tcgetpgrp(fd)

        try:
            with open('/proc/%s/cmdline' % pgrp, 'rb') as f:
                return f.read().decode('utf-8', 'ignore').split('\0')[0]
        except IOError:
            pass
