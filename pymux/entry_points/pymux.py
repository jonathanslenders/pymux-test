#!/usr/bin/env python
"""
pymux: Pure Python terminal multiplexer.
Usage:
    pymux
    pymux standalone
    pymux server [-s <socket>]
    pymux attach [-s <socket>]
    pymux list-sessions
    pymux -h | --help
    pymux <command>

Options:
    standalone   : Run as a standalone process. (for debugging, detaching is
                   not possible.
"""
from __future__ import unicode_literals, absolute_import

from pymux.main import Pymux
from pymux.client import Client, list_clients
from pymux.utils import daemonize
import docopt
import os

__all__ = (
    'run',
)


def run():
    a = docopt.docopt(__doc__)
    socket_name = a['<socket>'] or os.environ.get('PYMUX')

    setup_debugger()

    mux = Pymux()

    if a['standalone']:
        mux.run_standalone()
        mux.create_window()

    elif a['list-sessions']:
        for c in list_clients():
            print(c.socket_name)
    elif a['server']:
        socket_name = mux.listen_on_socket()
        mux.create_window()
        mux.run_server()
    elif a['attach']:
        if socket_name:
            Client(socket_name).attach()
        else:
            # Connect to the first server.
            for c in list_clients():
                c.attach()
                break
    elif a['<command>']:
        Client(socket_name).run_command(a['<command>'])
    else:
        # Run client/server combination.
        socket_name = mux.listen_on_socket(socket_name)
        pid = daemonize()


        if pid > 0:
            # Create window. It is important that this happens in the daemon,
            # because the parent of the process running inside should be this
            # daemon. (Otherwise the `waitpid` call won't work.)
            mux.create_window()
            mux.run_server()
        else:
            Client(socket_name).attach()


def setup_debugger():
    # http://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
    import code, traceback, signal

    def debug(sig, frame):
        """Interrupt running process, and provide a python prompt for
        interactive debugging."""
        d={'_frame':frame}         # Allow access to frame object.
        d.update(frame.f_globals)  # Unless shadowed by global
        d.update(frame.f_locals)

        i = code.InteractiveConsole(d)
        message  = "Signal received : entering python shell.\nTraceback:\n"
        message += ''.join(traceback.format_stack(frame))
        i.interact(message)

    signal.signal(signal.SIGUSR1, debug)  # Register handler

if __name__ == '__main__':
    run()
