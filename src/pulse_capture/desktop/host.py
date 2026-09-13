"""Phase 1.2 orchestrator: wires window events + input hooks + idle
detection + app resolution into the Phase 1.1 writer/store, and exposes
the start()/stop()/snapshot() surface run_capture_host.py drives.

Design notes on two things the fixed Stage 1 v1 event_type enum doesn't
have a slot for yet:

  * EVENT_SYSTEM_MINIMIZESTART/END are subscribed to (per the blueprint's
    build step 2) but NOT persisted as their own event -- there is no
    "window_minimized" type in schema/pulse-event.v1.schema.json's v1
    enum, and mapping them onto an unrelated type (e.g. window_closed)
    would misrepresent what happened. They are used only for internal
    bookkeeping (tracking minimize state doesn't currently gate anything
    else either -- this is flagged as a real, deliberate scope gap, not
    silently dropped).

  * app_launched / app_exited are a pragmatic heuristic, not a true
    process-creation/termination trace (which would need a heavier
    mechanism, e.g. WMI process-start/stop events): app_launched fires the
    first time a PID is seen via a resolved window event; app_exited
    fires when a previously-seen PID is later found to no longer exist,
    checked by a periodic liveness sweep. A process that never shows a
    window is invisible to this heuristic -- documented, not hidden.
"""

from __future__ import annotations

import hashlib
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

from pulse_capture.desktop.app_resolver import AppInfo, AppResolver, window_class_name, window_title
from pulse_capture.desktop.idle import IdleDetector
from pulse_capture.desktop.input_hooks import (
    KeyboardHookSource,
    MouseHookSource,
    RawClickEvent,
    RawShortcutEvent,
)
from pulse_capture.desktop.uia_events import UiaResolverThread, snapshot_result_to_event_fields
from pulse_capture.desktop.window_events import (
    EVENT_OBJECT_DESTROY,
    EVENT_OBJECT_FOCUS,
    EVENT_OBJECT_SHOW,
    EVENT_SYSTEM_FOREGROUND,
    EVENT_SYSTEM_MINIMIZEEND,
    EVENT_SYSTEM_MINIMIZESTART,
    RawWindowEvent,
    WindowEventSource,
)
from pulse_capture.schema import new_event, new_session_id
from pulse_capture.store import EventStore
from pulse_capture.writer import EventWriter

_LIVENESS_SWEEP_INTERVAL_S = 2.0

RawEvent = RawWindowEvent | RawClickEvent | RawShortcutEvent


