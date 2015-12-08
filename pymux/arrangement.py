"""
Arrangement of panes.

Don't confuse with the prompt_toolkit VSplit/HSplit classes. This is a higher
level abstraction of the Pymux window layout.
"""
from __future__ import unicode_literals
from .process import Process

from prompt_toolkit.interface import CommandLineInterface

import math
import os
import weakref

__all__ = (
    'Pane',
    'Window',
    'Arrangement',
)

class LayoutTypes:
    # The values are in lowercase with dashes, because that is what users can
    # use at the command line.
    EVEN_HORIZONTAL = 'even-horizontal'
    EVEN_VERTICAL = 'even-vertical'
    MAIN_HORIZONTAL = 'main-horizontal'
    MAIN_VERTICAL = 'main-vertical'
    TILED = 'tiled'

    _ALL = [EVEN_HORIZONTAL, EVEN_VERTICAL, MAIN_HORIZONTAL, MAIN_VERTICAL, TILED]


class Pane(object):
    _pane_counter = 0

    def __init__(self, process):
        assert isinstance(process, Process)

        self.process = process
        self.name = None

        # Displayed the clock instead of this pane content.
        self.clock_mode = False

        # Give unique ID.
        Pane._pane_counter += 1
        self.pane_id = Pane._pane_counter



class _Split(list):
    """ Base class for horizontal and vertical splits. (This is a higher level
    split than prompt_toolkit.layout.HSplit.) """
    def __init__(self, *a, **kw):
        list.__init__(self, *a, **kw)

        # Mapping children to its weight.
        self.weights = weakref.WeakKeyDictionary()

    def __hash__(self):
        # Required in order to add HSplit/VSplit to the weights dict. "
        return id(self)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, list.__repr__(self))


class HSplit(_Split):
    """ Horizontal split. """


class VSplit(_Split):
    """ Horizontal split. """


