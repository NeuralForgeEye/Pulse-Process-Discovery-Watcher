"""Window and focus events via SetWinEventHook (Phase 1.2 build step 2).

WINEVENT_OUTOFCONTEXT, idProcess = idThread = 0 (desktop-wide) -- no DLL
injection into target processes (an in-context hook would need that, which
is "a deployment and security nightmare and an instant red flag in any
enterprise security review", per the blueprint). The cost is asynchronous
delivery, which is fine: ordering is a Phase 1.7 concern, not this one.

Out-of-context WinEvent notifications are delivered via the *registering
thread's message queue* -- the OS does not just invoke the callback out of
thin air, the thread must be pumping messages (GetMessage/DispatchMessage)
for delivery to happen at all. So this runs its own dedicated thread with
a real Win32 message loop, stopped cleanly via PostThreadMessage(WM_QUIT).

Two hook registrations cover the five events of interest, because they
aren't numerically contiguous:
  - EVENT_SYSTEM_FOREGROUND (0x0003) .. EVENT_SYSTEM_MINIMIZEEND (0x0017)
  - EVENT_OBJECT_DESTROY   (0x8001) .. EVENT_OBJECT_FOCUS      (0x8005)
Each range also covers a couple of events we don't want (e.g.
EVENT_OBJECT_HIDE, EVENT_OBJECT_REORDER sit inside the second range) --
filtered out explicitly in the callback rather than by narrowing the
range, which is standard practice for this API.

The callback itself does the absolute minimum: read the (cheap) hwnd/
event id, timestamp, and put a raw tuple on a queue. All resolution
(PID -> process name -> exe path, window title) happens on a separate
consumer thread, per "resolve application identity off the hot path".
"""

from __future__ import annotations

import contextlib
import ctypes
import queue
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Explicit argtypes/restype for every Win32 call used below. Without these,
# ctypes defaults to a 32-bit `int` return type -- which silently TRUNCATES
# HWINEVENTHOOK (a pointer-sized, 64-bit handle on x64 Windows). A truncated
# handle can still look "non-null" and appear to work right up until
# UnhookWinEvent() is called with the wrong value at shutdown. This is
# exactly the class of bug that passes a quick manual test and fails later.
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    ctypes.c_void_p,  # WINEVENTPROC -- accepts the WINFUNCTYPE instance directly
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]
user32.UnhookWinEvent.restype = wintypes.BOOL
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.restype = ctypes.c_int  # BOOL, but -1/0/nonzero all matter -- see loop below
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []

WINEVENT_OUTOFCONTEXT = 0x0000
WM_QUIT = 0x0012
PM_REMOVE = 0x0001

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND = 0x0017
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_FOCUS = 0x8005

# Only these event ids are ever turned into raw records, even though the
# two SetWinEventHook ranges above are wider than this set.
_WANTED_EVENTS = frozenset(
    {
        EVENT_SYSTEM_FOREGROUND,
        EVENT_SYSTEM_MINIMIZESTART,
        EVENT_SYSTEM_MINIMIZEEND,
        EVENT_OBJECT_DESTROY,
        EVENT_OBJECT_SHOW,
        EVENT_OBJECT_FOCUS,
    }
)

# For EVENT_OBJECT_SHOW/DESTROY, idObject == OBJID_WINDOW (0) means "an
# actual top-level-ish window object", not some arbitrary child control.
# Filtering to this avoids being chatty for every button/control show or
# destroy inside a window -- Phase 1.2 has no element resolution yet, so a
# non-window idObject isn't attributable to anything more specific anyway.
OBJID_WINDOW = 0

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,  # hWinEventHook
    wintypes.DWORD,  # event
    wintypes.HWND,  # hwnd
    wintypes.LONG,  # idObject
    wintypes.LONG,  # idChild
    wintypes.DWORD,  # idEventThread
    wintypes.DWORD,  # dwmsEventTime
)


@dataclass(frozen=True, slots=True)
class RawWindowEvent:
    event_id: int
    hwnd: int
    id_object: int
    t_mono_ns: int
    t_wall_utc_us: int


class WindowEventSource:
    """Owns the SetWinEventHook registrations + message pump thread.

    Raw events land on `raw_queue` (a plain queue.Queue the caller
    supplies, shared with other raw-event producers e.g. input hooks, so a
    single resolver thread can drain everything in submission order).
    """

    def __init__(self, raw_queue: queue.Queue[Any]) -> None:
        # See input_hooks.MouseHookSource.__init__ for why this is
        # loosely typed: this queue is shared across raw-event sources in
        # the real orchestrator (host.py), and queue.Queue is invariant.
        self._raw_queue = raw_queue
        self._thread: threading.Thread | None = None
        self._win_thread_id: int | None = None
        self._ready = threading.Event()
        self._hook_handles: list[int] = []
        # Must keep a live reference to the ctypes callback, or it gets
        # garbage-collected out from under the OS the moment this function
        # returns -- a classic, silent ctypes footgun.
        self._callback = WinEventProcType(self._on_event)

    def start(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            raise RuntimeError("WindowEventSource already started")
        self._thread = threading.Thread(target=self._run, name="pulse-window-events", daemon=False)
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            raise TimeoutError("WindowEventSource hook thread did not start in time")

    def stop(self, timeout: float = 5.0) -> None:
        if self._thread is None or self._win_thread_id is None:
            return
        user32.PostThreadMessageW(self._win_thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        self._win_thread_id = kernel32.GetCurrentThreadId()

        h1 = user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_MINIMIZEEND,
            0,
            self._callback,
            0,
            0,
            WINEVENT_OUTOFCONTEXT,
        )
        h2 = user32.SetWinEventHook(
            EVENT_OBJECT_DESTROY,
            EVENT_OBJECT_FOCUS,
            0,
            self._callback,
            0,
            0,
            WINEVENT_OUTOFCONTEXT,
        )
        if not h1 or not h2:
            self._ready.set()  # unblock start() so it can raise below
            raise OSError("SetWinEventHook registration failed")
        self._hook_handles = [h1, h2]

        self._ready.set()

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            if ret == -1:
                break  # error; don't spin forever
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        for h in self._hook_handles:
            user32.UnhookWinEvent(h)

    def _on_event(
        self,
        _hwineventhook: int,
        event: int,
        hwnd: int,
        id_object: int,
        _id_child: int,
        _id_event_thread: int,
        _dwms_event_time: int,
    ) -> None:
        # Hot path: timestamp + enqueue, nothing else. Microsoft's own docs
        # warn these callbacks can re-enter before a previous invocation
        # finishes -- no shared mutable state touched here beyond the
        # thread-safe queue.
        if event not in _WANTED_EVENTS:
            return
        if event in (EVENT_OBJECT_SHOW, EVENT_OBJECT_DESTROY) and id_object != OBJID_WINDOW:
            return
        t_mono_ns = time.monotonic_ns()
        t_wall_utc_us = time.time_ns() // 1_000
        # the resolver-side queue enforces its own backpressure/counting
        with contextlib.suppress(queue.Full):
            self._raw_queue.put_nowait(
                RawWindowEvent(
                    event_id=event,
                    hwnd=hwnd,
                    id_object=id_object,
                    t_mono_ns=t_mono_ns,
                    t_wall_utc_us=t_wall_utc_us,
                )
            )
