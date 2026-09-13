"""Phase 1.3 build steps 1-6: UIA element resolution and the context
snapshot -- the accessibility-tree read that turns "a click happened" into
"a click on this specific control, next to these specific on-screen
values."

Everything in this module assumes it runs on a thread that has already
called ``comtypes.CoInitialize()`` (an STA) -- COM interface pointers are
apartment-affine, and calling them from any other thread is undefined
behaviour that sometimes "works" and sometimes raises RPC_E_WRONG_THREAD.
Thread ownership lives in uia_events.py's UiaResolverThread; this module is
deliberately thread-agnostic code that *that* thread calls into.

Caching discipline (blueprint step 2): every property/pattern we ever read
is requested ONCE via a shared IUIAutomationCacheRequest, built here and
reused for every ElementFromHandleBuildCache / *BuildCache tree-walk call.
Microsoft's own docs are explicit that fetching properties one at a time is
a cross-process call per property; batching is not an optimisation here,
it is the difference between this being usable and not.

A comtypes-specific trap, found by testing this against a real running
fixture app rather than assuming: a COM out-parameter that is a NULL
element pointer (e.g. "this element has no parent / no children") comes
back from comtypes as a non-``None`` Python object wrapping a null
pointer -- ``is None`` never catches it, and touching any property on it
raises "NULL COM pointer access". Every tree-walk step below therefore
checks emptiness with plain truthiness (``if element:``), which comtypes'
POINTER types overload correctly, never with ``is None`` / ``is not None``.
"""

from __future__ import annotations

import ctypes
import hashlib
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any

import comtypes
import comtypes.client

# Generates comtypes.gen.UIAutomationClient from the registered typelib on
# first call in a process; safe to call repeatedly (comtypes caches it).
comtypes.client.GetModule("UIAutomationCore.dll")
import comtypes.gen.UIAutomationClient as UIA  # noqa: E402

user32 = ctypes.windll.user32
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
GA_ROOT = 2

# -- bounds of the context snapshot (Phase 1.3 build step 4) ----------------
MAX_CONTEXT_ELEMENTS = 12
MAX_CONTEXT_DEPTH = 3
MAX_CHARS_PER_ELEMENT = 512
SNAPSHOT_BUDGET_MS = 120.0

_CACHED_PROPERTY_IDS = (
    UIA.UIA_AutomationIdPropertyId,
    UIA.UIA_NamePropertyId,
    UIA.UIA_ControlTypePropertyId,
    UIA.UIA_ClassNamePropertyId,
    UIA.UIA_IsPasswordPropertyId,
    UIA.UIA_BoundingRectanglePropertyId,
    UIA.UIA_FrameworkIdPropertyId,
    UIA.UIA_LabeledByPropertyId,
)
_CACHED_PATTERN_IDS = (UIA.UIA_ValuePatternId, UIA.UIA_TextPatternId)

# UIA_XxxControlTypeId -> "Xxx", derived from the generated module so it
# can't drift from the constants actually in use (same discipline as
# schema.py deriving EVENT_TYPES from the JSON Schema).
_CONTROL_TYPE_NAMES: dict[int, str] = {
    value: name[len("UIA_") : -len("ControlTypeId")]
    for name, value in vars(UIA).items()
    if name.startswith("UIA_") and name.endswith("ControlTypeId") and isinstance(value, int)
}


def control_type_name(control_type_id: int | None) -> str | None:
    if control_type_id is None:
        return None
    return _CONTROL_TYPE_NAMES.get(control_type_id, str(control_type_id))


def _ok(element: Any) -> bool:
    """True if `element` is a live (non-null) COM element pointer. See the
    module docstring: comtypes null-element out-params are not Python
    ``None``, so this -- not ``is not None`` -- is the correct check.
    """
    try:
        return bool(element)
    except Exception:
        return False


def _safe(fn: Any) -> Any:
    try:
        return fn()
    except Exception:
        return None


@dataclass(slots=True)
class ElementSnapshot:
    automation_id: str | None
    name: str | None
    control_type: str | None
    class_name: str | None
    role: str | None
    is_password: bool
    framework_id: str | None
    bounds: dict[str, float] | None
    path_hash: str | None


@dataclass(slots=True)
class ContextItem:
    role: str  # "parent" | "labeled_by" | "sibling"
    name: str | None
    automation_id: str | None
    control_type: str | None
    text: str | None
    path_hash: str | None


@dataclass(slots=True)
class SnapshotResult:
    element: ElementSnapshot | None
    context: list[ContextItem] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
    latency_ms: float = 0.0