class Window(object):
    """
    Pymux window.
    """
    _window_counter = 0

    def __init__(self):
        self.root = HSplit()
        self._active_pane = None
        self._prev_active_pane = None
        self.chosen_name = None
        self.previous_selected_layout = None

        #: When true, the current pane is zoomed in.
        self.zoom = False

        # Give unique ID.
        Window._window_counter += 1
        self.window_id = Window._window_counter

    def invalidation_hash(self):
        """
        Return a hash (string) that can be used to determine when the layout
        has to be rebuild.
        """
        def _hash_for_split(split):
            result = []
            for item in split:
                if isinstance(item, (VSplit, HSplit)):
                    result.append(_hash_for_split(item))
                elif isinstance(item, Pane):
                    result.append('p%s' % item.pane_id)

            if isinstance(split, HSplit):
                return 'HSplit(%s)' % (','.join(result))
            else:
                return 'VSplit(%s)' % (','.join(result))

        return '<window_id=%s,zoom=%s,children=%s>' % (
            self.window_id, self.zoom, _hash_for_split(self.root))

    @property
    def active_pane(self):
        return self._active_pane

    @active_pane.setter
    def active_pane(self, value):
        assert isinstance(value, Pane)

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
        """
        Add another pane to this Window.
        """
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

                # Give the newly created split the same weight as the original
                # pane that was at this position.
                parent.weights[new_split] = parent.weights[self.active_pane]


        self.active_pane = pane
        self.zoom = False

    def remove_pane(self, pane):
        """
        Remove pane from this Window.
        """
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

    def rotate(self, count=1, with_pane_before_only=False, with_pane_after_only=False):
        """
        Rotate panes.
        When `with_pane_before_only` or `with_pane_after_only` is True, only rotate
        with the pane before/after the active pane.
        """
        # Create (split, index, pane, weight) tuples.
        items = []
        current_pane_index = None

        for s in self.splits:
            for index, item in enumerate(s):
                if isinstance(item, Pane):
                    items.append((s, index, item, s.weights[item]))
                    if item == self.active_pane:
                        current_pane_index = len(items) - 1

        # Only before after? Reduce list of panes.
        if with_pane_before_only:
            items = items[current_pane_index - 1:current_pane_index + 1]

        elif with_pane_after_only:
            items = items[current_pane_index:current_pane_index + 2]

        # Rotate positions.
        for i, triple in enumerate(items):
            split, index, pane, weight = triple

            new_item = items[(i + count) % len(items)][2]

            split[index] = new_item
            split.weights[new_item] = weight

    def select_layout(self, layout_type):
        """
        Select one of the predefined layouts.
        """
        assert layout_type in LayoutTypes._ALL

        # When there is only one pane, always choose EVEN_HORIZONTAL,
        # Otherwise, we create VSplit/HSplit instances with an empty list of
        # children.
        if len(self.panes) == 1:
            layout_type = LayoutTypes.EVEN_HORIZONTAL

        # even-horizontal.
        if layout_type == LayoutTypes.EVEN_HORIZONTAL:
            self.root = HSplit(self.panes)

        # even-vertical.
        elif layout_type == LayoutTypes.EVEN_VERTICAL:
            self.root = VSplit(self.panes)

        # main-horizontal.
        elif layout_type == LayoutTypes.MAIN_HORIZONTAL:
            self.root = HSplit([
                self.active_pane,
                VSplit([p for p in self.panes if p != self.active_pane])
            ])

        # main-vertical.
        elif layout_type == LayoutTypes.MAIN_VERTICAL:
            self.root = VSplit([
                self.active_pane,
                HSplit([p for p in self.panes if p != self.active_pane])
            ])

        # tiled.
        elif layout_type == LayoutTypes.TILED:
            panes = self.panes
            column_count = math.ceil(len(panes) ** .5)

            rows = HSplit()
            current_row = VSplit()

            for p in panes:
                current_row.append(p)

                if len(current_row) >= column_count:
                    rows.append(current_row)
                    current_row = VSplit()
            if current_row:
                rows.append(current_row)

            self.root = rows

        self.previous_selected_layout = layout_type

    def select_next_layout(self, count=1):
        """
        Select next layout. (Cycle through predefined layouts.)
        """
        layout = self.previous_selected_layout or LayoutTypes._ALL[-1]
        index = LayoutTypes._ALL.index(layout)
        new_layout = LayoutTypes._ALL[(index + count) % len(LayoutTypes._ALL)]
        self.select_layout(new_layout)

    def select_previous_layout(self):
        self.select_next_layout(count=-1)

    def change_size_for_active_pane(self, up=0, right=0, down=0, left=0):
        """
        Increase the size of the current pane in any of the four directions.
        """
        child = self.active_pane
        self.change_size_for_pane(child, up=up, right=right, down=down, left=left)

    def change_size_for_pane(self, pane, up=0, right=0, down=0, left=0):
        """
        Increase the size of the current pane in any of the four directions.
        Positive values indicate an increase, negative values a decrease.
        """
        def find_split_and_child(split_cls, is_before):
            " Find the split for which we will have to update the weights. "
            child = pane
            split = self._get_parent(child)

            def found():
                return isinstance(split, split_cls) and (
                    not is_before or split.index(child) > 0) and (
                    is_before or split.index(child) < len(split) - 1)

            while split and not found():
                child = split
                split = self._get_parent(child)

            return split, child # split can be None!

        def handle_side(split_cls, is_before, amount, trying_other_side=False):
            " Increase weights on one side. (top/left/right/bottom). "
            if amount:
                split, child = find_split_and_child(split_cls, is_before)

                if split:
                    # Find neighbour.
                    neighbour_index = split.index(child) + (-1 if is_before else 1)
                    neighbour_child = split[neighbour_index]

                    # Increase/decrease weights.
                    split.weights[child] += amount
                    split.weights[neighbour_child] -= amount

                    # Ensure that all weights are at least one.
                    for k, value in split.weights.items():
                        if value < 1:
                            split.weights[k] = 1

                else:
                    # When no split has been found where we can move in this
                    # direction, try to move the other side instead using a
                    # negative amount. This happens when we run "resize-pane -R 4"
                    # inside the pane that is completely on the right. In that
                    # case it's logical to move the left border to the right
                    # instead.
                    if not trying_other_side:
                        handle_side(split_cls, not is_before, -amount,
                                    trying_other_side=True)

        handle_side(VSplit, True, left)
        handle_side(VSplit, False, right)
        handle_side(HSplit, True, up)
        handle_side(HSplit, False, down)

    def get_pane_index(self, pane):
        " Return the index of the given pane. ValueError if not found. "
        assert isinstance(pane, Pane)
        return self.panes.index(pane)


