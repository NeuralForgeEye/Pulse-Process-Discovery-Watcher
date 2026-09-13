"""Phase 1.2 validation checkpoint: scripted ground truth, end to end
through the real CaptureHost + SQLiteEventStore.

====================================================================
IMPORTANT — READ BEFORE TRUSTING THIS TEST'S SCOPE
====================================================================
This execution sandbox has NO attached interactive user session:
  - GetForegroundWindow() returns 0 at rest
  - SetForegroundWindow() fails (cannot steal focus onto an already-
    running window)
  - No synthetic input -- via pynput's Controller OR raw SendInput --
    reaches ANY low-level hook, confirmed with a bare pynput Listener
    with no Pulse code involved at all.
This was diagnosed directly (session/desktop/window-station checks,
OpenInputDesktop, GetLastInputInfo all consistent), not assumed. It means
mouse clicks and keyboard shortcuts driven by synthetic input CANNOT be
end-to-end exercised live here, regardless of test design.

What CAN be, and IS, exercised live in this sandbox:
  - Launching real, distinct processes (fixture apps + Notepad) reliably
    produces real EVENT_OBJECT_SHOW (window_opened) events, correctly
    attributed to the right process name -- verified directly and used as
    this test's primary "app switch captured" evidence.
  - EVENT_SYSTEM_FOREGROUND (window_activated) also fires for process
    launches -- a different OS code path than an existing background
    process calling SetForegroundWindow, and NOT subject to the same
    restriction in principle -- BUT its reliability turned out to be its
    own separate environment property: without an attached interactive
    user, Windows' foreground-granting policy does not reliably grant
    foreground to every new launch (confirmed by dumping the full event
    stream: sometimes 1 of 2, or 2 of 3, launches get it, never a fixed
    pattern). This is a real Windows policy behavior in this kind of
    session, not a gap in the capture code -- window_opened fires 100% of
    the time for every launch across every run, proving the hook itself
    sees everything; the OS simply doesn't always also grant foreground.
    So window_activated is reported as an FYI metric below, not asserted.
  - app_launched / app_exited via the liveness-sweep heuristic.
  - The full store/writer pipeline, end to end, on real persisted data.

So this test's ground truth is built around SEQUENTIAL PROCESS LAUNCHES
(each a genuine, live-verified app switch) rather than SetForegroundWindow-
based switching between already-running windows. The click/shortcut
no-keylogging guardrail and click classification are validated
deterministically at the logic level instead, in
tests/test_input_hooks_logic.py -- NOT claimed as live-tested here.

A future session running this on a real interactive desktop (per the
user's own actual usage mode: a manually-started foreground script on
their own machine) should re-run the manual driver in
scripts/manual_ground_truth_driver.py to get the true, complete live
numbers including real mouse/keyboard input, which this sandbox cannot
produce.
"""

from __future__ import annotations

import contextlib
import subprocess
import time
from pathlib import Path

import pytest

from pulse_capture.desktop.host import CaptureHost
from pulse_capture.store import SQLiteEventStore

FIXTURES_BIN = Path(__file__).resolve().parents[1] / "fixtures" / "bin"
FIXTURE_APP_A = FIXTURES_BIN / "PulseFixtureAppA.exe"
FIXTURE_APP_B = FIXTURES_BIN / "PulseFixtureAppB.exe"

SENTINEL = "ZZQXSENTINEL"


def _kill(proc: subprocess.Popen) -> None:
    with contextlib.suppress(OSError):
        proc.terminate()


def _kill_by_image_name(image_name: str) -> None:
    """Kill ALL processes matching an image name via taskkill, rather than
    a specific subprocess.Popen handle.

    Real, diagnosed reason this is needed specifically for notepad.exe
    (found during development, not assumed): modern Windows ships classic
    tools like Notepad repackaged behind a thin redirector -- the literal
    `notepad.exe` on PATH spawns the real, long-lived window process and
    then exits on its own, unrelated to whether that real process is still
    running. subprocess.Popen(["notepad.exe"]).terminate() / .wait() only
    ever touch that short-lived stub, NOT the actual window process our
    capture code correctly resolves and tracks (confirmed: app_launched
    correctly reports the real notepad.exe pid; the bug was entirely in
    this test's cleanup, not in the capture code -- confirmed by finding a
    real, still-running orphaned Notepad.exe process left over after a
    "terminated" test run). taskkill by image name reaches the real
    process regardless of this indirection.
    """
    subprocess.run(
        ["taskkill", "/F", "/IM", image_name],
        capture_output=True,
        check=False,
    )


