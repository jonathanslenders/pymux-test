"""
"""
from __future__ import unicode_literals

class Pane(object):
    def __init__(self):
        pass


class HSplit(list):
    """ Horizontal split. (This is a higher level split than
    prompt_toolkit.layout.HSplit.) """


class VSplit(list):
    """ Horizontal split. """


class Window(object):
    def __init__(self):
        self.root = HSplit()


class Arrangement(object):
    def __init__(self):
        self.windows = []
