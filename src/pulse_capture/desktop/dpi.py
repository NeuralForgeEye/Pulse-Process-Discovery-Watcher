"""Process DPI awareness -- must be set before ANY window/UIA/input call.

Real bug, found by testing (not theorised): on a DPI-scaled display (125%
scaling, the actual configuration of the machine this was tested on -- and
the default on most modern Windows laptops/monitors), a DPI-UNAWARE process
gets coordinates "virtualized" by Windows for most Win32 APIs (SetCursorPos,
GetWindowRect, WindowFromPoint all report a scaled-down, fake 96-DPI screen),
while UI Automation's `ElementFromPoint` uses REAL physical-monitor
coordinates. The two disagree, and every click resolves to the wrong
element -- confirmed directly: without this fix, clicking a fixture app's
"Reject" button at its own reported coordinates resolved to an unrelated
Chrome element instead; with `SetProcessDpiAwareness` called first, it
resolved correctly, `GetSystemMetrics` reported the real 1920x1080 panel
instead of a virtualized 1536x864, and the window rect scaled accordingly.

Without this fix, Phase 1.3's element resolution would be silently wrong
on essentially any real, DPI-scaled Windows machine -- not a corner case.

Must be called ONCE, as early as possible in the process (before creating
any window, before any UIA call, before any synthetic input) -- Windows
does not allow changing it after the fact, and the safe/expected failure
mode of calling it twice (or after a manifest already declared it) is
"already set", not a crash, so this is idempotent by design.
"""

from __future__ import annotations

import contextlib
import ctypes

_PROCESS_PER_MONITOR_DPI_AWARE = 2

_applied = False


def ensure_process_dpi_aware() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(_PROCESS_PER_MONITOR_DPI_AWARE)
    except Exception:
        # Older Windows without shcore (or a manifest already set awareness,
        # or this process genuinely isn't allowed to change it at this
        # point) -- fall back to the older, coarser API rather than fail.
        with contextlib.suppress(Exception):
            ctypes.windll.user32.SetProcessDPIAware()
