"""Read-only viewer: render pulse.db as a human-readable timeline.

This is a debugging/demo aid only -- it adds no new capture logic and is
not part of any blueprint phase. It exists because the raw `events` table
is not meant to be read directly (see store.py's docstring): this script
is the plain-English window onto data that's already there.

Usage:
    uv run python view_events.py [--db pulse.db] [--last N] [--type window_opened,click]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from pulse_capture.store import SQLiteEventStore

_COLLAPSE_TYPES = {"focus_changed"}  # noisy, low-signal for a first read


def _local_time(t_wall_utc_us: int) -> str:
    return datetime.fromtimestamp(t_wall_utc_us / 1e6, tz=UTC).astimezone().strftime("%H:%M:%S.%f")[:-3]


def _content_preview(event: dict, max_chars: int = 70) -> str:
    content = event.get("content") or {}
    if content.get("redaction_state") == "password_field":
        return "(password -- never captured)"
    text = content.get("value_readable")
    if not text:
        return "(empty)"
    text = " ".join(text.split())  # collapse newlines/whitespace for one-line display
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return f'"{text}"'


def _describe(event: dict) -> str:
    app = event.get("app") or {}
    window = event.get("window") or {}
    process = app.get("process_name") or "(unknown app)"
    title = (window.get("title") or "").strip()
    if len(title) > 60:
        title = title[:57] + "..."
    event_type = event["event_type"]

    if event_type == "app_launched":
        return f"{process} started"
    if event_type == "app_exited":
        return f"{process} closed"
    if event_type in ("window_opened", "window_closed", "window_activated", "focus_changed"):
        return f"{process} -- {title or '(no title)'}  [{event_type}]"
    if event_type in ("click", "double_click", "context_click"):
        return f"{process} -- {title or '(no title)'}  [{event_type}]"
    if event_type == "key_shortcut":
        return f"{process} -- {title or '(no title)'}  [shortcut]"
    if event_type == "text_selected":
        element = event.get("element") or {}
        source = (event.get("sensor") or {}).get("fallback_reason") or "observed"
        return f"{process} -- {title or '(no title)'}  [text_selected, {source}] {_content_preview(event)} (field: {element.get('automation_id') or element.get('name') or '?'})"
    if event_type == "field_value_changed":
        element = event.get("element") or {}
        return f"{process} -- {title or '(no title)'}  [field_value_changed] {_content_preview(event)} (field: {element.get('automation_id') or element.get('name') or '?'})"
    if event_type == "capture_degraded":
        meta = event.get("capture_meta") or {}
        return f"[capture_degraded: {meta.get('degraded_reason') or 'unknown reason'}]"
    if event_type in ("idle_start", "idle_end"):
        return f"[{event_type}]"
    return f"{process} -- {title}  [{event_type}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("pulse.db"))
    parser.add_argument("--last", type=int, default=200, help="Show only the most recent N events (default 200).")
    parser.add_argument("--type", type=str, default=None, help="Comma-separated event_type filter, e.g. click,window_opened")
    parser.add_argument("--all", action="store_true", help="Include noisy event types (focus_changed) normally collapsed.")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"No database at {args.db.resolve()}")
        return 1

    store = SQLiteEventStore(args.db)
    try:
        events = store.read_range(0, 2**63 - 1)
    finally:
        store.close()

    # store.read_range orders by t_mono_ns, which the schema is explicit is
    # only valid for ordering WITHIN one session_id (a monotonic clock
    # resets across separate capture-host runs). This file accumulates
    # events across many runs over days, so re-sort by t_wall_utc -- the
    # field the schema designates "for human reading... across sessions" --
    # or old and new sessions interleave in an arbitrary order. Found by
    # testing: without this, --last N could surface a much older session's
    # events ahead of ones from five minutes ago.
    events.sort(key=lambda e: e["t_wall_utc"])

    type_filter = set(args.type.split(",")) if args.type else None

    rows = []
    for e in events:
        if type_filter is not None and e["event_type"] not in type_filter:
            continue
        if type_filter is None and not args.all and e["event_type"] in _COLLAPSE_TYPES:
            continue
        rows.append(e)

    rows = rows[-args.last :]

    print(f"{len(events)} total events in {args.db.resolve()}; showing {len(rows)}\n")
    print(f"{'time':<13}  {'session':<8}  description")
    print("-" * 100)
    for e in rows:
        session_short = e["session_id"][:8]
        print(f"{_local_time(e['t_wall_utc']):<13}  {session_short:<8}  {_describe(e)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