def _persisted_actor_id(state_dir: Path) -> str:
    """A pseudonymous, stable-per-machine+user id, per Phase 1.1's schema
    requirement ("never the raw username"). This is a Phase 1.2-scoped
    placeholder: it persists a random salt in a local file and hashes
    hostname+username+salt. The real design (keyed HMAC via the internal
    Vault, per plans/platform-architecture.md §3) is a Phase 1.8 concern
    for CONTENT values -- actor_id's own hashing here is simpler and not
    yet wired to that SecretsProvider port; noted so it isn't mistaken for
    the final answer.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    salt_path = state_dir / "actor_salt"
    if salt_path.exists():
        salt = salt_path.read_bytes()
    else:
        salt = os.urandom(32)
        salt_path.write_bytes(salt)
    material = f"{os.environ.get('COMPUTERNAME', 'unknown-host')}:{os.environ.get('USERNAME', 'unknown-user')}".encode()
    return hashlib.sha256(material + salt).hexdigest()[:32]


class CaptureHost:
    def __init__(
        self,
        store: EventStore,
        *,
        state_dir: Path,
        idle_threshold_s: float = 60.0,
        raw_queue_maxsize: int = 20_000,
    ) -> None:
        self.session_id = new_session_id()
        self.actor_id = _persisted_actor_id(state_dir)

        self._store = store
        self._writer = EventWriter(store, session_id=self.session_id, actor_id=self.actor_id)
        self._resolver = AppResolver()

        self._raw_queue: queue.Queue[RawEvent] = queue.Queue(maxsize=raw_queue_maxsize)
        self._window_src = WindowEventSource(self._raw_queue)
        self._mouse_src = MouseHookSource(self._raw_queue)
        self._keyboard_src = KeyboardHookSource(self._raw_queue)
        self._idle = IdleDetector(
            on_idle_start=self._on_idle_start,
            on_idle_end=self._on_idle_end,
            threshold_s=idle_threshold_s,
        )

        self._uia = UiaResolverThread(emit_event=self._emit_uia_event, degraded_callback=self._on_uia_degraded)

        self._resolver_thread: threading.Thread | None = None
        self._sweep_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._known_pids: set[int] = set()
        self._minimized_hwnds: set[int] = set()
        self._started_at_mono = 0

        self._counts_lock = threading.Lock()
        self.raw_events_seen = 0

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        self._started_at_mono = time.monotonic_ns()
        self._writer.start()
        self._window_src.start()
        self._mouse_src.start()
        self._keyboard_src.start()
        self._idle.start()
        self._uia.start()

        self._resolver_thread = threading.Thread(target=self._resolver_loop, name="pulse-resolver", daemon=False)
        self._resolver_thread.start()
        self._sweep_thread = threading.Thread(target=self._liveness_sweep_loop, name="pulse-liveness", daemon=False)
        self._sweep_thread.start()

    def stop(self, timeout: float = 10.0) -> dict[str, int]:
        # Stop producers first so no new raw events arrive mid-drain.
        self._mouse_src.stop()
        self._keyboard_src.stop()
        self._window_src.stop()
        self._idle.stop()
        self._uia.stop()

        self._stop_event.set()
        if self._resolver_thread is not None:
            self._resolver_thread.join(timeout=timeout)
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=timeout)

        # Flush: block until every event already handed to the writer is
        # actually written, per the Ctrl+C "must not risk a lossy write"
        # operational requirement.
        self._writer.stop(timeout=timeout)

        return self.snapshot()

    def snapshot(self) -> dict[str, int]:
        w = self._writer.snapshot()
        with self._counts_lock:
            raw_seen = self.raw_events_seen
        uptime_s = int((time.monotonic_ns() - self._started_at_mono) / 1e9) if self._started_at_mono else 0
        return {**w, "raw_events_seen": raw_seen, "uptime_s": uptime_s}

    # -- idle callbacks (called from IdleDetector's own thread) ---------------

    def _on_idle_start(self, t_mono_ns: int, t_wall_us: int) -> None:
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type="idle_start",
                session_id=self.session_id,
                actor_id=self.actor_id,
                t_mono_ns=t_mono_ns,
                t_wall_utc=t_wall_us,
            )
        )

    def _on_idle_end(self, t_mono_ns: int, t_wall_us: int) -> None:
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type="idle_end",
                session_id=self.session_id,
                actor_id=self.actor_id,
                t_mono_ns=t_mono_ns,
                t_wall_utc=t_wall_us,
            )
        )

    # -- process liveness sweep (app_exited heuristic) ------------------------

    def _liveness_sweep_loop(self) -> None:
        while not self._stop_event.wait(_LIVENESS_SWEEP_INTERVAL_S):
            for pid in list(self._known_pids):
                try:
                    if not self._resolver.is_process_alive(pid):
                        self._known_pids.discard(pid)
                        self._resolver.invalidate(pid)
                        self._writer.submit(
                            new_event(
                                producer="desktop",
                                event_type="app_exited",
                                session_id=self.session_id,
                                actor_id=self.actor_id,
                                app={"process_name": None, "pid": pid, "exe_path_hash": None, "app_class": None},
                            )
                        )
                except Exception as exc:  # noqa: BLE001 -- see _resolver_loop's identical rationale
                    print(f"[pulse-liveness] error checking pid {pid}: {exc!r}", flush=True)

    # -- resolver loop: raw events -> full Stage 1 events -------------------

    def _resolver_loop(self) -> None:
        while True:
            try:
                raw = self._raw_queue.get(timeout=0.2)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue

            with self._counts_lock:
                self.raw_events_seen += 1

            try:
                if isinstance(raw, RawWindowEvent):
                    self._handle_window_event(raw)
                elif isinstance(raw, RawClickEvent):
                    self._handle_click_event(raw)
                elif isinstance(raw, RawShortcutEvent):
                    self._handle_shortcut_event(raw)
            except Exception as exc:  # noqa: BLE001 -- deliberate, see below
                # One malformed/unexpected raw event must never take down
                # the whole resolver thread for the rest of the session --
                # a background thread dying silently here is a far worse
                # outcome than dropping (and reporting) one event. This is
                # the defense-in-depth complement to fixing the specific
                # known cause (a garbage pid from certain WinEvent focus
                # notifications -- see app_resolver.py's pid<=0 guard);
                # this catch-all protects against causes not yet known.
                print(f"[pulse-resolver] error handling raw event {raw!r}: {exc!r}", flush=True)

            if self._stop_event.is_set() and self._raw_queue.empty():
                return

    def _maybe_emit_app_launched(self, app: AppInfo) -> None:
        if app.pid is None or app.pid in self._known_pids:
            return
        self._known_pids.add(app.pid)
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type="app_launched",
                session_id=self.session_id,
                actor_id=self.actor_id,
                app=app.as_dict(),
            )
        )

    def _window_dict(self, hwnd: int) -> dict[str, str | None]:
        return {
            "hwnd_or_tab_id": str(hwnd),
            "title": window_title(hwnd),
            "url": None,
            "window_class": window_class_name(hwnd),
        }

    def _handle_window_event(self, raw: RawWindowEvent) -> None:
        app = self._resolver.resolve_hwnd(raw.hwnd)
        self._maybe_emit_app_launched(app)

        if raw.event_id == EVENT_SYSTEM_MINIMIZESTART:
            self._minimized_hwnds.add(raw.hwnd)
            return  # no v1 event_type for this -- see module docstring
        if raw.event_id == EVENT_SYSTEM_MINIMIZEEND:
            self._minimized_hwnds.discard(raw.hwnd)
            return

        if raw.event_id == EVENT_SYSTEM_FOREGROUND:
            # Drives Phase 1.3/1.4's UIA subscription rescoping -- see
            # notify_foreground_changed's docstring for why this, and not
            # UIA's own (narrower) AutomationFocusChangedEvent alone, is
            # needed to keep the UIA thread scoped to the actual
            # foreground window.
            self._uia.notify_foreground_changed(raw.hwnd)

        event_type = {
            EVENT_SYSTEM_FOREGROUND: "window_activated",
            EVENT_OBJECT_FOCUS: "focus_changed",
            EVENT_OBJECT_SHOW: "window_opened",
            EVENT_OBJECT_DESTROY: "window_closed",
        }.get(raw.event_id)
        if event_type is None:
            return

        self._writer.submit(
            new_event(
                producer="desktop",
                event_type=event_type,
                session_id=self.session_id,
                actor_id=self.actor_id,
                t_mono_ns=raw.t_mono_ns,
                t_wall_utc=raw.t_wall_utc_us,
                app=app.as_dict(),
                window=self._window_dict(raw.hwnd),
            )
        )

    def _handle_click_event(self, raw: RawClickEvent) -> None:
        app = self._resolver.resolve_hwnd(raw.hwnd)
        self._maybe_emit_app_launched(app)
        extra = self._resolve_uia_extra(raw.hwnd, raw.x, raw.y, origin_t_mono_ns=raw.t_mono_ns)
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type=raw.action,  # "click" | "double_click" | "context_click"
                session_id=self.session_id,
                actor_id=self.actor_id,
                t_mono_ns=raw.t_mono_ns,
                t_wall_utc=raw.t_wall_utc_us,
                app=app.as_dict(),
                window=self._window_dict(raw.hwnd),
                **extra,
            )
        )

    def _handle_shortcut_event(self, raw: RawShortcutEvent) -> None:
        app = self._resolver.resolve_hwnd(raw.hwnd)
        self._maybe_emit_app_launched(app)
        extra = self._resolve_uia_extra(raw.hwnd, None, None, origin_t_mono_ns=raw.t_mono_ns)
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type="key_shortcut",
                session_id=self.session_id,
                actor_id=self.actor_id,
                t_mono_ns=raw.t_mono_ns,
                t_wall_utc=raw.t_wall_utc_us,
                app=app.as_dict(),
                window=self._window_dict(raw.hwnd),
                **extra,
            )
        )

    def _resolve_uia_extra(self, hwnd: int, x: int | None, y: int | None, *, origin_t_mono_ns: int) -> dict[str, Any]:
        """Phase 1.3 build step 4: enrich a click/shortcut action event with
        the acting element + bounded context neighbourhood. Applied to
        clicks and shortcuts (the "actions" the blueprint's step 4 example
        describes) -- deliberately NOT to window_opened/closed/activated/
        focus_changed, which fire far more often and are window-level
        bookkeeping rather than an "action" with an acting element.

        A timeout or missing UIA provider degrades gracefully: the event
        still gets written with app/window attribution, just without
        element/context, and a capture_meta.degraded_reason records why --
        never silently dropped, never a fabricated element.
        """
        # A generous WAIT timeout (distinct from the 150ms pass/fail gate
        # itself, which is asserted on the measured latency_ms downstream,
        # not on this value): measured on a real, busy interactive desktop,
        # round-trip time can exceed the UIA thread's own 120ms snapshot
        # budget because that ONE thread also processes a constant stream
        # of unrelated system-wide FocusChangedEvent notifications (every
        # focus change anywhere on the desktop reaches it, since that
        # handler is necessarily global -- see uia_events.py). A short wait
        # here would just turn "the thread was busy" into a fabricated
        # "no element" result instead of the real, slightly-slow number.
        result = self._uia.request_snapshot(hwnd, x, y, timeout_s=1.0)
        # True end-to-end latency per the blueprint's go/no-go gate: from
        # the INPUT HOOK's own timestamp (raw.t_mono_ns, captured the
        # instant the hardware event was seen) to right now -- not just the
        # UIA thread's internal snapshot-build time, which is a subset of
        # this and would understate the number a user actually experiences.
        end_to_end_ms = (time.monotonic_ns() - origin_t_mono_ns) / 1e6
        if result is None:
            return {
                "capture_meta": {
                    "latency_ms": end_to_end_ms,
                    "dropped_before": None,
                    "degraded_reason": "snapshot_request_timeout",
                    "hmac_key_generation": None,
                }
            }
        fields = snapshot_result_to_event_fields(result)
        fields["capture_meta"]["latency_ms"] = end_to_end_ms
        return fields

    # -- UIA-originated events (Phase 1.3 field_value_changed, Phase 1.4 text_selected) --

    def _emit_uia_event(self, fields: dict[str, Any]) -> None:
        hwnd = fields.pop("hwnd", 0)
        app = self._resolver.resolve_hwnd(hwnd)
        self._maybe_emit_app_launched(app)
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type=fields.pop("event_type"),
                session_id=self.session_id,
                actor_id=self.actor_id,
                app=app.as_dict(),
                window=self._window_dict(hwnd),
                **fields,
            )
        )

    def _on_uia_degraded(self, reason: str, extra: dict[str, Any] | None) -> None:
        self._writer.submit(
            new_event(
                producer="desktop",
                event_type="capture_degraded",
                session_id=self.session_id,
                actor_id=self.actor_id,
                capture_meta={"latency_ms": None, "dropped_before": None, "degraded_reason": reason, "hmac_key_generation": None},
            )
        )
