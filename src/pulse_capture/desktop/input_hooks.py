"""Mouse clicks and keyboard shortcuts via pynput (Phase 1.2 build step 1).

pynput wraps Win32 low-level hooks (WH_MOUSE_LL / WH_KEYBOARD_LL) so we get
the "thin, maintained, saves ctypes boilerplate" tradeoff the blueprint
calls for, without pulling in pywinauto/uiautomation (automation-driving
frameworks -- the wrong tool for *observing*).

The no-keylogging guarantee (research log §5.3, restated in the blueprint):
typed CHARACTERS are never captured here, or anywhere in this module, full
stop. The keyboard hook only ever recognizes a small, fixed set of named
shortcuts (Ctrl/Cmd+C/V/X/Z/A, Tab, Enter, Esc, F1-F12) and modifier keys
used to detect them. An ordinary letter/digit key press that is not part of
a tracked combo is dropped in the callback itself -- it never reaches a
queue, a log, or a variable that outlives the callback. This is enforced
at the earliest possible point, not filtered out later.

Typed field VALUES are Phase 1.3's job (UIA ValuePattern change events),
which also carries the field identity and whether it's a password field --
information this module has no way to know anyway.

Both listeners' callbacks do the minimum: timestamp + read the (cheap)
foreground hwnd + enqueue. No resolution work happens here.
"""

from __future__ import annotations

import contextlib
import queue
import time
from dataclasses import dataclass
from typing import Any, Literal

import win32gui
from pynput import keyboard, mouse

MouseAction = Literal["click", "double_click", "context_click"]


@dataclass(frozen=True, slots=True)
class RawClickEvent:
    action: MouseAction
    x: int
    y: int
    hwnd: int
    t_mono_ns: int
    t_wall_utc_us: int


@dataclass(frozen=True, slots=True)
class RawShortcutEvent:
    shortcut: str  # e.g. "ctrl+c", "tab", "f5" -- NEVER a raw character key
    hwnd: int
    t_mono_ns: int
    t_wall_utc_us: int


def _now() -> tuple[int, int]:
    return time.monotonic_ns(), time.time_ns() // 1_000


def _foreground_hwnd() -> int:
    try:
        return win32gui.GetForegroundWindow()
    except Exception:
        return 0


# --------------------------------------------------------------------------
# Mouse
# --------------------------------------------------------------------------


class MouseHookSource:
    """Distinguishes click / double_click / context_click from raw button
    press/release pairs. Windows' own double-click time/threshold
    (GetDoubleClickTime, SM_CXDOUBLECLK/SM_CYDOUBLECLK) is used so this
    matches the user's actual OS setting rather than a guessed constant.
    """

    def __init__(self, raw_queue: queue.Queue[Any]) -> None:
        # Typed loosely (Any) rather than queue.Queue[RawClickEvent]: in
        # the real orchestrator (host.py) this queue is intentionally
        # SHARED across all three raw-event sources (window/mouse/
        # keyboard) so a single resolver thread can drain them in true
        # arrival order. queue.Queue is invariant, so a caller passing a
        # queue.Queue[RawWindowEvent | RawClickEvent | RawShortcutEvent]
        # can't satisfy a narrower declared parameter type. What actually
        # matters -- that only RawClickEvent instances are ever put() by
        # THIS class -- is enforced by _emit() below, not by this
        # annotation.
        self._raw_queue = raw_queue
        self._listener: mouse.Listener | None = None
        self._last_left_click: tuple[float, int, int] | None = None  # (t_mono_s, x, y)

        import ctypes

        self._double_click_ms = ctypes.windll.user32.GetDoubleClickTime()
        self._double_click_px = ctypes.windll.user32.GetSystemMetrics(36)  # SM_CXDOUBLECLK
        if self._double_click_px <= 0:
            self._double_click_px = 4

    def start(self) -> None:
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=5)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if pressed:
            return  # act on release, so we have a complete click
        t_mono_ns, t_wall_us = _now()
        hwnd = _foreground_hwnd()

        if button == mouse.Button.right:
            self._emit("context_click", x, y, hwnd, t_mono_ns, t_wall_us)
            return

        if button != mouse.Button.left:
            return  # middle/extra buttons: not modeled as a Stage 1 event type yet

        action: MouseAction = "click"
        now_s = t_mono_ns / 1e9
        if self._last_left_click is not None:
            prev_t, prev_x, prev_y = self._last_left_click
            within_time = (now_s - prev_t) * 1000.0 <= self._double_click_ms
            within_space = abs(x - prev_x) <= self._double_click_px and abs(y - prev_y) <= self._double_click_px
            if within_time and within_space:
                action = "double_click"
                self._last_left_click = None  # consume the pair
                self._emit(action, x, y, hwnd, t_mono_ns, t_wall_us)
                return
        self._last_left_click = (now_s, x, y)
        self._emit(action, x, y, hwnd, t_mono_ns, t_wall_us)

    def _emit(self, action: MouseAction, x: int, y: int, hwnd: int, t_mono_ns: int, t_wall_us: int) -> None:
        with contextlib.suppress(queue.Full):
            self._raw_queue.put_nowait(
                RawClickEvent(action=action, x=x, y=y, hwnd=hwnd, t_mono_ns=t_mono_ns, t_wall_utc_us=t_wall_us)
            )


