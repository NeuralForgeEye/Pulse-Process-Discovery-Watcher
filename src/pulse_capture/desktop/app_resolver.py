"""Resolve a window handle to application identity, off the hot path.

Per Phase 1.2 build step 3: "Resolve application identity off the hot
path. From the hwnd, get the PID, then process name and executable path.
Cache by PID... because these calls are not free and the same process
recurs thousands of times."

`resolve()` is deliberately NOT called from any hook callback directly --
callers capture the hwnd on the hot path (cheap: GetForegroundWindow()
is a simple non-marshaling read) and hand it to a resolver thread, which
calls this.
"""

from __future__ import annotations

import hashlib
import threading

import psutil
import win32gui
import win32process

# Minimal, provisional app_class heuristic -- Stage 1 doesn't define
# classification rules yet; this is just enough to be useful now without
# pretending it's a considered taxonomy.
_BROWSER_PROCESS_NAMES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
}


class AppInfo:
    __slots__ = ("process_name", "pid", "exe_path_hash", "app_class")

    def __init__(self, process_name: str | None, pid: int | None, exe_path_hash: str | None, app_class: str | None) -> None:
        self.process_name = process_name
        self.pid = pid
        self.exe_path_hash = exe_path_hash
        self.app_class = app_class

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "process_name": self.process_name,
            "pid": self.pid,
            "exe_path_hash": self.exe_path_hash,
            "app_class": self.app_class,
        }


_UNKNOWN = AppInfo(process_name=None, pid=None, exe_path_hash=None, app_class=None)


class AppResolver:
    """Caches hwnd -> pid -> AppInfo. Not thread-safe for concurrent
    *writers*; intended to be driven by a single resolver thread (Phase
    1.2's design), so no internal locking beyond what dict access already
    guarantees under the GIL for simple get/set.
    """

    def __init__(self) -> None:
        self._by_pid: dict[int, AppInfo] = {}
        self._lock = threading.Lock()

    def resolve_hwnd(self, hwnd: int) -> AppInfo:
        if not hwnd:
            return _UNKNOWN
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return _UNKNOWN
        if not pid:
            return _UNKNOWN
        return self.resolve_pid(pid)

    def resolve_pid(self, pid: int) -> AppInfo:
        with self._lock:
            cached = self._by_pid.get(pid)
        if cached is not None:
            return cached

        info = self._resolve_pid_uncached(pid)
        # Deliberately not cached when unresolvable (pid <= 0, or a
        # transient resolution failure): caching a permanent "unknown"
        # result under a garbage/invalid key would be harmless today but
        # pointless, and would grow the cache with keys that can never be
        # looked up again meaningfully.
        if info.pid is not None:
            with self._lock:
                self._by_pid[pid] = info
        return info

    def _resolve_pid_uncached(self, pid: int) -> AppInfo:
        # Some WinEvent notifications (e.g. focus moving to a non-window
        # system object -- observed in practice with idObject values like
        # OBJID_CARET) can hand back an hwnd that GetWindowThreadProcessId
        # resolves to a garbage/negative "pid". A negative or zero pid is
        # never a real process, so this is checked BEFORE calling psutil
        # (which would otherwise raise ValueError and, prior to this fix,
        # silently killed the entire resolver background thread -- a much
        # more serious problem than the occasional unresolvable event).
        if pid <= 0:
            return AppInfo(process_name=None, pid=None, exe_path_hash=None, app_class=None)
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, OSError):
            return AppInfo(process_name=None, pid=pid, exe_path_hash=None, app_class=None)

        # Plain sha256, NOT the Vault-keyed HMAC used for sensitive content
        # values (Phase 1.8 concern). This hash exists only so we don't
        # store a raw filesystem path that may embed a username -- it is
        # not classified as a sensitive_identifier.
        exe_path_hash = hashlib.sha256(exe_path.encode("utf-8", "replace")).hexdigest()

        app_class = "browser" if process_name.lower() in _BROWSER_PROCESS_NAMES else "native"

        return AppInfo(
            process_name=process_name,
            pid=pid,
            exe_path_hash=exe_path_hash,
            app_class=app_class,
        )

    def invalidate(self, pid: int) -> None:
        with self._lock:
            self._by_pid.pop(pid, None)

    def is_process_alive(self, pid: int) -> bool:
        return psutil.pid_exists(pid)


def window_title(hwnd: int) -> str | None:
    if not hwnd:
        return None
    try:
        return win32gui.GetWindowText(hwnd) or None
    except Exception:
        return None


def window_class_name(hwnd: int) -> str | None:
    if not hwnd:
        return None
    try:
        return win32gui.GetClassName(hwnd) or None
    except Exception:
        return None
