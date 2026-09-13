"""Pulse capture host entry point.

OPERATIONAL REQUIREMENTS (stated here in the source, not just chat history):

  * Manually-started foreground script ONLY. One command starts it; Ctrl+C
    (SIGINT) stops it cleanly, flushing every pending write to the SQLite
    store before exiting -- never a bare kill that risks a corrupt/lossy
    write on a clean stop.
  * This module does NOT, and must never, register itself as a Windows
    service, a Scheduled Task, a Run/RunOnce startup entry, or anything
    else that causes it to start without the user explicitly invoking it.
    There is no code path here that touches the Service Control Manager,
    Task Scheduler, or the registry's startup keys. If that is ever
    needed, it is a deliberate, separate, explicitly-requested change --
    not something to add quietly while touching this file.
  * While running, prints a visible, continuously-updating status line so
    it is never silently active in the background unnoticed.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from pulse_capture.desktop.dpi import ensure_process_dpi_aware
from pulse_capture.desktop.host import CaptureHost
from pulse_capture.store import SQLiteEventStore

# Must happen before any window/UIA/input call anywhere in the process --
# see dpi.py for the real, tested bug this prevents (Phase 1.3's element
# resolution silently landing on the wrong element on any DPI-scaled
# display, which is most real Windows machines).
ensure_process_dpi_aware()

_BANNER = "Pulse capture running - press Ctrl+C to stop"


def _format_status(counts: dict[str, int]) -> str:
    uptime = counts.get("uptime_s", 0)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    return (
        f"\r{_BANNER} | uptime {h:02d}:{m:02d}:{s:02d} | "
        f"raw={counts.get('raw_events_seen', 0)} "
        f"written={counts.get('written', 0)} "
        f"queued={counts.get('queued', 0)} "
        f"dropped={counts.get('dropped', 0)} "
        f"rejected={counts.get('rejected', 0)}   "
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pulse-capture-host",
        description=(
            "Pulse Stage 1 desktop capture host (Phase 1.1 + 1.2). "
            "Foreground only; press Ctrl+C to stop. Never installs itself "
            "as a service, scheduled task, or startup entry."
        ),
    )
    parser.add_argument("--db", type=Path, default=Path("pulse.db"), help="Path to the SQLite event store.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(".pulse_state"),
        help="Local directory for the actor-id salt file (see host.py's docstring on actor_id).",
    )
    parser.add_argument(
        "--idle-threshold-s",
        type=float,
        default=60.0,
        help="Seconds of no input before an idle_start event is emitted.",
    )
    args = parser.parse_args(argv)

    store = SQLiteEventStore(args.db)
    host = CaptureHost(store, state_dir=args.state_dir, idle_threshold_s=args.idle_threshold_s)

    print(_BANNER)
    print(f"  db path:      {args.db.resolve()}")
    print(f"  session_id:   {host.session_id}")
    print(f"  actor_id:     {host.actor_id}")
    print(f"  idle after:   {args.idle_threshold_s:.0f}s")
    print()

    host.start()

    stop_requested = {"flag": False}

    def _handle_stop_signal(_signum: int, _frame: object) -> None:
        stop_requested["flag"] = True

    # SIGINT: a real, interactive Ctrl+C at the console -- the primary,
    # required operational path.
    signal.signal(signal.SIGINT, _handle_stop_signal)
    # SIGBREAK (Windows-only, raised from CTRL_BREAK_EVENT): Windows does
    # not deliver CTRL_C_EVENT to a process running in its own process
    # group (a documented OS restriction, not a Pulse design choice) --
    # which is exactly how a supervising process/scheduler would need to
    # launch this to signal it without also signaling itself. Handling
    # SIGBREAK too means this host can be stopped cleanly either way,
    # through the exact same flush-on-shutdown path.
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handle_stop_signal)

    try:
        while not stop_requested["flag"]:
            sys.stdout.write(_format_status(host.snapshot()))
            sys.stdout.flush()
            time.sleep(0.5)
    finally:
        sys.stdout.write("\n\nShutting down - flushing pending events...\n")
        sys.stdout.flush()
        final = host.stop(timeout=30.0)
        store.close()
        print(
            "Stopped cleanly.\n"
            f"  raw events seen:  {final.get('raw_events_seen', 0)}\n"
            f"  events written:   {final.get('written', 0)}\n"
            f"  events dropped:   {final.get('dropped', 0)}\n"
            f"  events rejected:  {final.get('rejected', 0)}\n"
            f"  db path:          {args.db.resolve()}\n"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
