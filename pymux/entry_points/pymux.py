#!/usr/bin/env python
"""
pymux: Pure Python terminal multiplexer.
Usage:
    pymux
"""
from __future__ import unicode_literals, absolute_import

from pymux.main import PyMux
import docopt

__all__ = (
    'run',
)


def run():
    a = docopt.docopt(__doc__)

    mux = PyMux()
    mux.add_process()
    mux.run()


if __name__ == '__main__':
    run()
