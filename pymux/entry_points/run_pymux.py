#!/usr/bin/env python
"""
pymux: Pure Python terminal multiplexer.
Usage:
    pymux [(standalone|server|attach)] [-d] [(-s <socket>)] [(--log <logfile>)]
    pymux list-sessions
    pymux -h | --help
    pymux <command>

Options:
    standalone   : Run as a standalone process. (for debugging, detaching is
                   not possible.
    server       : Run a server daemon that can be attached later on.
    attach       : Attach to a running session.

    -s           : Unix socket path.
    -d           : Detach all other clients, when attaching.
    --log        : Logfile.
"""
from __future__ import unicode_literals, absolute_import

from pymux.main import Pymux
from pymux.client import Client, list_clients
from pymux.utils import daemonize

import docopt
import os
import sys
import logging

__all__ = (
    'run',
)


def run():
    a = docopt.docopt(__doc__)
    socket_name = a['<socket>'] or os.environ.get('PYMUX')
    socket_name_from_env = not a['<socket>'] and os.environ.get('PYMUX')

    mux = Pymux()

    # Setup logging
    if a['<logfile>']:
        logging.basicConfig(filename=a['<logfile>'], level=logging.DEBUG)

    if a['standalone']:
        mux.run_standalone()

    elif a['list-sessions']:
        for c in list_clients():
            print(c.socket_name)

    elif a['server']:
        if socket_name_from_env:
            _socket_from_env_warning()
            sys.exit(1)

        # Log to stdout.
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

        # Run server.
        socket_name = mux.listen_on_socket()
        mux.run_server()

    elif a['attach']:
        if socket_name_from_env:
            _socket_from_env_warning()
            sys.exit(1)

        if socket_name:
            Client(socket_name).attach()
        else:
            # Connect to the first server.
            for c in list_clients():
                c.attach()
                break

    elif a['<command>'] and socket_name:
        Client(socket_name).run_command(a['<command>'])

    elif not a['<command>']:
        if socket_name_from_env:
            _socket_from_env_warning()
            sys.exit(1)

        # Run client/server combination.
        socket_name = mux.listen_on_socket(socket_name)
        pid = daemonize()

        if pid > 0:
            # Create window. It is important that this happens in the daemon,
            # because the parent of the process running inside should be this
            # daemon. (Otherwise the `waitpid` call won't work.)
            mux.run_server()
        else:
            Client(socket_name).attach()

    else:
        print('Invalid command.')
        sys.exit(1)


def _socket_from_env_warning():
    print('Please be careful nesting pymux sessions.')
    print('Unset PYMUX environment variable first.')


if __name__ == '__main__':
    run()