class Arrangement(object):
    """
    Arrangement class for one Pymux session.
    This contains the list of windows and the layout of the panes for each
    window. All the clients share the same Arrangement instance, but they can
    have different windows active.
    """
    def __init__(self):
        self.windows = []

        self._active_window_for_cli = weakref.WeakKeyDictionary()
        self._prev_active_window_for_cli = weakref.WeakKeyDictionary()

    def invalidation_hash(self, cli):
        """
        When this changes, the layout needs to be rebuild.
        """
        w = self.get_active_window(cli)
        return w.invalidation_hash()

    def get_active_window(self, cli):
        assert isinstance(cli, CommandLineInterface)

        try:
            return self._active_window_for_cli[cli]
        except KeyError:
            self._active_window_for_cli[cli] = self.windows[0]
            return self.windows[0]

    def set_active_window(self, cli, window):
        assert isinstance(cli, CommandLineInterface)
        assert isinstance(window, Window)

        previous = self.get_active_window(cli)
        self._prev_active_window_for_cli[cli] = previous
        self._active_window_for_cli[cli] = window

    def set_active_window_from_pane_id(self, cli, pane_id):
        """
        Make the window with this pane ID the active Window.
        """
        assert isinstance(cli, CommandLineInterface)
        assert isinstance(pane_id, int)

        for w in self.windows:
            for p in w.panes:
                if p.pane_id == pane_id:
                    self.set_active_window(cli, w)

    def get_previous_active_window(self, cli):
        " The previous active Window or None if unknown. "
        assert isinstance(cli, CommandLineInterface)

        try:
            return self._prev_active_window_for_cli[cli]
        except KeyError:
            return None

    def create_window(self, cli, pane):
        """
        Create a new window that contains just this pane.
        If `cli` has been given, this window will be focussed for that client.
        """
        assert isinstance(pane, Pane)
        assert cli is None or isinstance(cli, CommandLineInterface)

        w = Window()
        w.add_pane(pane)
        self.windows.append(w)

        if cli is not None:
            self.set_active_window(cli, w)

        assert w.active_pane == pane
        assert w._get_parent(pane)

    def get_active_pane(self, cli):
        assert isinstance(cli, CommandLineInterface)

        w = self.get_active_window(cli)
        if w is not None:
            return w.active_pane

    def remove_pane(self, pane):
        assert isinstance(pane, Pane)

        for w in self.windows:
            w.remove_pane(pane)

            # No panes left in this window?
            if not w.has_panes:
                # Focus next.
                for cli, active_w in self._active_window_for_cli.items():
                    if w == active_w:
                        self.focus_next_window(cli)

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

    def focus_previous_window(self, cli):
        assert isinstance(cli, CommandLineInterface)

        w = self.get_active_window(cli)

        self.set_active_window(cli, self.windows[
            (self.windows.index(w) - 1) % len(self.windows)])

    def focus_next_window(self, cli):
        assert isinstance(cli, CommandLineInterface)

        w = self.get_active_window(cli)

        self.set_active_window(cli, self.windows[
            (self.windows.index(w) + 1) % len(self.windows)])

    def break_pane(self, cli):
        """ When the current window has multiple panes, remove the pane from
        this window and put it in a new window. """
        assert isinstance(cli, CommandLineInterface)

        w = self.get_active_window(cli)

        if len(w.panes) > 1:
            pane = w.active_pane
            self.get_active_window(cli).remove_pane(pane)
            self.create_window(cli, pane)

    def rotate_window(self, cli, count=1):
        " Rotate the panes in the active window. "
        assert isinstance(cli, CommandLineInterface)

        w = self.get_active_window(cli)
        w.rotate(count=count)

    @property
    def has_panes(self):
        for w in self.windows:
            if w.has_panes:
                return True
        return False