class UiaContext:
    """Holds the one IUIAutomation instance + cache request a resolver
    thread uses for its whole lifetime. Construct exactly once, on the STA
    thread that will make every subsequent call.
    """

    def __init__(self) -> None:
        self.uia = comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
        self.cache_request = self.uia.CreateCacheRequest()
        for pid in _CACHED_PROPERTY_IDS:
            self.cache_request.AddProperty(pid)
        for pid in _CACHED_PATTERN_IDS:
            self.cache_request.AddPattern(pid)
        self.walker = self.uia.RawViewWalker

    def element_from_hwnd(self, hwnd: int) -> Any | None:
        if not hwnd:
            return None
        try:
            elem = self.uia.ElementFromHandleBuildCache(hwnd, self.cache_request)
        except Exception:
            return None
        return elem if _ok(elem) else None

    def element_from_point(self, x: int, y: int) -> Any | None:
        try:
            pt = wintypes.POINT(x, y)
            elem = self.uia.ElementFromPointBuildCache(pt, self.cache_request)
        except Exception:
            return None
        return elem if _ok(elem) else None

    def focused_element(self) -> Any | None:
        try:
            elem = self.uia.GetFocusedElementBuildCache(self.cache_request)
        except Exception:
            return None
        return elem if _ok(elem) else None


def top_level_hwnd_for(hwnd: int) -> int:
    """Best-effort: the top-level ancestor of hwnd, or hwnd itself on
    failure. WinForms controls are each their own native HWND (unlike WPF),
    so this is meaningful for our fixture apps and most native Win32/
    WinForms surfaces; for surfaces where the focused element has no HWND
    at all, the caller falls back to the last-known foreground window.
    """
    if not hwnd:
        return hwnd
    try:
        root = user32.GetAncestor(hwnd, GA_ROOT)
        return root or hwnd
    except Exception:
        return hwnd


def _read_bounds(element: Any) -> dict[str, float] | None:
    # CachedBoundingRectangle comes back as a ctypes.wintypes.RECT struct
    # (left/top/right/bottom attributes), not a Python tuple -- confirmed
    # by inspecting a live value, not assumed.
    try:
        rect = element.CachedBoundingRectangle
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None
    return {"left": float(left), "top": float(top), "width": float(right - left), "height": float(bottom - top)}


def build_element_snapshot(element: Any, uia: Any, walker: Any, window_root_hwnd: int) -> ElementSnapshot:
    """Read the element's CACHED properties (already fetched in the
    element's own BuildCache call -- no per-property cross-process calls
    happen here) and compute its stable path_hash.
    """
    automation_id = _safe(lambda: element.CachedAutomationId) or None
    name = _safe(lambda: element.CachedName) or None
    control_type_id = _safe(lambda: element.CachedControlType)
    control_type = control_type_name(control_type_id)
    class_name = _safe(lambda: element.CachedClassName) or None
    is_password = bool(_safe(lambda: element.CachedIsPassword) or False)
    framework_id = _safe(lambda: element.CachedFrameworkId) or None
    bounds = _read_bounds(element)
    path_hash = compute_path_hash(element, uia, walker, window_root_hwnd)

    return ElementSnapshot(
        automation_id=automation_id,
        name=name,
        control_type=control_type,
        class_name=class_name,
        role=control_type,  # UIA has no separate ARIA-independent "role" for native controls; control_type IS the role here
        is_password=is_password,
        framework_id=framework_id,
        bounds=bounds,
        path_hash=path_hash,
    )


def compute_path_hash(element: Any, uia: Any, walker: Any, window_root_hwnd: int, max_depth: int = 30) -> str | None:
    """Stable identity per blueprint step 5: control-type path + AutomationIds
    from the window root down, falling back to Name + ordinal index where
    AutomationId is absent. Walks ancestors via the (uncached) RawViewWalker
    -- acceptable cost because this runs off the input hot path, on the
    resolver thread, same rationale as Phase 1.2's app-identity resolution.

    Stops at the element whose own HWND equals the window's top-level HWND
    (known already from Phase 1.2's SetWinEventHook attribution), or after
    max_depth steps as a hard safety cap against any COM tree-walk oddity.
    """
    if not _ok(element):
        return None
    parts: list[str] = []
    current = element
    depth = 0
    while _ok(current) and depth < max_depth:
        try:
            control_type = control_type_name(current.CurrentControlType) or "Unknown"
            automation_id = current.CurrentAutomationId or ""
            name = current.CurrentName or ""
            hwnd = current.CurrentNativeWindowHandle or 0
        except Exception:
            break

        if automation_id:
            parts.append(f"{control_type}:{automation_id}")
        else:
            idx = _sibling_ordinal(walker, current)
            parts.append(f"{control_type}:{name}#{idx}")

        if window_root_hwnd and hwnd == window_root_hwnd:
            break

        try:
            parent = walker.GetParentElement(current)
        except Exception:
            parent = None
        if not _ok(parent):
            break
        current = parent
        depth += 1

    if not parts:
        return None
    parts.reverse()
    digest = hashlib.sha256("/".join(parts).encode("utf-8", "replace")).hexdigest()
    return digest