# --------------------------------------------------------------------------
# Keyboard -- shortcuts only, never characters
# --------------------------------------------------------------------------

_TRACKED_CTRL_COMBOS = {"c", "v", "x", "z", "a"}  # Ctrl+C/V/X/Z/A
_NAMED_KEYS: dict[keyboard.Key, str] = {
    keyboard.Key.tab: "tab",
    keyboard.Key.enter: "enter",
    keyboard.Key.esc: "esc",
    keyboard.Key.f1: "f1",
    keyboard.Key.f2: "f2",
    keyboard.Key.f3: "f3",
    keyboard.Key.f4: "f4",
    keyboard.Key.f5: "f5",
    keyboard.Key.f6: "f6",
    keyboard.Key.f7: "f7",
    keyboard.Key.f8: "f8",
    keyboard.Key.f9: "f9",
    keyboard.Key.f10: "f10",
    keyboard.Key.f11: "f11",
    keyboard.Key.f12: "f12",
}
_CTRL_KEYS = {keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl}


class KeyboardHookSource:
    def __init__(self, raw_queue: queue.Queue[Any]) -> None:
        # See MouseHookSource.__init__ for why this is loosely typed.
        self._raw_queue = raw_queue
        self._listener: keyboard.Listener | None = None
        self._ctrl_down = False

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=5)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key in _CTRL_KEYS:
            self._ctrl_down = False

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        # Hot path: no logging, no buffering of ANY character. Only a
        # closed set of named/shortcut keys is ever turned into an event.
        if key in _CTRL_KEYS:
            self._ctrl_down = True
            return

        shortcut: str | None = None

        if isinstance(key, keyboard.KeyCode):
            # KeyCode covers plain character keys. We only ever look at
            # `.char` to check membership in the tracked Ctrl-combo set --
            # if it's not one of those specific letters, or Ctrl isn't
            # held, NOTHING is recorded, kept, or derived from this key
            # press. There is no path from here to a stored character.
            if self._ctrl_down and key.char is not None and key.char.lower() in _TRACKED_CTRL_COMBOS:
                shortcut = f"ctrl+{key.char.lower()}"
        elif key in _NAMED_KEYS:
            shortcut = _NAMED_KEYS[key]

        if shortcut is None:
            return  # not a tracked shortcut -- dropped here, permanently

        t_mono_ns, t_wall_us = _now()
        hwnd = _foreground_hwnd()
        with contextlib.suppress(queue.Full):
            self._raw_queue.put_nowait(
                RawShortcutEvent(shortcut=shortcut, hwnd=hwnd, t_mono_ns=t_mono_ns, t_wall_utc_us=t_wall_us)
            )
