"""Idle detection (Phase 1.2 build step 4).

GetLastInputInfo polled on a timer. Threshold is configurable, not a
hardcoded constant -- Stage 2 is expected to tune it later (see the
platform-wide note in research/stage-2-episode-segmentation.md about the
30-minute web-analytics convention being an arbitrary, poorly-sourced
default that should not be copied uncritically).
"""

from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Callable
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _get_idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    tick_count = kernel32.GetTickCount()
    # Both wrap around ~49.7 days; a wrapped delta stays correct because
    # unsigned 32-bit subtraction wraps too (Python's plain `-` doesn't
    # wrap the way C does, so mask to 32 bits explicitly).
    elapsed_ms = (tick_count - info.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


class IdleDetector:
    """Polls GetLastInputInfo and calls back on idle_start / idle_end
    transitions. Runs on its own thread; does not touch the writer or
    store directly, so it stays testable in isolation.
    """

    def __init__(
        self,
        on_idle_start: Callable[[int, int], None],
        on_idle_end: Callable[[int, int], None],
        *,
        threshold_s: float = 60.0,
        poll_interval_s: float = 1.0,
    ) -> None:
        self._on_idle_start = on_idle_start
        self._on_idle_end = on_idle_end
        self.threshold_s = threshold_s
        self._poll_interval_s = poll_interval_s
        self._is_idle = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="pulse-idle", daemon=False)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.wait(self._poll_interval_s):
            idle_s = _get_idle_seconds()
            now_mono = time.monotonic_ns()
            now_wall = time.time_ns() // 1_000
            if not self._is_idle and idle_s >= self.threshold_s:
                self._is_idle = True
                self._on_idle_start(now_mono, now_wall)
            elif self._is_idle and idle_s < self.threshold_s:
                self._is_idle = False
                self._on_idle_end(now_mono, now_wall)
