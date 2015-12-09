from __future__ import unicode_literals
from prompt_toolkit.keys import Keys

__all__ = (
    'pymux_key_to_prompt_toolkit_key_sequence',
    'PYMUX_TO_PROMPT_TOOLKIT_KEYS',
)


def pymux_key_to_prompt_toolkit_key_sequence(key):
    """
    Turn a pymux description of a key. E.g.  "C-a" or "M-x" into a
    prompt-toolkit key sequence.
    """
    if len(key) == 1 and key.isalnum():
        return key

    return PYMUX_TO_PROMPT_TOOLKIT_KEYS.get(key) or tuple(key)


PYMUX_TO_PROMPT_TOOLKIT_KEYS = {
    'C-a': (Keys.ControlA, ),
    'C-b': (Keys.ControlB, ),
    'C-c': (Keys.ControlC, ),
    'C-d': (Keys.ControlD, ),
    'C-e': (Keys.ControlE, ),
    'C-f': (Keys.ControlF, ),
    'C-g': (Keys.ControlG, ),
    'C-h': (Keys.ControlH, ),
    'C-i': (Keys.ControlI, ),
    'C-j': (Keys.ControlJ, ),
    'C-k': (Keys.ControlK, ),
    'C-l': (Keys.ControlL, ),
    'C-m': (Keys.ControlM, ),
    'C-n': (Keys.ControlN, ),
    'C-o': (Keys.ControlO, ),
    'C-p': (Keys.ControlP, ),
    'C-q': (Keys.ControlQ, ),
    'C-r': (Keys.ControlR, ),
    'C-s': (Keys.ControlS, ),
    'C-t': (Keys.ControlT, ),
    'C-u': (Keys.ControlU, ),
    'C-v': (Keys.ControlV, ),
    'C-w': (Keys.ControlW, ),
    'C-x': (Keys.ControlX, ),
    'C-y': (Keys.ControlY, ),
    'C-z': (Keys.ControlZ, ),

    'C-Left': (Keys.ControlLeft, ),
    'C-Right': (Keys.ControlRight, ),
    'C-Up': (Keys.ControlUp, ),
    'C-Down': (Keys.ControlDown, ),
    'Space': (' '),

    'M-a': (Keys.Escape, 'a'),
    'M-b': (Keys.Escape, 'b'),
    'M-c': (Keys.Escape, 'c'),
    'M-d': (Keys.Escape, 'd'),
    'M-e': (Keys.Escape, 'e'),
    'M-f': (Keys.Escape, 'f'),
    'M-g': (Keys.Escape, 'g'),
    'M-h': (Keys.Escape, 'h'),
    'M-i': (Keys.Escape, 'i'),
    'M-j': (Keys.Escape, 'j'),
    'M-k': (Keys.Escape, 'k'),
    'M-l': (Keys.Escape, 'l'),
    'M-m': (Keys.Escape, 'm'),
    'M-n': (Keys.Escape, 'n'),
    'M-o': (Keys.Escape, 'o'),
    'M-p': (Keys.Escape, 'p'),
    'M-q': (Keys.Escape, 'q'),
    'M-r': (Keys.Escape, 'r'),
    'M-s': (Keys.Escape, 's'),
    'M-t': (Keys.Escape, 't'),
    'M-u': (Keys.Escape, 'u'),
    'M-v': (Keys.Escape, 'v'),
    'M-w': (Keys.Escape, 'w'),
    'M-x': (Keys.Escape, 'x'),
    'M-y': (Keys.Escape, 'y'),
    'M-z': (Keys.Escape, 'z'),

    'M-0': (Keys.Escape, '0'),
    'M-1': (Keys.Escape, '1'),
    'M-2': (Keys.Escape, '2'),
    'M-3': (Keys.Escape, '3'),
    'M-4': (Keys.Escape, '4'),
    'M-5': (Keys.Escape, '5'),
    'M-6': (Keys.Escape, '6'),
    'M-7': (Keys.Escape, '7'),
    'M-8': (Keys.Escape, '8'),
    'M-9': (Keys.Escape, '9'),

    'M-Up': (Keys.Escape, Keys.Up),
    'M-Down': (Keys.Escape, Keys.Down, ),
    'M-Left': (Keys.Escape, Keys.Left, ),
    'M-Right': (Keys.Escape, Keys.Right, ),
    'Left': (Keys.Left, ),
    'Right': (Keys.Right, ),
    'Up': (Keys.Up, ),
    'Down': (Keys.Down, ),
    'BSpace': (Keys.Backspace, ),
    'BTab': (Keys.BackTab, ),
    'DC': (Keys.Delete, ),
    'IC': (Keys.Insert, ),
    'End': (Keys.End, ),
    'Enter': (Keys.ControlJ, ),
    'Home': (Keys.Home, ),
    'Escape': (Keys.Escape, ),
    'Tab': (Keys.Tab, ),

    'F1': (Keys.F1, ),
    'F2': (Keys.F2, ),
    'F3': (Keys.F3, ),
    'F4': (Keys.F4, ),
    'F5': (Keys.F5, ),
    'F6': (Keys.F6, ),
    'F7': (Keys.F7, ),
    'F8': (Keys.F8, ),
    'F9': (Keys.F9, ),
    'F10': (Keys.F10, ),
    'F11': (Keys.F11, ),
    'F12': (Keys.F12, ),
    'F13': (Keys.F13, ),
    'F14': (Keys.F14, ),
    'F15': (Keys.F15, ),
    'F16': (Keys.F16, ),
    'F17': (Keys.F17, ),
    'F18': (Keys.F18, ),
    'F19': (Keys.F19, ),
    'F20': (Keys.F20, ),

    'NPage': (Keys.PageDown, ),
    'PageDown': (Keys.PageDown, ),
    'PgDn': (Keys.PageDown, ),
    'PPage': (Keys.PageUp, ),
    'PageUp': (Keys.PageUp, ),
    'PgUp': (Keys.PageUp, ),

}

