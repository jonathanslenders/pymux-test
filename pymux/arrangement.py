"""
Arrangement of panes.

Don't confuse with the prompt_toolkit VSplit/HSplit classes. This is a much
higher level abstraction.
"""
from __future__ import unicode_literals
from .process import Process

import os
import weakref

__all__ = (
    'Pane',
    'Window',
    'Arrangement',
)


class Pane(object):
    def __init__(self, process):
        assert isinstance(process, Process)

        self.process = process
        self.name = None


class HSplit(list):
    """ Horizontal split. (This is a higher level split than
    prompt_toolkit.layout.HSplit.) """

    def __repr__(self):
        return 'HSplit(%s)' % list.__repr__(self)


class VSplit(list):
    """ Horizontal split. """

    def __repr__(self):
        return 'VSplit(%s)' % list.__repr__(self)


class Window(object):
    """
    Pymux window.
    """
    def __init__(self):
        self.root = HSplit()
        self._active_pane = None
        self._prev_active_pane = None
        self.chosen_name = None

        #: When true, the current pane is zoomed in.
        self.zoom = False

    @property
    def active_pane(self):
        return self._active_pane

    @active_pane.setter
    def active_pane(self, value):
        # Remember previous active pane.
        if self._active_pane:
            self._prev_active_pane = weakref.ref(self._active_pane)

        self.zoom = False
        self._active_pane = value

    @property
    def previous_active_pane(self):
        " The previous active pane or None if unknown. "
        p = self._prev_active_pane and self._prev_active_pane()

        # Only return when this pane actually still exists in the current
        # window.
        if p and p in self.panes:
            return p

    @property
    def name(self):
        # Name, explicitely set for the window.
        if self.chosen_name:
            return self.chosen_name
        else:
            pane = self.active_pane
            if pane:
                # Name, explicitely set for the pane.
                if pane.name:
                    return pane.name
                else:
                    # Name from the process running inside the pane.
                    name = pane.process.get_name()
                    if name:
                        return os.path.basename(name)

        return '(noname)'

    def add_pane(self, pane, vsplit=False):
        assert isinstance(pane, Pane)
        assert isinstance(vsplit, bool)

        split_cls = VSplit if vsplit else HSplit

        if self.active_pane is None:
            self.root.append(pane)
        else:
            parent = self._get_parent(self.active_pane)
            same_direction = isinstance(parent, split_cls)

            index = parent.index(self.active_pane)

            if same_direction:
                parent.insert(index + 1, pane)
            else:
                new_split = split_cls([self.active_pane, pane])
                parent[index] = new_split

        self.active_pane = pane
        self.zoom = False

    def remove_pane(self, pane):
        assert isinstance(pane, Pane)

        if pane in self.panes:
            # When this pane was focused. Focus next.
            if pane == self.active_pane:
                self.focus_next()

            # Remove from the parent. When the parent becomes empty, remove the
            # parent itself recursively.
            p = self._get_parent(pane)
            p.remove(pane)

            while len(p) == 0 and p != self.root:
                p2 = self._get_parent(p)
                p2.remove(p)
                p = p2

            # When the parent has only one item left, collapse into its parent.
            while len(p) == 1 and p != self.root:
                p2 = self._get_parent(p)
                i = p2.index(p)
                p2[i] = p[0]
                p = p2

    @property
    def panes(self):
        " All panes from this Window. "
        result = []

        for s in self.splits:
            for item in s:
                if isinstance(item, Pane):
                    result.append(item)

        return result

    @property
    def splits(self):
        " Return all HSplit/VSplit instances. "
        result = []

        def collect(split):
            result.append(split)

            for item in split:
                if isinstance(item, (HSplit, VSplit)):
                    collect(item)

        collect(self.root)
        return result

    def _get_parent(self, item):
        " The HSplit/VSplit that contains the active pane. "
        for s in self.splits:
            if item in s:
                return s

    @property
    def has_panes(self):
        " True when this window contains at least one pane. "
        return len(self.panes) > 0

    @property
    def active_process(self):
        " Return `Process` that should receive user input. "
        p = self.active_pane

        if p is not None:
            return p.process

    def focus_next(self):
        " Focus the next pane. "
        panes = self.panes
        self.active_pane = panes[(panes.index(self.active_pane) + 1) % len(panes)]


class Arrangement(object):
    def __init__(self):
        self.windows = []
        self._active_window = None
        self._prev_active_window = None

    @property
    def active_window(self):
        return self._active_window

    @active_window.setter
    def active_window(self, value):
        if self._active_window:
            self._prev_active_window = weakref.ref(self._active_window)
        self._active_window = value

    @property
    def previous_active_window(self):
        " The previous active Window or None if unknown. "
        w = self._prev_active_window and self._prev_active_window()

        if w and w in self.windows:
            return w

    def create_window(self, pane):
        " Create a new window that contains just this pane. "
        assert isinstance(pane, Pane)

        w = Window()
        w.add_pane(pane)
        self.windows.append(w)
        self.active_window = w

        assert w.active_pane == pane
        assert w._get_parent(pane)

    @property
    def active_pane(self):
        " Return the active :class:`.Pane` or `None`."
        if self.active_window is not None:
            return self.active_window.active_pane

    @property
    def active_process(self):
        " Return `Process` that should receive user input. "
        p = self.active_pane
        if p is not None:
            return p.process

    def remove_pane(self, pane):
        assert isinstance(pane, Pane)

        for w in self.windows:
            w.remove_pane(pane)

            # No panes left in this window?
            if not w.has_panes:
                self.focus_next_window()
                self.windows.remove(w)


    def remove_dead_panes(self):
        for w in self.windows[:]:
            for pane in w.panes:
                if pane.process.is_terminated:
                    w.remove_pane(pane)

            # No panes left in this window?
            if not w.has_panes:
                self.focus_previous_window()
                self.windows.remove(w)

    def focus_previous_window(self):
        self.active_window = self.windows[
            (self.windows.index(self.active_window) - 1) % len(self.windows)]

    def focus_next_window(self):
        self.active_window = self.windows[
            (self.windows.index(self.active_window) + 1) % len(self.windows)]

    def break_pane(self):
        """ When the current window has multiple panes, remove the pane from
        this window and put it in a new window. """
        if len(self.active_window.panes) > 1:
            pane = self.active_window.active_pane
            self.active_window.remove_pane(pane)
            self.create_window(pane)

    @property
    def has_panes(self):
        for w in self.windows:
            if w.has_panes:
                return True
        return False
