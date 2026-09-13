"""Phase 1.3 build step 3 + Phase 1.4: UIA event subscriptions, owned by one
dedicated STA thread -- ``AutomationFocusChangedEvent``,
``AutomationPropertyChangedEvent`` on ``ValuePattern.Value``, a narrowly
scoped ``StructureChangedEvent``, and (Phase 1.4) ``TextSelectionChangedEvent``.

Why one thread owns all of it: COM interface pointers created in an STA are
apartment-affine, and Microsoft's own UIA docs warn against adding/removing
event handlers from more than one thread. So every UIA call in this module
-- registration, removal, and the on-demand context-snapshot builds
Phase 1.3 needs for click/shortcut enrichment -- happens on this one thread,
which pumps a real Win32 message loop (out-of-context COM callbacks are
delivered via the registering thread's message queue, exactly like
SetWinEventHook in window_events.py -- same reasoning, same pattern).

Other threads (host.py's resolver thread) ask this thread to do work via a
plain thread-safe queue plus a custom thread-message to wake the pump loop,
and block on a per-request ``threading.Event`` with a timeout -- so the
Phase 1.3 latency checkpoint's budget (120 ms snapshot budget, subject to a
150 ms end-to-end p95 gate) is enforced by the SAME mechanism a caller uses
to get a result, not bolted on separately.
"""

from __future__ import annotations

import contextlib
import ctypes
import queue
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

import comtypes
import comtypes.client
import win32gui
from comtypes import COMObject
from pynput import mouse

from pulse_capture.desktop import uia_client as uc

comtypes.client.GetModule("UIAutomationCore.dll")
import comtypes.gen.UIAutomationClient as UIA  # noqa: E402

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []

WM_QUIT = 0x0012
WM_USER = 0x0400
WM_PULSE_WORK = WM_USER + 1  # wake the pump loop to drain the work queue

TreeScope_Element = 0x1
TreeScope_Subtree = 0x7

# Debounce window for text_selected on selection "settle" (blueprint step 3).
_SELECTION_SETTLE_S = 0.300
# Mouse-drag heuristic thresholds for the Phase 1.4 fallback (build step 2).
_DRAG_PIXEL_THRESHOLD = 6


@dataclass
class _SnapshotRequest:
    hwnd: int
    x: int | None
    y: int | None
    done: threading.Event
    result: uc.SnapshotResult | None = None