def _sibling_ordinal(walker: Any, element: Any, max_scan: int = 64) -> int:
    """Ordinal index of `element` among its siblings -- the AutomationId
    fallback per blueprint step 5. Best-effort: a COM failure mid-scan
    yields whatever index was reached, never an exception the caller has
    to handle.
    """
    try:
        parent = walker.GetParentElement(element)
    except Exception:
        return 0
    if not _ok(parent):
        return 0
    idx = 0
    try:
        sib = walker.GetFirstChildElement(parent)
        count = 0
        while _ok(sib) and count < max_scan:
            try:
                same = (
                    sib.CurrentNativeWindowHandle == element.CurrentNativeWindowHandle
                    and sib.CurrentName == element.CurrentName
                )
            except Exception:
                same = False
            if same:
                return idx
            idx += 1
            count += 1
            try:
                sib = walker.GetNextSiblingElement(sib)
            except Exception:
                break
    except Exception:
        return idx
    return idx


def build_context_snapshot(
    element: Any,
    uia: Any,
    walker: Any,
    window_root_hwnd: int,
    max_elements: int = MAX_CONTEXT_ELEMENTS,
    max_chars: int = MAX_CHARS_PER_ELEMENT,
    budget_ms: float = SNAPSHOT_BUDGET_MS,
) -> tuple[list[ContextItem], bool, str | None]:
    """Phase 1.3 build step 4: the acting element's parent, its labelling
    element (LabeledBy), and up to `max_elements` sibling elements bearing
    text -- bounded by element count, depth, per-element character count,
    and a hard wall-clock budget. Returns (items, degraded, reason).
    """
    start = time.monotonic()
    items: list[ContextItem] = []
    degraded_reason: str | None = None

    def budget_left() -> bool:
        return (time.monotonic() - start) * 1000.0 < budget_ms

    parent = _safe(lambda: walker.GetParentElement(element))
    if _ok(parent) and budget_left():
        items.append(_context_item_from("parent", parent, max_chars))

    labeled_by = _safe(lambda: element.CachedLabeledBy)
    if _ok(labeled_by) and budget_left():
        items.append(_context_item_from("labeled_by", labeled_by, max_chars))

    if _ok(parent):
        sib = _safe(lambda: walker.GetFirstChildElement(parent))
        depth_elements_seen = 0
        while _ok(sib) and len(items) < max_elements and depth_elements_seen < max_elements * 4:
            depth_elements_seen += 1
            if not budget_left():
                degraded_reason = "snapshot_timeout"
                break
            try:
                same_as_acting = (
                    sib.CurrentNativeWindowHandle == element.CurrentNativeWindowHandle
                    and sib.CurrentName == element.CurrentName
                )
            except Exception:
                same_as_acting = False
            if not same_as_acting:
                text = _element_text(sib, max_chars)
                if text:
                    items.append(_context_item_from("sibling", sib, max_chars, text=text))
            try:
                sib = walker.GetNextSiblingElement(sib)
            except Exception:
                break

    if not budget_left() and degraded_reason is None:
        degraded_reason = "snapshot_timeout"

    return items[:max_elements], degraded_reason is not None, degraded_reason


def _element_text(element: Any, max_chars: int) -> str | None:
    # ValuePattern first, not Name: for an Edit control, CurrentName is
    # often just an inherited label association (e.g. a WinForms TextBox
    # picks up its neighbouring Label's text as its accessible name), while
    # ValuePattern.CurrentValue is the actual on-screen content -- which is
    # what the content-correctness checkpoint (Phase 1.3) and Stage 3's
    # linking evidence both need. Confirmed by testing against a real
    # fixture field: CurrentName returned the label text, not the typed
    # value, until this was reordered. Name is the right fallback for
    # controls with no ValuePattern at all (e.g. a Label or Button).
    value_pattern = get_value_pattern(element)
    if value_pattern is not None:
        val = _safe(lambda: value_pattern.CurrentValue)
        if val:
            return str(val)[:max_chars]
    name = _safe(lambda: element.CurrentName)
    if name:
        return str(name)[:max_chars]
    return None


def _context_item_from(role: str, element: Any, max_chars: int, text: str | None = None) -> ContextItem:
    return ContextItem(
        role=role,
        name=_safe(lambda: element.CurrentName) or None,
        automation_id=_safe(lambda: element.CurrentAutomationId) or None,
        control_type=control_type_name(_safe(lambda: element.CurrentControlType)),
        text=(text if text is not None else _element_text(element, max_chars)),
        path_hash=None,  # neighbourhood elements don't need their own identity hash for Stage 1's purposes
    )


def get_value_pattern(element: Any) -> Any | None:
    try:
        unk = element.GetCurrentPattern(UIA.UIA_ValuePatternId)
        if not _ok(unk):
            return None
        return unk.QueryInterface(UIA.IUIAutomationValuePattern)
    except Exception:
        return None


def get_text_pattern(element: Any) -> Any | None:
    try:
        unk = element.GetCurrentPattern(UIA.UIA_TextPatternId)
        if not _ok(unk):
            return None
        return unk.QueryInterface(UIA.IUIAutomationTextPattern)
    except Exception:
        return None
