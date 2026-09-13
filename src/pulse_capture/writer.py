"""Phase 1.1 step 6 — the writer with backpressure.

A bounded in-memory queue drained by a single writer thread, batching
inserts (~100 events or 250ms, whichever first). On queue-full: drop and
increment a counter, then emit a `capture_degraded` event — never block a
hook callback (a blocked low-level hook is removed by Windows; a blocked
UIA callback stalls the provider application).

This module also owns the "flush on clean shutdown" behavior the
operational requirement (Ctrl+C must not risk a corrupt/lossy write) is
built on: `stop()` drains whatever is still sitting in the queue and
writes it before returning, distinct from (and in addition to) the
store's own crash-safety under an unclean kill.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from typing import Any

from pulse_capture.schema import new_event
from pulse_capture.store import EventStore

_DEGRADED_EMIT_INTERVAL_S = 2.0


class EventWriter:
    def __init__(
        self,
        store: EventStore,
        *,
        session_id: str,
        actor_id: str,
        maxsize: int = 10_000,
        batch_size: int = 100,
        batch_interval_s: float = 0.25,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._actor_id = actor_id
        self._batch_size = batch_size
        self._batch_interval_s = batch_interval_s

        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=maxsize)
        self._thread: threading.Thread | None = None
        self._shutdown = threading.Event()

        self._lock = threading.Lock()  # protects the counters below
        self.submitted = 0
        self.written = 0
        self.dropped = 0
        self.rejected = 0
        self._last_degraded_emit = 0.0
        self._dropped_since_last_emit = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("EventWriter already started")
        self._thread = threading.Thread(target=self._run, name="pulse-writer", daemon=False)
        self._thread.start()

    def stop(self, timeout: float | None = 10.0) -> None:
        """Signal shutdown, then BLOCK until the writer thread has drained
        the queue and written everything, or the timeout elapses.
        """
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                # Should not happen in practice (drain is bounded by queue
                # size), but never silently pretend we flushed if we didn't.
                raise TimeoutError(
                    "EventWriter did not finish flushing within the timeout; "
                    f"~{self._queue.qsize()} events may still be unwritten."
                )

    # -- submission (hot path — must never block) -----------------------------

    def submit(self, event: dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            with self._lock:
                self.dropped += 1
                self._dropped_since_last_emit += 1
            self._maybe_emit_degraded()
            return False
        with self._lock:
            self.submitted += 1
        return True

    def _maybe_emit_degraded(self) -> None:
        now = time.monotonic()
        if now - self._last_degraded_emit < _DEGRADED_EMIT_INTERVAL_S:
            return
        self._last_degraded_emit = now
        with self._lock:
            dropped_before = self._dropped_since_last_emit
            self._dropped_since_last_emit = 0
        degraded = new_event(
            producer="desktop",
            event_type="capture_degraded",
            session_id=self._session_id,
            actor_id=self._actor_id,
            capture_meta={
                "dropped_before": dropped_before,
                "degraded_reason": "writer_queue_full",
            },
        )
        # Best-effort: if even this can't fit, the dropped counter above is
        # still the honest record that something was lost.
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(degraded)

    # -- writer thread -----------------------------------------------------

    def _run(self) -> None:
        while True:
            batch = self._collect_batch()
            if batch:
                self._write_batch(batch)
            if self._shutdown.is_set() and self._queue.empty():
                # Final drain: anything that landed between the last
                # _collect_batch() call and here.
                final = self._drain_nowait()
                if final:
                    self._write_batch(final)
                return

    def _collect_batch(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._batch_interval_s
        while len(batch) < self._batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=remaining))
            except queue.Empty:
                break
        return batch

    def _drain_nowait(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                return batch

    def _write_batch(self, batch: list[dict[str, Any]]) -> None:
        rejected = self._store.append_batch(batch)
        with self._lock:
            self.written += len(batch) - len(rejected)
            self.rejected += len(rejected)
        for _event, error in rejected:
            # A rejection reaching here means something built an invalid
            # event upstream — a real bug, not user error, so it goes to
            # stderr immediately rather than being silently swallowed.
            print(f"[pulse-writer] REJECTED event: {error}", flush=True)

    # -- introspection for the status line -----------------------------------

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "submitted": self.submitted,
                "written": self.written,
                "dropped": self.dropped,
                "rejected": self.rejected,
                "queued": self._queue.qsize(),
            }