class UiaResolverThread:
    """Owns the UIA COM object, the event-handler registrations, and the
    on-demand element/context resolution Phase 1.3 needs. Emits
    `field_value_changed` and `text_selected` events directly to the
    writer (these are asynchronous, not requested by a caller); exposes
    `request_snapshot()` as the synchronous API host.py's resolver thread
    uses to enrich a click/shortcut event with `element` + `context`.
    """

    def __init__(
        self,
        *,
        emit_event: Callable[[dict[str, Any]], None],
        degraded_callback: Callable[[str, dict[str, Any] | None], None],
    ) -> None:
        # `emit_event` builds+submits a full Stage 1 event dict (host.py
        # supplies a closure that fills in session_id/actor_id/app/window
        # and calls writer.submit) -- kept generic so this module doesn't
        # need to know about EventWriter directly.
        self._emit_event = emit_event
        self._degraded_callback = degraded_callback

        self._thread: threading.Thread | None = None
        self._win_thread_id: int | None = None
        self._ready = threading.Event()
        self._stopping = False

        self._work_queue: queue.Queue[_SnapshotRequest] = queue.Queue()
        self._rescope_queue: queue.Queue[int] = queue.Queue()

        self._ctx: uc.UiaContext | None = None
        self._scoped_hwnd: int = 0

        self._focus_handler: Any = None
        self._property_handler: Any = None
        self._structure_handler: Any = None
        self._text_selection_handler: Any = None
        self.structure_change_count = 0

        # Phase 1.4 debounce state: last-seen selection per element identity.
        self._pending_selection: dict[int, tuple[str, float]] = {}  # id(sender) -> (text, last_seen_mono)
        # Last EMITTED (not just pending) selection per element, so a
        # second selection-finalisation notification arriving just after
        # the debounce window already flushed doesn't re-emit an identical,
        # redundant event -- see _debounced_emit_selection's docstring.
        self._last_emitted_selection: dict[int, tuple[str, float]] = {}
        self._selection_lock = threading.Lock()

        self._drag_listener: mouse.Listener | None = None
        self._drag_down: tuple[int, int, float] | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self, timeout: float = 5.0) -> None:
        self._thread = threading.Thread(target=self._run, name="pulse-uia", daemon=False)
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            raise TimeoutError("UiaResolverThread did not start in time")

        self._drag_listener = mouse.Listener(on_click=self._on_drag_click)
        self._drag_listener.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stopping = True
        if self._drag_listener is not None:
            self._drag_listener.stop()
            self._drag_listener.join(timeout=5)
        if self._thread is None or self._win_thread_id is None:
            return
        user32.PostThreadMessageW(self._win_thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        comtypes.CoInitialize()
        self._win_thread_id = kernel32.GetCurrentThreadId()
        try:
            self._ctx = uc.UiaContext()
            self._register_focus_handler()
        finally:
            self._ready.set()  # unblock start() either way; failures surface as "everything degraded"

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_PULSE_WORK:
                self._drain_work_queue()
                continue
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._unregister_all()
        comtypes.CoUninitialize()

    # -- public synchronous API (called from OTHER threads) -----------------

    def request_snapshot(self, hwnd: int, x: int | None = None, y: int | None = None, timeout_s: float = 0.25) -> uc.SnapshotResult | None:
        if self._win_thread_id is None:
            return None
        req = _SnapshotRequest(hwnd=hwnd, x=x, y=y, done=threading.Event())
        self._work_queue.put_nowait(req)
        user32.PostThreadMessageW(self._win_thread_id, WM_PULSE_WORK, 0, 0)
        if req.done.wait(timeout=timeout_s):
            return req.result
        return None  # caller treats a timeout as capture_degraded("snapshot_timeout")

    def notify_foreground_changed(self, hwnd: int) -> None:
        """Tell the UIA thread the foreground window changed, so it can
        rescope PropertyChanged/StructureChanged/TextSelectionChanged to
        it. host.py calls this from Phase 1.2's window_activated handling
        (SetWinEventHook's EVENT_SYSTEM_FOREGROUND), which is proven
        reliable across this whole session's testing.

        This exists ALONGSIDE (not instead of) UIA's own
        AutomationFocusChangedEvent because that event tracks a narrower
        thing than "the foreground window changed" -- it fires when
        keyboard-input focus moves to a specific element, which is not
        guaranteed to happen just because a window becomes foreground
        (confirmed by testing: forcing a window to the foreground with no
        real keyboard interaction inside it left the UIA thread scoped to
        whatever window last held actual UI Automation focus, sometimes
        an unrelated app, indefinitely). Reusing Phase 1.2's own
        already-reliable foreground signal closes that gap.
        """
        if self._win_thread_id is None:
            return
        self._rescope_queue.put_nowait(hwnd)
        user32.PostThreadMessageW(self._win_thread_id, WM_PULSE_WORK, 0, 0)

    # -- work queue, processed on the UIA thread ----------------------------

    def _drain_work_queue(self) -> None:
        while True:
            try:
                hwnd = self._rescope_queue.get_nowait()
            except queue.Empty:
                break
            with contextlib.suppress(Exception):
                self._rescope_if_needed(hwnd)
        while True:
            try:
                req = self._work_queue.get_nowait()
            except queue.Empty:
                return
            req.result = self._build_snapshot(req.hwnd, req.x, req.y)
            req.done.set()

    def _build_snapshot(self, hwnd: int, x: int | None, y: int | None) -> uc.SnapshotResult:
        assert self._ctx is not None
        start = time.monotonic()
        if x is not None and y is not None:
            element = self._ctx.element_from_point(x, y)
        else:
            element = self._ctx.element_from_hwnd(hwnd)

        if not uc._ok(element):
            return uc.SnapshotResult(element=None, degraded=True, degraded_reason="no_uia_provider", latency_ms=(time.monotonic() - start) * 1000.0)

        window_root_hwnd = uc.top_level_hwnd_for(hwnd)
        try:
            snap = uc.build_element_snapshot(element, self._ctx.uia, self._ctx.walker, window_root_hwnd)
        except Exception:
            return uc.SnapshotResult(element=None, degraded=True, degraded_reason="resolution_error", latency_ms=(time.monotonic() - start) * 1000.0)

        context, degraded, reason = uc.build_context_snapshot(element, self._ctx.uia, self._ctx.walker, window_root_hwnd)
        latency_ms = (time.monotonic() - start) * 1000.0
        return uc.SnapshotResult(element=snap, context=context, degraded=degraded, degraded_reason=reason, latency_ms=latency_ms)

    # -- focus-driven rescoping ----------------------------------------------

    def _register_focus_handler(self) -> None:
        assert self._ctx is not None
        self._focus_handler = _FocusHandler(self._on_focus_changed)
        self._ctx.uia.AddFocusChangedEventHandler(self._ctx.cache_request, self._focus_handler)
        # Establish an initial scope from whatever has focus right now,
        # rather than waiting for the first focus change.
        self._rescope_if_needed(win32gui.GetForegroundWindow())

    def _on_focus_changed(self, _sender: Any) -> None:
        with contextlib.suppress(Exception):
            self._rescope_if_needed(win32gui.GetForegroundWindow())

    def _rescope_if_needed(self, foreground_hwnd: int) -> None:
        assert self._ctx is not None
        if not foreground_hwnd or foreground_hwnd == self._scoped_hwnd:
            return
        self._unregister_scoped_handlers()

        window_element = self._ctx.element_from_hwnd(foreground_hwnd)
        if not uc._ok(window_element):
            self._scoped_hwnd = 0
            return

        try:
            self._property_handler = _PropertyChangedHandler(self._on_property_changed)
            value_prop_array = (ctypes.c_long * 1)(UIA.UIA_ValueValuePropertyId)
            self._ctx.uia.AddPropertyChangedEventHandlerNativeArray(
                window_element, TreeScope_Subtree, self._ctx.cache_request, self._property_handler, value_prop_array, 1
            )
        except Exception:
            self._property_handler = None

        try:
            self._structure_handler = _StructureChangedHandler(self._on_structure_changed)
            self._ctx.uia.AddStructureChangedEventHandler(window_element, TreeScope_Subtree, self._ctx.cache_request, self._structure_handler)
        except Exception:
            self._structure_handler = None

        try:
            self._text_selection_handler = _AutomationEventHandler(self._on_text_selection_changed)
            self._ctx.uia.AddAutomationEventHandler(
                UIA.UIA_Text_TextSelectionChangedEventId, window_element, TreeScope_Subtree, self._ctx.cache_request, self._text_selection_handler
            )
        except Exception:
            self._text_selection_handler = None

        self._scoped_hwnd = foreground_hwnd

    def _unregister_scoped_handlers(self) -> None:
        assert self._ctx is not None
        if self._property_handler is not None:
            with contextlib.suppress(Exception):
                self._ctx.uia.RemovePropertyChangedEventHandler(self._ctx.uia.GetRootElement(), self._property_handler)
            self._property_handler = None
        if self._structure_handler is not None:
            with contextlib.suppress(Exception):
                self._ctx.uia.RemoveStructureChangedEventHandler(self._ctx.uia.GetRootElement(), self._structure_handler)
            self._structure_handler = None
        if self._text_selection_handler is not None:
            with contextlib.suppress(Exception):
                self._ctx.uia.RemoveAutomationEventHandler(
                    UIA.UIA_Text_TextSelectionChangedEventId, self._ctx.uia.GetRootElement(), self._text_selection_handler
                )
            self._text_selection_handler = None

    def _unregister_all(self) -> None:
        if self._ctx is None:
            return
        self._unregister_scoped_handlers()
        if self._focus_handler is not None:
            with contextlib.suppress(Exception):
                self._ctx.uia.RemoveFocusChangedEventHandler(self._focus_handler)
        with contextlib.suppress(Exception):
            self._ctx.uia.RemoveAllEventHandlers()

    # -- field_value_changed (Phase 1.3 build step 3 / typed-value source) --

    def _on_property_changed(self, sender: Any, property_id: int, new_value: Any) -> None:
        if property_id != UIA.UIA_ValueValuePropertyId:
            return
        try:
            is_password = bool(sender.CachedIsPassword)
        except Exception:
            is_password = False

        assert self._ctx is not None
        window_root_hwnd = 0
        with contextlib.suppress(Exception):
            window_root_hwnd = uc.top_level_hwnd_for(self._scoped_hwnd)

        try:
            snap = uc.build_element_snapshot(sender, self._ctx.uia, self._ctx.walker, window_root_hwnd)
        except Exception:
            snap = None

        if is_password:
            # Build step 6: skip password fields STRUCTURALLY -- the value
            # is never read into a Python variable at all beyond the COM
            # callback's own `new_value` parameter, which is discarded here
            # unused, never logged, never passed to _emit_event.
            content = {"value_hmac": None, "value_readable": None, "class": None, "redaction_state": "password_field"}
        else:
            # No Phase 1.8 (privacy/redaction) yet -- deliberately, honestly
            # unclassified rather than mislabelled as safe. See host.py's
            # module docstring and BUILD-STATUS.md for the scope note this
            # depends on.
            value_str = None
            with contextlib.suppress(Exception):
                value_str = str(new_value) if new_value is not None else None
            content = {
                "value_hmac": None,
                "value_readable": value_str,
                "class": None,
                "redaction_state": "unclassified_pending_phase_1_8",
            }

        event_extra = {
            "hwnd": self._scoped_hwnd,
            "element": _snapshot_to_dict(snap) if snap else None,
            "content": content,
            "sensor": {"tier": "t1_uia", "confidence": 1.0, "agreement": "single_sensor"},
        }
        self._emit_event({"event_type": "field_value_changed", **event_extra})

    # -- text_selected (Phase 1.4) -------------------------------------------

    def _on_structure_changed(self, _sender: Any, _change_type: int, _runtime_id: Any) -> None:
        self.structure_change_count += 1  # bookkeeping only -- no v1 event_type for this, same documented gap as Phase 1.2's minimize events

    def _on_text_selection_changed(self, sender: Any, _event_id: int) -> None:
        text_pattern = uc.get_text_pattern(sender)
        if text_pattern is None:
            return
        try:
            ranges = text_pattern.GetSelection()
            count = ranges.Length
            if count < 1:
                return
            first_range = ranges.GetElement(0)
            text = first_range.GetText(-1)
        except Exception:
            return
        if not text:
            return
        self._debounced_emit_selection(sender, str(text), source="uia_textpattern")

    @staticmethod
    def _element_identity_key(element: Any) -> Any:
        """A hashable, stable identity for `element` across separate COM
        callbacks -- see _debounced_emit_selection's bug #2 note. Falls
        back to id() only if GetRuntimeId() itself is unavailable, which
        would otherwise just reproduce the same bug for that one element.
        """
        try:
            runtime_id = element.GetRuntimeId()
            return tuple(runtime_id)
        except Exception:
            return id(element)

    def _debounced_emit_selection(self, sender: Any, text: str, *, source: str) -> None:
        # Selection-changed fires repeatedly while dragging; emit once per
        # settle (blueprint step 3: default 300 ms of stability), keyed by
        # the sender element's identity so concurrent selections in two
        # different controls debounce independently.
        #
        # Real bug #1, found by testing: an earlier version compared "is
        # the dict's last-seen time CLOSE to now" to decide whether to
        # skip. That is not exact enough -- during a drag, selection-changed
        # can fire every ~15-20 ms, spawning one flush-timer thread per
        # event; several of those threads' 300 ms deadlines can each
        # independently observe "no update in the last ~290 ms" and all
        # fire, producing 2-3 events for one drag instead of one. Fixed
        # with the standard debounce pattern: each scheduled flush stores
        # the EXACT token (a monotonic float) it saw, and at wake time
        # fires only if the dict's current token is still identical to its
        # own -- i.e. it is the LAST one scheduled, not merely "recent
        # enough".
        #
        # Real bug #2, found by testing THAT fix: using `id(sender)` as the
        # per-element key is unreliable across separate COM callback
        # invocations -- comtypes can hand back a different Python wrapper
        # object for the same underlying UI element on each callback, so
        # two bursts ~50-100ms apart (an intermediate drag notification and
        # a mouse-up finalisation notification) got DIFFERENT ids and were
        # tracked as two unrelated elements, defeating both the debounce
        # and the duplicate-suppression check below. `GetRuntimeId()` is
        # UIA's own API for exactly this -- a stable identifier for "the
        # same real UI element", independent of which wrapper object
        # happens to represent it in this particular callback.
        key = self._element_identity_key(sender)
        my_token = time.monotonic()
        with self._selection_lock:
            self._pending_selection[key] = (text, my_token)

        def _flush_if_settled() -> None:
            time.sleep(_SELECTION_SETTLE_S)
            with self._selection_lock:
                entry = self._pending_selection.get(key)
                if entry is None or entry[1] != my_token:
                    return  # superseded by a later selection-changed event; that one's timer will flush
                del self._pending_selection[key]
                # A second, separate debounce burst for the SAME element
                # with the SAME text landing within one settle window of
                # the last emission is a redundant notification (observed:
                # a drag's move-driven selection-changed and its
                # mouse-up-driven finalisation can arrive as two bursts a
                # few tens of ms apart, straddling the debounce window),
                # not a second real selection -- suppress it rather than
                # emit a duplicate.
                last = self._last_emitted_selection.get(key)
                if last is not None and last[0] == text and (my_token - last[1]) < _SELECTION_SETTLE_S:
                    return
                self._last_emitted_selection[key] = (text, my_token)
            sensor: dict[str, Any] = {
                "tier": "t1_uia",
                "confidence": 1.0 if source == "uia_textpattern" else 0.5,
                "agreement": "single_sensor",
            }
            if source == "inferred_selection":
                # Honest labelling per blueprint step 2: this value is a
                # best-effort heuristic (drag detected + best-available text
                # read), NOT an observed TextPattern selection, and must
                # never be presented as equally reliable. `fallback_reason`
                # is the schema's designated place to record exactly that.
                sensor["fallback_reason"] = "inferred_selection_drag_heuristic"
            self._emit_event(
                {
                    "event_type": "text_selected",
                    "hwnd": self._scoped_hwnd,
                    "content": {
                        "value_hmac": None,
                        "value_readable": text,
                        "class": None,
                        "redaction_state": "unclassified_pending_phase_1_8",
                    },
                    "sensor": sensor,
                }
            )

        threading.Thread(target=_flush_if_settled, name="pulse-selection-debounce", daemon=True).start()

    # -- Phase 1.4 fallback: mouse-drag heuristic for non-TextPattern controls --

    def _on_drag_click(self, x: int, y: int, _button: Any, pressed: bool) -> None:
        if self._stopping:
            return
        if pressed:
            self._drag_down = (x, y, time.monotonic())
            return
        if self._drag_down is None:
            return
        down_x, down_y, _down_t = self._drag_down
        self._drag_down = None
        distance = max(abs(x - down_x), abs(y - down_y))
        if distance < _DRAG_PIXEL_THRESHOLD:
            return  # not a drag -- MouseHookSource's own click logic already covers plain clicks

        hwnd = win32gui.WindowFromPoint((x, y))
        req = _SnapshotRequest(hwnd=hwnd, x=x, y=y, done=threading.Event())
        self._work_queue.put_nowait(req)
        if self._win_thread_id is not None:
            user32.PostThreadMessageW(self._win_thread_id, WM_PULSE_WORK, 0, 0)
        if not req.done.wait(timeout=0.25) or req.result is None or req.result.element is None:
            return

        # If the element supports TextPattern, the primary mechanism above
        # already handles it -- do not double-report the same selection
        # from both paths. This heuristic exists ONLY for controls that
        # don't expose TextPattern at all.
        assert self._ctx is not None
        element = self._ctx.element_from_point(x, y)
        if not uc._ok(element):
            return
        if uc.get_text_pattern(element) is not None:
            return

        text = uc._element_text(element, uc.MAX_CHARS_PER_ELEMENT)
        if not text:
            return
        # Best-effort and explicitly imperfect: without TextPattern there is
        # no generic way to know exactly which substring was highlighted, so
        # the control's whole visible text/value is reported -- which is
        # exactly why this path is labelled `inferred_selection` and scored
        # lower than the TextPattern-observed path, never presented as
        # equally reliable (research log §5.3 / blueprint step 2).
        self._debounced_emit_selection(element, text, source="inferred_selection")


def _snapshot_to_dict(snap: uc.ElementSnapshot) -> dict[str, Any]:
    return {
        "automation_id": snap.automation_id,
        "name": snap.name,
        "control_type": snap.control_type,
        "role": snap.role,
        "framework": snap.framework_id,
        "path_hash": snap.path_hash,
        "bounds": snap.bounds,
    }


def snapshot_result_to_event_fields(result: uc.SnapshotResult) -> dict[str, Any]:
    """Turn a SnapshotResult into the `element`/`context`/`capture_meta`
    fields host.py attaches to an enriched click/shortcut event.
    """
    fields: dict[str, Any] = {}
    if result.element is not None:
        fields["element"] = _snapshot_to_dict(result.element)
    if result.context:
        fields["context"] = [
            {
                "role": c.role,
                "name": c.name,
                "automation_id": c.automation_id,
                "control_type": c.control_type,
                "text": c.text,
                "path_hash": c.path_hash,
            }
            for c in result.context
        ]
    # Always recorded (not just on degradation) so the Phase 1.3 latency
    # checkpoint can compute p95 end-to-end latency across every captured
    # action, not just the ones that happened to time out.
    fields["capture_meta"] = {
        "latency_ms": result.latency_ms,
        "dropped_before": None,
        "degraded_reason": result.degraded_reason,
        "hmac_key_generation": None,
    }
    return fields


# -- COM event handler shims -------------------------------------------------
# Each wraps a plain Python callback so uia_events.py's own methods (which
# need `self`) don't have to be COM interface implementations themselves.


class _FocusHandler(COMObject):
    _com_interfaces_ = [UIA.IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback: Callable[[Any], None]) -> None:
        super().__init__()
        self._callback = callback

    def IUIAutomationFocusChangedEventHandler_HandleFocusChangedEvent(self, sender: Any) -> int:
        with contextlib.suppress(Exception):
            self._callback(sender)
        return 0


class _PropertyChangedHandler(COMObject):
    _com_interfaces_ = [UIA.IUIAutomationPropertyChangedEventHandler]

    def __init__(self, callback: Callable[[Any, int, Any], None]) -> None:
        super().__init__()
        self._callback = callback

    def IUIAutomationPropertyChangedEventHandler_HandlePropertyChangedEvent(self, sender: Any, property_id: int, new_value: Any) -> int:
        with contextlib.suppress(Exception):
            self._callback(sender, property_id, new_value)
        return 0


class _StructureChangedHandler(COMObject):
    _com_interfaces_ = [UIA.IUIAutomationStructureChangedEventHandler]

    def __init__(self, callback: Callable[[Any, int, Any], None]) -> None:
        super().__init__()
        self._callback = callback

    def IUIAutomationStructureChangedEventHandler_HandleStructureChangedEvent(self, sender: Any, change_type: int, runtime_id: Any) -> int:
        with contextlib.suppress(Exception):
            self._callback(sender, change_type, runtime_id)
        return 0


class _AutomationEventHandler(COMObject):
    _com_interfaces_ = [UIA.IUIAutomationEventHandler]

    def __init__(self, callback: Callable[[Any, int], None]) -> None:
        super().__init__()
        self._callback = callback

    def IUIAutomationEventHandler_HandleAutomationEvent(self, sender: Any, event_id: int) -> int:
        with contextlib.suppress(Exception):
            self._callback(sender, event_id)
        return 0
