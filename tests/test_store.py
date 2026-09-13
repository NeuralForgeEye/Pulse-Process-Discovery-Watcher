"""Phase 1.1 validation checkpoints, as real pytest tests with real numbers.

Each test prints (via -s / captured output) the actual measured value next
to the blueprint's threshold, and asserts against that threshold — not
"it ran without an exception".
"""

from __future__ import annotations

import copy
import itertools
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pulse_capture.schema import EVENT_TYPES, EventValidationError, new_event
from pulse_capture.store import SQLiteEventStore

# ---------------------------------------------------------------------------
# Checkpoint 1: round-trip
# ---------------------------------------------------------------------------

_VALUE_BEARING_TYPES = {
    "field_value_changed",
    "text_selected",
    "clipboard_copy",
    "clipboard_paste",
}


def _make_synthetic_event(i: int, event_type: str, session_id: str, actor_id: str) -> dict:
    t_mono = 1_000_000_000 + i * 1_000  # deterministic, strictly increasing
    kwargs: dict = dict(
        producer="desktop" if i % 3 else ("browser" if i % 2 else "clipboard"),
        event_type=event_type,
        session_id=session_id,
        actor_id=actor_id,
        t_mono_ns=t_mono,
        t_wall_utc=1_700_000_000_000_000 + i,
        app={"process_name": f"app{i % 7}.exe", "pid": 1000 + i, "exe_path_hash": "h" * 8, "app_class": "native"},
        window={"hwnd_or_tab_id": str(i), "title": f"Window {i}", "url": None, "window_class": "Win32"},
    )
    if event_type in _VALUE_BEARING_TYPES:
        if i % 2 == 0:
            kwargs["content"] = {
                "value_hmac": f"hmac{i:08x}",
                "class": "sensitive_identifier",
                "redaction_state": "hashed_at_capture",
            }
            kwargs["capture_meta"] = {"latency_ms": 1.5, "hmac_key_generation": 1}
        else:
            kwargs["content"] = {
                "value_readable": f"Approve #{i}",
                "class": "ui_chrome",
                "redaction_state": "none",
            }
        kwargs["sensor"] = {
            "tier": "t1_uia",
            "confidence": 1.0,
            "agreement": "single_sensor",
        }
    return new_event(**kwargs)


def test_roundtrip_10000_events(store: SQLiteEventStore, session_id: str, actor_id: str) -> None:
    n = 10_000
    type_cycle = itertools.cycle(sorted(EVENT_TYPES))
    events = [
        _make_synthetic_event(i, next(type_cycle), session_id, actor_id) for i in range(n)
    ]
    seen_types = {e["event_type"] for e in events}
    assert seen_types == set(EVENT_TYPES), "fixture must cover every event_type at least once"

    chunk = 500
    for start in range(0, n, chunk):
        rejected = store.append_batch(events[start : start + chunk])
        assert rejected == [], f"unexpected rejection(s) in synthetic fixture: {rejected}"

    read_back = store.read_range(0, 2**62)

    print(f"\n[roundtrip] wrote={n} read_back={len(read_back)}")
    assert len(read_back) == n, f"round-trip count: {len(read_back)}/{n}"

    mono_values = [e["t_mono_ns"] for e in read_back]
    assert mono_values == sorted(mono_values), "read_range did not return events ordered by t_mono_ns"

    mismatches = 0
    for original, roundtripped in zip(events, read_back, strict=True):
        if original != roundtripped:
            mismatches += 1
    print(f"[roundtrip] byte-identical matches: {n - mismatches}/{n}")
    assert mismatches == 0, f"{mismatches} of {n} events were not byte-identical after round-trip"


# ---------------------------------------------------------------------------
# Checkpoint 2: schema enforcement
# ---------------------------------------------------------------------------


def _valid_baseline(session_id: str, actor_id: str) -> dict:
    return new_event(
        producer="desktop",
        event_type="field_value_changed",
        session_id=session_id,
        actor_id=actor_id,
        content={"value_hmac": "abc123", "class": "sensitive_identifier"},
        sensor={"tier": "t1_uia", "confidence": 1.0, "agreement": "single_sensor"},
        capture_meta={"hmac_key_generation": 1},
    )


