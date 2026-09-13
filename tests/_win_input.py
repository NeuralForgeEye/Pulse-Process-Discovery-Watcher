"""Real synthetic input via SendInput, for Phase 1.3/1.4 test drivers.

SendInput injects into the actual OS input stream -- unlike PostMessage or a
UIA Invoke pattern call, this is what the low-level mouse/keyboard hooks
(Phase 1.2) genuinely see, which matters here because these tests are meant
to exercise the real hot path, not bypass it. Acceptable as a TEST-RIG
driving mechanism per the same precedent the blueprint itself sets for
Phase 1.2's checkpoint ("an automated driver... acceptable here because it
is the test rig, not the product").
"""

from __future__ import annotations

import contextlib
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_HOME = 0x24
VK_END = 0x23
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_A = 0x41


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


def _send(*inputs: _INPUT) -> None:
    n = len(inputs)
    arr = (_INPUT * n)(*inputs)
    user32.SendInput(n, arr, ctypes.sizeof(_INPUT))


def move_to(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)
    time.sleep(0.02)


def click(x: int, y: int, settle_s: float = 0.05) -> None:
    move_to(x, y)
    _send(_INPUT(INPUT_MOUSE, _INPUT_UNION(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None))))
    time.sleep(settle_s)
    _send(_INPUT(INPUT_MOUSE, _INPUT_UNION(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None))))
    time.sleep(settle_s)


def drag(x1: int, y1: int, x2: int, y2: int, steps: int = 8, settle_s: float = 0.4) -> None:
    """A real mouse-down, real intermediate moves, real mouse-up -- what the
    Phase 1.4 fallback's drag-distance heuristic and, for TextPattern
    controls, the primary selection mechanism both need to see.
    """
    move_to(x1, y1)
    _send(_INPUT(INPUT_MOUSE, _INPUT_UNION(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None))))
    time.sleep(0.03)
    for i in range(1, steps + 1):
        ix = x1 + (x2 - x1) * i // steps
        iy = y1 + (y2 - y1) * i // steps
        user32.SetCursorPos(ix, iy)
        time.sleep(0.02)
    _send(_INPUT(INPUT_MOUSE, _INPUT_UNION(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None))))
    time.sleep(settle_s)  # allow the debounce settle window to elapse before the caller reads state


def key_down(vk: int) -> None:
    _send(_INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(vk, 0, 0, 0, None))))


def key_up(vk: int) -> None:
    _send(_INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None))))


def select_all(settle_s: float = 0.4) -> None:
    key_down(VK_CONTROL)
    key_down(VK_A)
    time.sleep(0.03)
    key_up(VK_A)
    key_up(VK_CONTROL)
    time.sleep(settle_s)


SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001


def make_topmost(hwnd: int) -> None:
    """Pin a fixture window above everything else on the real, actively-used
    desktop these tests run against. Observed necessity, not caution for its
    own sake: mid-test, real background activity on the user's own machine
    (a browser tab, another app) can steal foreground focus between
    `force_foreground` and the moment a click is actually processed, which
    then makes ElementFromPoint resolve to whatever real window is now
    sitting at that screen location instead of the fixture app. Topmost
    keeps the fixture window there regardless of *focus*, which is what
    element-at-a-point resolution actually depends on.
    """
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)


def force_foreground(hwnd: int) -> None:
    """SetForegroundWindow alone is refused by Windows' anti-focus-stealing
    heuristic when the caller isn't the current foreground process (which a
    test driver process never is). Tapping Alt first resets that lock --
    a well-known, harmless workaround, not a real keypress the user asked
    for; used here only to let the TEST DRIVER bring a fixture window to
    the front, same spirit as the rest of this module.
    """
    key_down(0x12)  # VK_MENU (Alt)
    key_up(0x12)
    time.sleep(0.05)
    with contextlib.suppress(Exception):
        user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)


def select_to_end_of_line(settle_s: float = 0.4) -> None:
    """Home, then Shift+End -- a real keyboard-driven selection."""
    key_down(VK_HOME)
    time.sleep(0.02)
    key_up(VK_HOME)
    time.sleep(0.05)
    key_down(VK_SHIFT)
    key_down(VK_END)
    time.sleep(0.03)
    key_up(VK_END)
    key_up(VK_SHIFT)
    time.sleep(settle_s)
