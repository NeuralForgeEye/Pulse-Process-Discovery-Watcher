"""Local capture-health report: how reliably has Pulse been capturing on
THIS machine, and when/why did it degrade.

This is the single-machine building block for Stage 7 Phase 7.2
(capture-health monitoring) -- see plans/BUILD-STATUS.md and
plans/stage-7-blueprint.md. It reads one local pulse.db and reports on it;
it does NOT send anything anywhere, and it is not the fleet-wide,
across-many-machines dashboard the full Phase 7.2 design calls for -- that
needs a central collection point, which does not exist yet and is a data-
governance decision, not a technical one to make unilaterally (see
CLAUDE.md's "Data controls" section, point 4).

What "degraded" means here, precisely (see uia_client.py /
uia_events.py's SnapshotResult):
  - "clean"    -- the acting element resolved AND the full context walk
                  finished inside its budget. No caveats.
  - "degraded" -- the acting element resolved, but the neighbourhood walk
                  (Phase 1.3 build step 4) hit its wall-clock budget before
                  finishing -- some nearby field values may be missing from
                  `context`, but the click itself is correctly attributed.
  - "dropped"  -- no element resolved at all for this action. The event is
                  still captured (app/window attribution, timing), just
                  without element/context detail.

Usage:
    uv run python capture_health.py [--db pulse.db] [--session <id-prefix>]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

# Event types that go through Phase 1.3's element/context resolution and so
# can carry a meaningful degraded_reason -- window/focus/app-lifecycle
# events never attempt a snapshot at all, so including them would understate
# the real degradation rate by diluting it with events that were never at risk.
_SNAPSHOT_ELIGIBLE_TYPES = {"click", "double_click", "context_click", "key_shortcut"}


def _local_time(t_wall_utc_us: int) -> str:
    return datetime.fromtimestamp(t_wall_utc_us / 1e6, tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    idx = max(0, min(len(sorted_values) - 1, int(len(sorted_values) * pct) - 1))
    return sorted_values[idx]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path("pulse.db"))
    parser.add_argument("--session", type=str, default=None, help="Only report on sessions whose id starts with this prefix.")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"No database at {args.db.resolve()}")
        return 1

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT session_id, event_type, t_wall_utc, element_json, capture_meta_json FROM events ORDER BY t_wall_utc ASC"
    ).fetchall()
    conn.close()

    if args.session:
        rows = [r for r in rows if r["session_id"].startswith(args.session)]

    eligible = [r for r in rows if r["event_type"] in _SNAPSHOT_ELIGIBLE_TYPES]
    if not eligible:
        print(f"No snapshot-eligible events (click/double_click/context_click/key_shortcut) found in {args.db.resolve()}.")
        print("Nothing to report on yet -- run the capture host and do some clicking first.")
        return 0

    clean = 0
    degraded_context = 0
    dropped = 0
    latencies: list[float] = []
    reason_counts: Counter[str] = Counter()
    by_session: dict[str, dict[str, int]] = defaultdict(lambda: {"clean": 0, "degraded": 0, "dropped": 0})
    first_ts = eligible[0]["t_wall_utc"]
    last_ts = eligible[-1]["t_wall_utc"]

    for r in eligible:
        session_short = r["session_id"][:8]
        has_element = bool(r["element_json"])
        meta = json.loads(r["capture_meta_json"]) if r["capture_meta_json"] else {}
        latency = meta.get("latency_ms")
        reason = meta.get("degraded_reason")
        if latency is not None:
            latencies.append(latency)

        if not has_element:
            dropped += 1
            by_session[session_short]["dropped"] += 1
            reason_counts[reason or "no_element_unspecified"] += 1
        elif reason:
            degraded_context += 1
            by_session[session_short]["degraded"] += 1
            reason_counts[reason] += 1
        else:
            clean += 1
            by_session[session_short]["clean"] += 1

    total = len(eligible)
    latencies.sort()

    print(f"Pulse capture-health report -- {args.db.resolve()}")
    print(f"Covering {_local_time(first_ts)} to {_local_time(last_ts)}")
    print(f"({len(rows)} total events in the file; {total} were snapshot-eligible click/shortcut actions)\n")

    print(f"{'':14}{'count':>8}{'%':>8}")
    print(f"{'clean':14}{clean:>8}{100 * clean / total:>7.1f}%")
    print(f"{'degraded':14}{degraded_context:>8}{100 * degraded_context / total:>7.1f}%   (element resolved OK, but nearby field context was incomplete)")
    print(f"{'dropped':14}{dropped:>8}{100 * dropped / total:>7.1f}%   (no element resolved at all for this action)")
    print()

    if latencies:
        p50 = _percentile(latencies, 0.50)
        p95 = _percentile(latencies, 0.95)
        print(f"Latency (end-to-end, click to resolved snapshot): p50={p50:.0f}ms  p95={p95:.0f}ms  max={max(latencies):.0f}ms  (n={len(latencies)})")
        print()

    if reason_counts:
        print("Degradation reasons:")
        for reason, count in reason_counts.most_common():
            print(f"  {reason:<28} {count}")
        print()

    print("By session (first 8 chars of session_id):")
    print(f"{'session':10}{'clean':>8}{'degraded':>10}{'dropped':>9}{'rate':>8}")
    for session_short, counts in sorted(by_session.items(), key=lambda kv: -sum(kv[1].values())):
        s_total = sum(counts.values())
        bad_rate = 100 * (counts["degraded"] + counts["dropped"]) / s_total if s_total else 0.0
        flag = "  <-- elevated" if bad_rate > 10 else ""
        print(f"{session_short:10}{counts['clean']:>8}{counts['degraded']:>10}{counts['dropped']:>9}{bad_rate:>7.1f}%{flag}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