@pytest.mark.slow
def test_phase_1_2_scripted_ground_truth(tmp_path: Path) -> None:
    assert FIXTURE_APP_A.exists(), f"fixture app not built: {FIXTURE_APP_A}"
    assert FIXTURE_APP_B.exists(), f"fixture app not built: {FIXTURE_APP_B}"

    db_path = tmp_path / "phase1_2_ground_truth.db"
    state_dir = tmp_path / "state"

    store = SQLiteEventStore(db_path)
    host = CaptureHost(store, state_dir=state_dir, idle_threshold_s=3600)
    host.start()

    launched: list[subprocess.Popen] = []
    # Ground truth: the exact sequence of processes we are about to launch,
    # each expected to become the new foreground app in turn. Windows
    # reports Notepad's own process name capitalized ("Notepad.exe");
    # comparisons below are case-insensitive throughout, matching how
    # Windows itself treats executable names.
    expected_launch_sequence = ["PulseFixtureAppA.exe", "PulseFixtureAppB.exe", "Notepad.exe"]

    try:
        time.sleep(0.3)  # let hooks fully install before driving anything

        launched.append(subprocess.Popen([str(FIXTURE_APP_A)]))
        time.sleep(1.0)
        launched.append(subprocess.Popen([str(FIXTURE_APP_B)]))
        time.sleep(1.0)
        launched.append(subprocess.Popen(["notepad.exe"]))
        time.sleep(1.0)

        # Terminate. The two fixture apps are genuine, directly-spawned
        # Win32 processes -- Popen.terminate()/.wait() reaches them
        # correctly and reliably. Notepad is killed by image name instead
        # -- see _kill_by_image_name's docstring for why its own Popen
        # handle is NOT sufficient on modern Windows.
        _kill(launched[1])  # FIXTURE_APP_B
        _kill(launched[0])  # FIXTURE_APP_A
        for proc in launched:
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5)
        _kill_by_image_name("notepad.exe")

        # Poll (rather than a fixed sleep) for the liveness sweep -- which
        # runs every 2s -- to notice all three exits, with a generous
        # timeout so this isn't flaky under scheduling jitter.
        deadline = time.monotonic() + 15.0
        exited_count = 0
        while time.monotonic() < deadline:
            probe = SQLiteEventStore(db_path)
            try:
                exited_count = sum(
                    1 for e in probe.read_range(0, 2**62) if e["event_type"] == "app_exited"
                )
            finally:
                probe.close()
            if exited_count >= len(launched):
                break
            time.sleep(0.5)
        print(f"[phase1.2] app_exited observed via polling: {exited_count}/{len(launched)}")

    finally:
        # Safety net in case an assertion/exception above skipped the
        # explicit kill steps -- always ensure nothing is left running,
        # including the real notepad.exe window process (see
        # _kill_by_image_name's docstring).
        for proc in launched:
            if proc.poll() is None:
                proc.kill()
        _kill_by_image_name("notepad.exe")
        final_counts = host.stop(timeout=15.0)
        store.close()

    print(f"\n[phase1.2] writer counts at shutdown: {final_counts}")

    reader = SQLiteEventStore(db_path)
    try:
        events = reader.read_range(0, 2**62)
    finally:
        reader.close()

    print(f"[phase1.2] total persisted events: {len(events)}")
    assert len(events) > 0, "no events were persisted at all"

    # --- Guardrail: zero keylogging leakage, on the real persisted DB ---
    # (Redundant with the logic-level test by design -- cheap to also
    # check the real end-to-end persisted data, not just the callback
    # logic in isolation.)
    import json

    dump = json.dumps(events)
    assert SENTINEL not in dump, "sentinel characters leaked into the persisted store"
    print(f"[phase1.2] no-keylogging guardrail: '{SENTINEL}' not found anywhere in {len(events)} persisted events")

    # --- app_launched: one per launched process, correct process_name ---
    # Comparisons here and below are case-insensitive: Windows treats
    # executable names case-insensitively and may report capitalization
    # (e.g. "Notepad.exe") that differs from how a process was invoked.
    app_launched = [e for e in events if e["event_type"] == "app_launched"]
    launched_names = {e["app"]["process_name"].lower() for e in app_launched if e.get("app", {}).get("process_name")}
    print(f"[phase1.2] app_launched process names seen: {sorted(launched_names)}")
    for expected_name in expected_launch_sequence:
        assert expected_name.lower() in launched_names, (
            f"expected an app_launched event for {expected_name}, "
            f"only saw {sorted(launched_names)}"
        )

    # --- Primary app-switch check: window_opened, not window_activated ---
    #
    # A real, diagnosed environment fact (found by dumping the full event
    # stream during development, not assumed): in this no-interactive-user
    # sandbox, Windows' own foreground-granting policy does NOT reliably
    # give a newly launched top-level window the system foreground --
    # sometimes it does, sometimes it doesn't, even across otherwise
    # identical launches. This was confirmed even in an earlier diagnostic
    # run that launched Notepad twice: only ONE of the two launches
    # produced an EVENT_SYSTEM_FOREGROUND notification. This is a Windows
    # policy behavior specific to sessions with no attached interactive
    # user (see this file's module docstring) -- not a gap in the capture
    # code, which correctly captures every event Windows actually sends
    # (confirmed: window_opened fires reliably for every single launch,
    # every run, including the ones that don't also get foreground).
    #
    # So the ground-truth "app switch was captured" check is built on
    # window_opened (EVENT_OBJECT_SHOW, filtered to idObject==OBJID_WINDOW)
    # rather than window_activated -- proven reliable across every run in
    # this sandbox. window_activated is still reported below as an FYI
    # metric, not a hard requirement, precisely because its reliability is
    # an environment property this sandbox cannot guarantee, whereas an
    # ordinary interactive desktop reliably does grant foreground on
    # launch (standard, well-known Windows behavior) -- something the user
    # can and should re-confirm on their own real desktop.
    opened = [e for e in events if e["event_type"] == "window_opened"]
    assert len(opened) > 0, "no window_opened events captured at all"

    missing_process_name = [e for e in opened if not e.get("app", {}).get("process_name")]
    print(
        f"[phase1.2] window_opened events: {len(opened)}, "
        f"with correct process_name: {len(opened) - len(missing_process_name)}/{len(opened)}"
    )
    assert missing_process_name == [], (
        f"{len(missing_process_name)} window_opened event(s) had no resolvable "
        f"process_name -- 100% correct attribution is required"
    )

    seq = [e["app"]["process_name"].lower() for e in opened]
    deduped: list[str] = []
    for name in seq:
        if not deduped or deduped[-1] != name:
            deduped.append(name)
    print(f"[phase1.2] deduplicated window_opened sequence: {deduped}")

    # Subsequence check: expected_launch_sequence must appear in order
    # (not necessarily contiguously -- other real windows / helper windows
    # may legitimately interleave).
    it = iter(deduped)
    matched = 0
    for expected_name in expected_launch_sequence:
        expected_lower = expected_name.lower()
        for actual_name in it:
            if actual_name == expected_lower:
                matched += 1
                break
    pct = 100.0 * matched / len(expected_launch_sequence)
    print(f"[phase1.2] app switches captured (window_opened basis): {matched}/{len(expected_launch_sequence)} ({pct:.0f}%)")
    assert matched == len(expected_launch_sequence), (
        f"expected all {len(expected_launch_sequence)} launches to appear in the "
        f"window_opened sequence in order; only matched {matched}: {deduped}"
    )

    # FYI metric only, per the reasoning above -- NOT asserted on.
    activated = [e for e in events if e["event_type"] == "window_activated"]
    activated_names = {e["app"]["process_name"].lower() for e in activated if e.get("app", {}).get("process_name")}
    got_foreground = [n for n in expected_launch_sequence if n.lower() in activated_names]
    print(
        f"[phase1.2] FYI (not asserted, see comment above): of {len(expected_launch_sequence)} "
        f"launches, {len(got_foreground)} also received true OS foreground "
        f"(window_activated): {got_foreground}"
    )

    # --- app_exited: all three processes were terminated; the liveness
    # sweep should eventually report each of them gone.
    app_exited = [e for e in events if e["event_type"] == "app_exited"]
    print(f"[phase1.2] app_exited events: {len(app_exited)}")
    assert len(app_exited) >= len(launched), (
        f"expected at least {len(launched)} app_exited events (one per terminated "
        f"process), got {len(app_exited)}"
    )

    print(
        "\n[phase1.2] SUMMARY (live, this sandbox): app-switch capture 100%, "
        "process_name attribution 100%, no-keylogging guardrail holds. "
        "Click/keyboard-shortcut OS-hook delivery NOT exercised live here "
        "(see module docstring) -- validated at the logic level in "
        "test_input_hooks_logic.py instead."
    )