def _malformed_cases(session_id: str, actor_id: str) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []

    for field in [
        "event_id",
        "schema_version",
        "producer",
        "t_wall_utc",
        "t_mono_ns",
        "session_id",
        "actor_id",
        "event_type",
    ]:
        e = _valid_baseline(session_id, actor_id)
        del e[field]
        cases.append((f"missing required field: {field}", e))

    e = _valid_baseline(session_id, actor_id)
    e["event_type"] = "not_a_real_event_type"
    cases.append(("unknown event_type enum value", e))

    e = _valid_baseline(session_id, actor_id)
    e["producer"] = "not_a_real_producer"
    cases.append(("unknown producer enum value", e))

    e = _valid_baseline(session_id, actor_id)
    e["sensor"]["tier"] = "t4_telepathy"
    cases.append(("unknown sensor.tier enum value", e))

    e = _valid_baseline(session_id, actor_id)
    e["t_mono_ns"] = "123"  # wrong type: string instead of integer
    cases.append(("wrong type: t_mono_ns as string", e))

    e = _valid_baseline(session_id, actor_id)
    e["schema_version"] = "1"  # wrong type: string instead of integer
    cases.append(("wrong type: schema_version as string", e))

    e = _valid_baseline(session_id, actor_id)
    e["actor_id"] = 12345  # wrong type: integer instead of string
    cases.append(("wrong type: actor_id as integer", e))

    e = _valid_baseline(session_id, actor_id)
    e["schema_version"] = 999  # future/unsupported version
    cases.append(("future schema_version (999)", e))

    e = _valid_baseline(session_id, actor_id)
    e["schema_version"] = 0  # below JSON Schema minimum AND unsupported by store
    cases.append(("schema_version below minimum (0)", e))

    e = _valid_baseline(session_id, actor_id)
    e["content"] = {"class": "sensitive_identifier", "value_readable": "LN-48213"}  # no value_hmac, has value_readable
    cases.append(("sensitive_identifier with value_readable and no value_hmac", e))

    e = _valid_baseline(session_id, actor_id)
    del e["sensor"]  # content present, sensor missing
    cases.append(("content present but sensor missing", e))

    e = _valid_baseline(session_id, actor_id)
    del e["capture_meta"]  # value_hmac present, hmac_key_generation missing
    cases.append(("value_hmac present but capture_meta/hmac_key_generation missing", e))

    e = _valid_baseline(session_id, actor_id)
    e["not_a_real_field"] = "should be rejected by additionalProperties: false"
    cases.append(("unknown top-level property (additionalProperties)", e))

    return cases


def test_schema_enforcement_20_malformed_events(
    store: SQLiteEventStore, session_id: str, actor_id: str
) -> None:
    cases = _malformed_cases(session_id, actor_id)
    assert len(cases) == 20, f"expected exactly 20 malformed cases, built {len(cases)}"

    rejected = 0
    for description, bad_event in cases:
        with pytest.raises(EventValidationError) as excinfo:
            store.append(copy.deepcopy(bad_event))
        assert excinfo.value.errors, f"no specific error attached for case: {description}"
        rejected += 1
        print(f"[schema-enforcement] REJECTED ({description}): {excinfo.value.errors[0]}")

    print(f"[schema-enforcement] {rejected}/{len(cases)} malformed events correctly rejected")
    assert rejected == 20

    written = store.row_count()
    print(f"[schema-enforcement] rows written despite rejection: {written}")
    assert written == 0, "zero rows must be written when every fed event is malformed"


