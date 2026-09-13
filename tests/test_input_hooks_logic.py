"""Deterministic, OS-hook-independent tests for input_hooks.py's
classification logic.

IMPORTANT CONTEXT (see tests/test_phase1_2_desktop_capture.py's module
docstring and the Phase 1.2 results writeup for the full explanation):
this execution sandbox has session 1 ("Console") but no attached
interactive user -- GetForegroundWindow() returns 0, SetForegroundWindow
fails, and no synthetic input (via pynput's Controller or raw SendInput)
reaches ANY low-level hook, including a bare pynput Listener with no
Pulse code involved at all. That was verified directly, not assumed.

This means the OS-level input-hook *delivery* mechanism cannot be
end-to-end exercised live in this sandbox. What CAN be verified
deterministically -- and IS verified here -- is that the classification
logic inside MouseHookSource/KeyboardHookSource is correct: given a
sequence of press/release/click callback invocations (the same shape
pynput would call them with), does the right RawShortcutEvent /
RawClickEvent come out, and does the no-keylogging guarantee hold.

These tests call the private `_on_press` / `_on_release` / `_on_click`
methods directly with real pynput Key/KeyCode/Button objects -- the exact
argument types and values pynput's listener would pass -- so the only
thing NOT exercised here is the OS's own hook-delivery plumbing, which
this sandbox cannot exercise at all regardless of test design.
"""

from __future__ import annotations

import queue

from pynput import keyboard, mouse

from pulse_capture.desktop.input_hooks import KeyboardHookSource, MouseHookSource


def test_ctrl_c_produces_exactly_one_shortcut_event() -> None:
    q: queue.Queue = queue.Queue()
    src = KeyboardHookSource(q)

    src._on_press(keyboard.Key.ctrl_l)
    src._on_press(keyboard.KeyCode.from_char("c"))
    src._on_release(keyboard.Key.ctrl_l)

    events = list(q.queue)
    assert [e.shortcut for e in events] == ["ctrl+c"]


def test_named_keys_produce_shortcut_events() -> None:
    q: queue.Queue = queue.Queue()
    src = KeyboardHookSource(q)

    src._on_press(keyboard.Key.tab)
    src._on_press(keyboard.Key.enter)
    src._on_press(keyboard.Key.esc)
    src._on_press(keyboard.Key.f5)

    shortcuts = [e.shortcut for e in list(q.queue)]
    assert shortcuts == ["tab", "enter", "esc", "f5"]


def test_ctrl_combo_letters_ignored_without_ctrl_held() -> None:
    """The letters in _TRACKED_CTRL_COMBOS (c, v, x, z, a) must NOT
    produce a shortcut event when typed without Ctrl held -- otherwise
    ordinary typing of those letters would leak as "shortcut" events.
    """
    q: queue.Queue = queue.Queue()
    src = KeyboardHookSource(q)

    for ch in "cvxza":
        src._on_press(keyboard.KeyCode.from_char(ch))

    assert list(q.queue) == []


def test_sentinel_typed_without_ctrl_produces_zero_events() -> None:
    """The no-keylogging guardrail, exercised directly: type the exact
    sentinel string used in the live ground-truth checkpoint, with no
    modifier held, and confirm NOTHING is enqueued -- not the characters,
    not any derived event at all.
    """
    q: queue.Queue = queue.Queue()
    src = KeyboardHookSource(q)

    sentinel = "ZZQXSENTINEL"
    for ch in sentinel:
        src._on_press(keyboard.KeyCode.from_char(ch.lower()))
        src._on_press(keyboard.KeyCode.from_char(ch.upper()))

    assert list(q.queue) == [], "sentinel characters must never produce any event"


def test_unrelated_ctrl_combo_ignored() -> None:
    """Ctrl+<letter not in the tracked set> must not produce an event --
    proves we track a closed, specific set rather than "any Ctrl+letter"."""
    q: queue.Queue = queue.Queue()
    src = KeyboardHookSource(q)

    src._on_press(keyboard.Key.ctrl_l)
    src._on_press(keyboard.KeyCode.from_char("q"))
    src._on_release(keyboard.Key.ctrl_l)

    assert list(q.queue) == []


def test_click_classified_as_plain_click() -> None:
    q: queue.Queue = queue.Queue()
    src = MouseHookSource(q)

    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)

    events = list(q.queue)
    assert [e.action for e in events] == ["click"]


def test_two_rapid_clicks_at_same_spot_classified_as_double_click() -> None:
    q: queue.Queue = queue.Queue()
    src = MouseHookSource(q)

    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)
    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)

    events = list(q.queue)
    assert [e.action for e in events] == ["click", "double_click"]


def test_two_slow_clicks_at_same_spot_stay_two_plain_clicks() -> None:

    q: queue.Queue = queue.Queue()
    src = MouseHookSource(q)
    # Force the internal "last click" state far enough in the past that
    # the double-click time window has definitely elapsed, without an
    # actual real-time sleep in the test.
    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)
    src._last_left_click = (
        src._last_left_click[0] - (src._double_click_ms / 1000.0) - 1.0,
        100,
        100,
    )
    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)

    events = list(q.queue)
    assert [e.action for e in events] == ["click", "click"]


def test_click_far_away_is_not_a_double_click() -> None:
    q: queue.Queue = queue.Queue()
    src = MouseHookSource(q)

    src._on_click(100, 100, mouse.Button.left, True)
    src._on_click(100, 100, mouse.Button.left, False)
    src._on_click(900, 900, mouse.Button.left, True)
    src._on_click(900, 900, mouse.Button.left, False)

    events = list(q.queue)
    assert [e.action for e in events] == ["click", "click"]


def test_right_click_is_context_click() -> None:
    q: queue.Queue = queue.Queue()
    src = MouseHookSource(q)

    src._on_click(100, 100, mouse.Button.right, True)
    src._on_click(100, 100, mouse.Button.right, False)

    events = list(q.queue)
    assert [e.action for e in events] == ["context_click"]
