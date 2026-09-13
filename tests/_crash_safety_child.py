"""Helper process for test_store.py::test_crash_safety_kill_mid_write.

Two-phase design, deliberately deterministic rather than relying on
probabilistic chunk-boundary timing:

  1. Write and COMMIT a known baseline of `baseline_n` events.
  2. Report BASELINE_DONE, then immediately start ONE single transaction
     (one `append_batch()` call -> one `executemany` inside one commit)
     inserting the remaining `extra_n` events.

The parent kills this process as soon as it sees BASELINE_DONE, i.e. while
step 2's single large transaction is very likely still in flight. Because
SQLite transactions are atomic, the only two admissible outcomes after an
unclean kill are: (a) the whole extra_n transaction is absent (rolled back
by WAL recovery on next open), or (b) it fully landed before the kill took
effect. A torn/partial version of it is what this test exists to rule out.

Never calls writer.stop()/store.close() -- the whole point is to be killed
uncleanly.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pulse_capture.schema import EVENT_TYPES, new_event  # noqa: E402
from pulse_capture.store import SQLiteEventStore  # noqa: E402


def _events(start: int, count: int, session_id: str, actor_id: str) -> list[dict]:
    type_cycle = itertools.cycle(sorted(EVENT_TYPES))
    return [
        new_event(
            producer="desktop",
            event_type=next(type_cycle),
            session_id=session_id,
            actor_id=actor_id,
            t_mono_ns=1_000_000_000 + i * 1000,
        )
        for i in range(start, start + count)
    ]


def main() -> None:
    db_path = Path(sys.argv[1])
    progress_path = Path(sys.argv[2])
    baseline_n = int(sys.argv[3])
    extra_n = int(sys.argv[4])

    session_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    actor_id = "crash-test-actor"

    store = SQLiteEventStore(db_path)

    # Phase 1: baseline, committed in modest sub-batches (fast; not the
    # thing under test).
    for start in range(0, baseline_n, 1000):
        n = min(1000, baseline_n - start)
        rejected = store.append_batch(_events(start, n, session_id, actor_id))
        assert rejected == []

    progress_path.write_text(f"BASELINE_DONE {baseline_n}\n", encoding="utf-8")
    print(f"BASELINE_DONE {baseline_n}", flush=True)

    # Phase 2: the transaction under test -- ONE append_batch() call, so
    # exactly one `executemany` inside exactly one commit for all of
    # extra_n rows. If the parent's kill lands anywhere inside this call,
    # WAL recovery must show either none of these rows or all of them --
    # never a partial subset.
    extra = _events(baseline_n, extra_n, session_id, actor_id)
    rejected = store.append_batch(extra)
    assert rejected == []

    progress_path.write_text(f"BASELINE_DONE {baseline_n}\nEXTRA_DONE {extra_n}\n", encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