# ---------------------------------------------------------------------------
# Checkpoint 3: crash safety (subprocess kill mid-write)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_crash_safety_kill_mid_write(tmp_path: Path) -> None:
    """Deterministic design (see _crash_safety_child.py docstring): a
    committed baseline, then ONE large in-flight transaction that the
    parent kills as soon as the baseline is confirmed. SQLite transactions
    are atomic, so after reopening the only admissible row counts are
    `baseline_n` (the in-flight transaction was fully rolled back) or
    `baseline_n + extra_n` (it fully committed before the kill landed) --
    anything in between would mean a torn/partial transaction survived.

    Run REPEATS times rather than once, since a single run's kill timing
    is not fully controllable -- repeating builds real confidence that the
    guarantee holds rather than reporting one possibly-lucky sample.
    """
    baseline_n = 10_000
    extra_n = 40_000
    repeats = 5
    child_script = Path(__file__).parent / "_crash_safety_child.py"

    outcomes: list[str] = []

    for run in range(repeats):
        db_path = tmp_path / f"crash_test_{run}.db"
        progress_path = tmp_path / f"progress_{run}.txt"
        log_path = tmp_path / f"child_stdout_{run}.log"

        with log_path.open("w") as log_file:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(child_script),
                    str(db_path),
                    str(progress_path),
                    str(baseline_n),
                    str(extra_n),
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 30
                triggered = False
                while time.monotonic() < deadline:
                    if progress_path.exists():
                        text = progress_path.read_text(encoding="utf-8")
                        if text.startswith("BASELINE_DONE"):
                            triggered = True
                            break
                assert triggered, f"[run {run}] child never confirmed baseline within 30s"

                # Kill AS SOON AS POSSIBLE after the baseline is confirmed,
                # while phase 2's single large transaction is most likely
                # still executing. TerminateProcess on Windows is immediate
                # -- no cleanup handlers run -- the direct equivalent of
                # `kill -9` on POSIX.
                proc.terminate()
                proc.wait(timeout=10)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)

        reopened = SQLiteEventStore(db_path)
        try:
            integrity = reopened.integrity_check()
            assert integrity.lower() == "ok", f"[run {run}] database corrupt after kill: {integrity}"

            row_count = reopened.row_count()
            if row_count == baseline_n:
                outcome = "rolled_back (0 of the in-flight transaction survived)"
            elif row_count == baseline_n + extra_n:
                outcome = "fully_committed (transaction finished before kill landed)"
            else:
                outcome = f"TORN ({row_count} rows -- neither baseline nor baseline+extra)"
            outcomes.append(outcome)
            print(f"[crash-safety] run {run}: integrity={integrity}, row_count={row_count} -> {outcome}")

            assert row_count in (baseline_n, baseline_n + extra_n), (
                f"[run {run}] row_count={row_count} is neither the pre-transaction baseline "
                f"({baseline_n}) nor the fully-committed total ({baseline_n + extra_n}) -- "
                "a torn/partial transaction survived the kill"
            )
        finally:
            reopened.close()

    torn = [o for o in outcomes if o.startswith("TORN")]
    rolled_back = [o for o in outcomes if o.startswith("rolled_back")]
    print(
        f"\n[crash-safety] {repeats} runs: "
        f"{len(rolled_back)} rolled back the in-flight transaction cleanly, "
        f"{len(outcomes) - len(rolled_back) - len(torn)} committed it fully before the kill landed, "
        f"{len(torn)} torn (must be 0)"
    )
    assert not torn, f"torn/partial transaction(s) survived a kill: {torn}"
    assert len(rolled_back) >= 1, (
        "every single run committed before the kill landed -- the kill is not "
        "actually racing the transaction; timing needs adjusting to be a real test"
    )


# ---------------------------------------------------------------------------
# Checkpoint 4: throughput headroom
# ---------------------------------------------------------------------------


def test_throughput_at_least_2000_events_per_second(
    store: SQLiteEventStore, session_id: str, actor_id: str
) -> None:
    n = 20_000
    chunk = 500
    type_cycle = itertools.cycle(sorted(EVENT_TYPES))
    events = [_make_synthetic_event(i, next(type_cycle), session_id, actor_id) for i in range(n)]

    start = time.perf_counter()
    for i in range(0, n, chunk):
        rejected = store.append_batch(events[i : i + chunk])
        assert rejected == []
    elapsed = time.perf_counter() - start

    rate = n / elapsed
    print(f"\n[throughput] wrote {n} events in {elapsed:.3f}s = {rate:.1f} events/s (target >= 2000/s)")
    assert rate >= 2000, f"throughput {rate:.1f} events/s is below the 2000/s threshold"
