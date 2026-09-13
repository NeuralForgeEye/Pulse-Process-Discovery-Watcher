# Stage 1 Blueprint — Continuous, wide-net capture (the "listening" layer)

**Source of truth:** `plans/pulse-architecture.md`, Stage 1.
**Cross-cutting controls:** `plans/platform-architecture.md` — **read this
too**; sensing provenance, HMAC-at-capture and environment abstraction are
defined there and are binding on every phase below.
**Research backing:** `research/stage-1-capture-layer.md`, and
`research/deployment-sensing-and-data-controls.md` (which supersedes parts of it).
**Status:** blueprint only — no implementation code has been written.
**Scope decision (mine, not the architecture's):** Windows 10/11 + Chromium
browsers for the structural sensing tiers. macOS and Linux are out of scope;
see §4.4.

> **Two decisions have changed this stage since it was first written:**
>
> 1. **Sensing is now tiered** (T1 accessibility → T2 DOM → T3 computer vision).
>    The CV tier exists only for surfaces with no structural layer — Citrix,
>    VDI, mainframe, canvas apps. It is specified in Phase 1.10 and **cannot be
>    validated outside the Wells Fargo environment**. Every captured value
>    carries its sensor and that sensor's confidence; values of different
>    provenance are **never merged**.
> 2. **OQ-1 is resolved.** Sensitive identifiers are hashed with a keyed HMAC
>    **at the point of capture**, not dual-written. Cleartext never enters the
>    pipeline. Phase 1.8 is rewritten accordingly.

Read both research logs before starting any phase. They contain the debates
behind every technical choice, what was verified versus recalled, and the open
items that need a human decision.

---

## 1. Stage goal

Stage 1 produces **one unbroken, ordered, machine-readable timeline of
everything meaningful a person did on their computer**, assembled from the
structured signals applications already emit — the same accessibility layer a
screen reader consumes — rather than from pixels. Each entry says what happened
(click, type, select, copy, paste, window switch, navigation), where it happened
(application, window, and the specific UI element, identified structurally), what
content was involved (the value typed or copied, and the text the surrounding
fields were displaying at that moment), and exactly when. Nothing downstream
works without this: Stage 2 can only find episode boundaries if the stream is
continuous and gap-free, and Stage 3 can only link applications together if the
capture retained the actual *values* that moved between them. Stage 1 is
therefore the stage where the project's leverage and its risk both concentrate —
**it is also, per the research log, the stage with the least novelty**, since
Paxray and KYP.ai already ship metadata-only capture commercially. Build it for
reliability and evidential quality, not for invention.

---

## 2. Phases

Nine phases. Each is sized to be built and validated in one working session.
They are ordered so that every phase has something real to test against as soon
as it lands.

> **Safety gate:** phases 1.2 through 1.7 capture real content with no redaction
> layer in place. Until **Phase 1.8** is complete and its checkpoint passes, the
> capture host runs **only against the synthetic fixture applications from Phase
> 1.2 and a dedicated dev browser profile** — never against a real user's
> machine, real credentials, or real customer data. This is not optional.

---

### Phase 1.1 — Event schema and the local event store

**Goal.** Define the one data contract every producer writes into and every
later stage reads from, plus a crash-safe local store. Nothing else in Stage 1
can be built until the shape of an event is fixed.

**Build steps**

1. **Read SmartRPA's event taxonomy first.** Pull `SmartRPA_events.pdf` from
   [github.com/bpm-diag/smartRPA](https://github.com/bpm-diag/smartRPA) and list
   its event types. Where their naming is sound, adopt it verbatim — it is MIT
   licensed and published, so matching it buys interoperability with existing
   research at no cost. Record in the research log which of their types we took,
   which we renamed, and why.
2. **Define the event record.** One flat record per event. Required fields:

   | Field | Type | Notes |
   |---|---|---|
   | `event_id` | UUIDv7 | time-ordered UUID, so id order ≈ time order |
   | `schema_version` | int | bump on any breaking change; store rejects unknown versions |
   | `producer` | enum | `desktop` \| `browser` \| `clipboard` |
   | `t_wall_utc` | int64 µs | wall clock, for human reading and cross-machine joins |
   | `t_mono_ns` | int64 | monotonic source, for **ordering** (never use wall clock to order) |
   | `session_id` | UUID | one capture-host run |
   | `actor_id` | string | pseudonymous, stable per machine+user; never the raw username |
   | `event_type` | enum | see step 3 |
   | `app` | object | `{process_name, pid, exe_path_hash, app_class}` |
   | `window` | object | `{hwnd_or_tab_id, title, url?, window_class?}` |
   | `element` | object | `{automation_id, name, control_type, role, framework, path_hash, bounds}` |
   | `content` | object | `{value_hmac?, value_readable?, class, redaction_state}` — see Phase 1.8. **No `value_raw` field exists for sensitive classes**; cleartext identifiers never enter the store |
   | `sensor` | object | `{tier: t1_uia \| t2_dom \| t3_cv, confidence, agreement: agree \| disagree \| single_sensor \| not_cross_checked, fallback_reason?}` — **mandatory on every value-bearing event** |
   | `context` | object | up to N sibling/label elements captured at action time (Phase 1.3), each carrying its own `sensor` |
   | `link_hint` | object | `{clipboard_seq?, pair_id?}` for copy/paste pairing (Phase 1.5) |
   | `capture_meta` | object | `{latency_ms, dropped_before, degraded_reason?, hmac_key_generation}` |

   **Schema-enforced rules** (reject at write time, not by convention):
   - a value classified `sensitive_identifier` **must** carry `value_hmac` and
     **must not** carry `value_readable`;
   - every value-bearing event **must** carry a populated `sensor` object;
   - `hmac_key_generation` is required so a key rotation doesn't silently
     orphan historical matches.

3. **Fix the event-type enum.** Minimum for Stage 1:
   `click`, `double_click`, `context_click`, `key_shortcut`, `field_value_changed`,
   `text_selected`, `clipboard_copy`, `clipboard_paste`, `focus_changed`,
   `window_activated`, `window_opened`, `window_closed`, `navigation`,
   `tab_activated`, `app_launched`, `app_exited`, `idle_start`, `idle_end`,
   `capture_degraded`. The last two categories matter as much as the first —
   Stage 2 needs idle boundaries, and honest degradation records are what keep
   Stage 3 from inventing links across blind spots.
4. **Write the schema as a versioned artifact,** not as code comments. Use JSON
   Schema (draft 2020-12) as the normative definition, and generate/hand-write
   matching Python dataclasses (or Pydantic models) from it. Rationale: three
   producers in two languages (Python host, JS extension) must agree, and a JSON
   Schema is the only artifact both can validate against.
5. **Build the store.** SQLite in WAL mode, one table `events` with the scalar
   fields as columns and the nested objects as JSON columns, plus indices on
   `(t_mono_ns)`, `(session_id, t_mono_ns)`, and `(event_type)`.
   - *Why SQLite over JSONL:* crash-safe under a hard power-off (WAL +
     `synchronous=NORMAL`), readable concurrently while the host is still
     writing, queryable without loading the day into memory, and present
     everywhere with no dependency.
   - *Why not XES or OCEL 2.0 at this layer:* both require a **case notion**,
     and deciding what a case is *is Stage 2's entire job*. Writing a case ID at
     capture time pre-judges segmentation and destroys the evidence Stage 2
     learns from. pm4py supports OCEL 2.0 (SQLite/XML/JSON), so converting later
     costs nothing. This debate is written out in full in the research log §5.4.
   - *Why not DuckDB as the live sink:* excellent for analysis, but it is not
     designed as a concurrent write-ahead transactional sink for a long-running
     process. Use it (or Parquet) for the **export** path instead.
6. **Build a writer with backpressure.** A bounded in-memory queue
   (`queue.Queue(maxsize=N)`) drained by a single writer thread batching inserts
   in transactions of ~100 events or 250 ms, whichever first. On queue-full,
   **drop and increment a counter, then emit a `capture_degraded` event** — never
   block a hook callback (a blocked low-level hook is removed by Windows and a
   blocked UIA callback stalls the provider application).
7. **Build the export path:** `events → Parquet` and `events → JSONL`, for
   downstream stages and for sharing fixtures.

**Expected output**

- `schema/pulse-event.v1.schema.json` — normative JSON Schema.
- `schema/README.md` — field-by-field semantics and the SmartRPA mapping table.
- A store module exposing `append(event)`, `read_range(t0, t1)`, `export_parquet()`.
- `pulse.db` created on first run with `schema_version` recorded in a `meta` table.

**Validation checkpoint**

- **Round-trip:** generate 10,000 synthetic events covering every `event_type`,
  write, read back, assert byte-identical field values and identical ordering by
  `t_mono_ns`. Pass = 10,000/10,000.
- **Schema enforcement:** feed 20 deliberately malformed events (missing
  required field, unknown `event_type`, wrong type, future `schema_version`).
  Pass = all 20 rejected with a specific error, zero written.
- **Crash safety:** write 50,000 events, `kill -9` the process mid-write, reopen.
  Pass = the database opens, is not corrupt, and loses at most one batch.
- **Throughput headroom:** sustained insert rate ≥ 2,000 events/s on the target
  machine. Real capture will produce orders of magnitude less; this proves the
  store is never the bottleneck.

---

### Phase 1.2 — Desktop action and window-context capture

**Goal.** Know *that* something happened and *where*: clicks, shortcut keys,
focus changes, window/application activation, app launch and exit — with correct
application attribution for every event. No content yet.

**Build steps**

1. **Input events — use Win32 low-level hooks** (`SetWindowsHookEx` with
   `WH_MOUSE_LL` and `WH_KEYBOARD_LL`), either directly via `ctypes` or through
   `pynput`, which wraps them.
   - *Versus Raw Input (`WM_INPUT`):* Raw Input is better for high-rate gaming
     input but gives device-level data without the windowing context we need,
     and does not integrate with the foreground-window notion as cleanly.
   - *Versus polling `GetAsyncKeyState`:* rejected outright — polling burns CPU
     continuously and still misses events.
   - **Critical constraint:** low-level hooks run on the installing thread and
     Windows removes hooks that take too long. The callback must do nothing but
     timestamp and enqueue. All resolution work happens on another thread.
   - **Content policy (decided in research log §5.3):** the keyboard hook
     records **shortcuts and timing only** — Ctrl+C/V/X/Z, Tab, Enter, Esc,
     function keys, and typing-burst boundaries/rates. It does **not** record
     typed characters. Typed content comes from UIA value-change events in Phase
     1.3, which also tells us which field the value belongs to and whether that
     field is a password field.
2. **Window and focus events — use `SetWinEventHook`** with
   `WINEVENT_OUTOFCONTEXT` and `idProcess = idThread = 0` (desktop-wide).
   Subscribe to at minimum `EVENT_SYSTEM_FOREGROUND`, `EVENT_OBJECT_FOCUS`,
   `EVENT_OBJECT_SHOW`, `EVENT_OBJECT_DESTROY`, `EVENT_SYSTEM_MINIMIZESTART/END`.
   - *Why out-of-context:* an in-context hook requires a DLL that Windows
     injects into every target process — a deployment and security nightmare and
     an instant red flag in any enterprise security review. Out-of-context
     delivers events cross-process to our own process with no injection, at the
     cost of asynchronous delivery (acceptable; ordering is handled in Phase 1.7).
   - Microsoft's own docs warn hook callbacks can re-enter before the previous
     invocation finishes. The callback must be re-entrancy safe: timestamp,
     enqueue, return.
   - This requires a **message pump** on a dedicated thread. Both
     `SetWindowsHookEx` and `SetWinEventHook` deliver via the thread's message
     queue.
3. **Resolve application identity off the hot path.** From the `hwnd`, get the
   PID (`GetWindowThreadProcessId`), then process name and executable path
   (`QueryFullProcessImageName` / `psutil`). Cache by PID with invalidation on
   `EVENT_OBJECT_DESTROY`, because these calls are not free and the same
   process recurs thousands of times.
4. **Idle detection.** `GetLastInputInfo` polled on a 1 s timer, or derived from
   the absence of input events. Emit `idle_start` / `idle_end` with a
   configurable threshold (default 60 s — Stage 2 will tune it; make it config,
   not a constant).
5. **Build the fixture applications now, not later.** Two small WinForms or WPF
   apps with known, stable control trees (`AutomationId` set on every control) —
   one playing "System A: record viewer", one playing "System B: lookup tool".
   These are the ground truth for every later phase and for the Stage 1
   acceptance harness. Without them every checkpoint below degrades to "looks
   about right".

**Reuse call.** Use `pynput` for input hooks (thin, maintained, saves ctypes
boilerplate) but write the `SetWinEventHook` layer directly via `ctypes` —
`pywinauto` and `uiautomation` both expose automation-oriented wrappers aimed at
*driving* the UI rather than *observing* it, and pulling in a large automation
framework for one hook registration is the wrong trade. Do not write a custom
input-hook layer; that problem is solved.

**Expected output**

- A capture host process that runs continuously and emits `click`,
  `key_shortcut`, `focus_changed`, `window_activated`, `window_opened`,
  `window_closed`, `app_launched`, `app_exited`, `idle_start`, `idle_end` into
  the Phase 1.1 store, each with correct `app` and `window` attribution.
- Two fixture applications with documented control trees, checked into the repo.

**Validation checkpoint**

- **Scripted ground truth:** drive a 50-action sequence across Notepad, File
  Explorer and both fixture apps using an automated driver (AutoHotkey script or
  `pywinauto` in *driving* mode — acceptable here because it is the test rig,
  not the product). The script writes its own ground-truth action list as it
  goes.
- Pass conditions, all four required:
  - ≥ 98% of ground-truth actions present in the captured log;
  - **100%** of foreground/application switches captured (a missed app switch
    corrupts attribution for every subsequent event, so this one is strict);
  - correct `app.process_name` on 100% of captured events;
  - zero typed characters anywhere in the store — grep the database for a
    sentinel string typed during the test (e.g. `ZZQXSENTINEL`) and assert **no
    match**. This is the guardrail for the no-keylogging decision.
- **Stability:** 30 minutes of continuous running under normal use, CPU < 3% of
  one core on average, no hook removal by the OS, no unbounded memory growth.

---

### Phase 1.3 — UIA element resolution and on-screen content snapshot

**Goal.** The heart of Stage 1 and the reason Pulse is not "just another click
logger": for each action, resolve the *specific UI element* involved and capture
the *text the surrounding screen was displaying at that moment* — from the
accessibility tree, never from pixels.

**Build steps**

1. **Choose the UIA client binding.** Options: raw `IUIAutomation` COM through
   `comtypes`; `uiautomation` (yinkaisheng) which wraps it; `pywinauto`
   `backend="uia"`; or FlaUI in C#.
   - **Recommendation: `comtypes` + a thin wrapper of our own, borrowing
     patterns from `uiautomation`.** We need caching and event subscription with
     exact control over what is fetched — the higher-level Python wrappers
     optimise for "find a control and click it", and their convenience property
     accessors trigger exactly the per-property cross-process calls that
     Microsoft's own documentation identifies as slow.
   - **FlaUI/C# is the documented fallback**, triggered by this phase's latency
     checkpoint failing. Do not pre-emptively move to C# — prove the need first.
2. **Use cached property batches, always.** Build one
   `IUIAutomationCacheRequest` containing exactly the properties we need
   (`Name`, `AutomationId`, `ControlType`, `ClassName`, `IsPassword`,
   `BoundingRectangle`, `FrameworkId`, plus `ValuePattern` and `TextPattern`),
   set `TreeScope` appropriately, and refresh with `BuildUpdatedCache`.
   Microsoft's caching documentation is explicit that retrieving properties one
   at a time requires a cross-process call per property and is slow; batching
   retrieves everything in a single call. **Do not fetch properties ad hoc.**
3. **Subscribe to UIA events**, not polling: `AutomationFocusChangedEvent`,
   `AutomationPropertyChangedEvent` on `ValuePattern.Value` (this is the typed
   value source decided in Phase 1.2), and `StructureChangedEvent` scoped
   narrowly. Microsoft's guidance: UIA improves performance by removing the need
   to poll, and scoping listening narrowly improves it further. Two hard
   constraints from the same docs: **never add or remove handlers from multiple
   threads**, and treat handler invocations as re-entrant — so the handler
   timestamps and enqueues, nothing more.
4. **Define the "context snapshot"** — the core capture decision of this phase.
   On each action event, capture the acting element plus a bounded neighbourhood:
   its parent, its labelling element (`LabeledBy` where present), and up to *N*
   sibling elements bearing text (default N = 12, configurable). **Bound it
   explicitly**: max elements, max depth (default 3), max characters per element
   (default 512), and a hard wall-clock budget (default 120 ms) after which the
   snapshot is truncated and `capture_meta.degraded_reason = "snapshot_timeout"`
   is set. An unbounded tree walk on a complex application will hang the capture
   host; the bound is not a nicety.
5. **Element identity that survives across sessions.** A raw runtime ID is
   useless later. Compute a stable `element.path_hash` from the control-type
   path plus `AutomationId`s from the window root down (falling back to `Name`
   and ordinal index where `AutomationId` is absent). Stage 4 needs to recognise
   "the same button in the same screen" across different people and different
   days — this hash is what makes that possible, so get it right here.
6. **Skip password fields, structurally.** If `IsPassword` is true, capture the
   element identity and emit `field_value_changed` with `content.value_raw =
   null` and `redaction_state = "password_field"`. Never read the value.
7. **Record degradation honestly.** When an application exposes nothing useful
   (no UIA provider, custom-drawn canvas, `FrameworkId` unknown), emit
   `capture_degraded` with the application and reason. The architecture's Stage 3
   step 3 explicitly demands honest gaps rather than forced links — this is where
   that honesty is actually manufactured.

**Reuse call.** Nothing off-the-shelf does this. SmartRPA logs UI actions but,
as far as the repo surfaces, does not do accessibility-tree *content
neighbourhood* snapshots; `pywinauto`/`uiautomation` are automation frameworks
that would fight our caching strategy; commercial tools that do it (KYP.ai,
Paxray) are closed, and Paxray deliberately does not capture content at all.
**This is a genuine build-custom, and it is the one place in Stage 1 where that
call is justified.**

**Expected output**

- Every action event now carries a populated `element` object and a `context`
  array of labelled on-screen text captured at action time.
- `field_value_changed` events carrying final field values with field identity.
- `capture_degraded` events wherever the accessibility layer gave us nothing.

**Validation checkpoint**

- **Correctness against fixtures:** using the Phase 1.2 fixture apps with 20
  known controls, click each one and assert the captured
  `(automation_id, name, control_type)` matches the documented control tree
  exactly. Pass = 20/20.
- **Content correctness:** set five fields in the fixture app to known sentinel
  values, click an unrelated button, and assert those five values appear in the
  `context` array of that click event **without the user ever having touched
  those fields**. This is the specific capability the architecture's Stage 1
  step 4 claims; if it fails, the claim is not real.
- **Password guardrail:** type a sentinel into the fixture's password field;
  assert it appears **nowhere** in the store.
- **Latency, the go/no-go gate:** measure end-to-end from input hook timestamp
  to a fully populated snapshot over a 5-minute scripted workload across the
  fixtures plus one real heavy application (Outlook or Excel).
  **Pass = p95 < 150 ms and zero dropped focus events.** On failure, invoke the
  documented fallback and move the desktop producer to C#/FlaUI — do not
  silently loosen the threshold.
- **Real-world coverage sample:** run against five real applications (Excel,
  Outlook, a WPF app, an Electron app such as Slack or Teams, and one internal
  line-of-business app if available). Record for each: does UIA expose a useful
  tree at all? Log the result in `/research/` — a coverage map is exactly the
  kind of evidence CLAUDE.md wants, including the negative results.

---

### Phase 1.4 — Text selection and highlight capture

**Goal.** Capture deliberate text selection as its own event type. The
architecture calls this out separately for good reason: a highlight is a strong,
intentional signal of attention, and it is Stage 3's second-strongest evidence
class for cross-application linking — weaker than copy/paste, stronger than mere
visibility.

**Build steps**

1. **Primary mechanism — UIA `TextPattern`.** Subscribe to
   `TextSelectionChangedEvent` (`UIA_Text_TextSelectionChangedEventId`); on fire,
   call `GetSelection()` on the element's `TextPattern` to obtain the selected
   `TextRange` and its text. This is the right mechanism because it gives the
   selected *text* plus the *element it came from* — both needed by Stage 3.
2. **Fallback for controls without `TextPattern`.** A mouse-drag heuristic:
   mouse-down, movement beyond a threshold, mouse-up within a text-bearing
   element, then attempt `ValuePattern`/`TextPattern` read. Mark these events
   `content.source = "inferred_selection"` so Stage 3 can weight them lower.
   **Do not let inferred selections masquerade as observed ones** — the evidence
   ranking in Stage 3 is only as honest as this field.
3. **Handle selection churn.** Dragging fires a stream of selection-changed
   events. Debounce: emit one `text_selected` event on selection *settle*
   (default 300 ms of stability), carrying the final range. Store the debounce
   window in config; Stage 2 may care about selection duration later.
4. **Browser selections are out of scope here** — they are handled natively by
   the extension in Phase 1.6 via `selectionchange`, which is both cheaper and
   more accurate than UIA over Chrome.

**Reuse call.** Build custom — this is a thin layer on the Phase 1.3 UIA client
we already own. No library wraps `TextSelectionChangedEvent` usefully.

**Expected output**

- `text_selected` events with `{selected_text, element, source: "uia_textpattern"
  | "inferred_selection", duration_ms}`.

**Validation checkpoint**

- In Notepad, WordPad, Excel and the fixture app, select 10 known strings by
  mouse drag and 10 by keyboard (Shift+arrows, Ctrl+A). Pass = ≥ 18/20 captured
  with the **exact** selected string, per application; any application scoring
  below that gets a documented entry in the coverage map rather than a silent
  failure.
- **No-churn check:** a single 3-second drag-select produces exactly **one**
  `text_selected` event, not a stream.
- **Source honesty:** every event captured via the drag heuristic is labelled
  `inferred_selection`. Assert zero mislabelled events.

---

### Phase 1.5 — Clipboard capture and copy/paste pairing

**Goal.** Capture copy and paste as *linked* events carrying the actual value —
the strongest evidence class in Stage 3's ranking, and the one thing Paxray
explicitly refuses to do (it detects that Ctrl+C happened, never what was
copied). This is where Pulse diverges from the closest prior art.

**Build steps**

1. **Use `AddClipboardFormatListener`**, not polling. Create a message-only
   window, register it, and handle `WM_CLIPBOARDUPDATE`.
   - *Versus polling `pyperclip`/`GetClipboardData` on a timer:* polling burns
     CPU continuously, misses fast successive copies, and races with other
     clipboard users. The listener API exists precisely to avoid this.
   - *Versus `SetClipboardViewer` (legacy chain):* deprecated and fragile — one
     misbehaving application in the chain breaks notification for everyone.
2. **Read robustly.** `OpenClipboard` can legitimately fail immediately after
   `WM_CLIPBOARDUPDATE` because another process holds it open. Implement a
   bounded retry (e.g. 5 attempts, 20 ms apart) and, on exhaustion, emit the
   copy event with `content.value_raw = null` and `degraded_reason =
   "clipboard_locked"` rather than dropping the event — Stage 3 still benefits
   from knowing a copy occurred.
3. **Use `GetClipboardSequenceNumber`** as the clipboard's own version counter.
   Store it in `link_hint.clipboard_seq`. This is what makes pairing reliable:
   a paste is matched to the copy whose sequence number was current at paste
   time, rather than to "whatever was copied most recently in wall-clock terms".
4. **Detect paste.** Windows gives no paste notification. Combine two signals:
   the Ctrl+V shortcut from the Phase 1.2 keyboard hook (plus Shift+Insert and
   context-menu Paste clicks), and a `field_value_changed` from Phase 1.3 whose
   new value contains the current clipboard content. Emit `clipboard_paste` with
   `link_hint.pair_id` referencing the originating copy event.
   - Rank the pairing evidence in the event itself: `pair_confidence =
     "shortcut_and_value_match"` > `"value_match_only"` > `"shortcut_only"`.
     Stage 3's evidence ranking depends on this distinction existing at capture
     time; it cannot be reconstructed later.
5. **Capture format metadata:** which clipboard formats were present
   (`CF_UNICODETEXT`, `CF_HTML`, files, image). Capture **text formats only** for
   v1; for images/files record only that the format was present, never the
   payload.
6. **Cross-machine/RDP caveat:** clipboard redirection over RDP or Citrix may
   produce copies with no observable source application. Emit these with an
   explicit `degraded_reason = "clipboard_source_unknown"` — see the VDI risk in §4.3.

**Reuse call.** Use `pywin32` for the Win32 clipboard calls (mature, saves
considerable `ctypes` marshalling for clipboard formats), but write the pairing
logic custom — no library does copy/paste *pairing with confidence ranking*,
and that ranking is exactly what Stage 3 consumes.

**Expected output**

- `clipboard_copy` events with the copied value, source element, and sequence
  number.
- `clipboard_paste` events with `pair_id`, destination element, and
  `pair_confidence`.

**Validation checkpoint**

- **Pairing accuracy:** a scripted sequence of 30 copy/paste operations across
  the two fixture apps, Notepad and Excel, including three deliberate traps:
  (a) copy, copy again, then paste — must pair to the **second** copy;
  (b) copy then paste **three times** — must produce three pastes all pairing to
  the one copy; (c) copy in App A, switch app, paste in App B — must pair
  across the application boundary. Pass = ≥ 29/30 correctly paired, and **all
  three traps** handled correctly.
- **Fidelity:** copied value in the log is byte-identical to the source string
  for all 30, including one string with unicode, one with a newline, and one of
  4,000 characters.
- **No-poll proof:** with the capture host running idle for 10 minutes and no
  clipboard activity, assert zero clipboard reads occurred (instrument the read
  path with a counter).

---

### Phase 1.6 — Browser capture via a Chrome MV3 extension

**Goal.** Capture the same five signal classes inside Chromium browsers, where
most QA/QC work actually happens, **without** switching Chrome into its
high-CPU accessibility mode.

**Why an extension and not OS-level UIA** (full debate in research log §5.1):
driving Chrome through UIA requires `--force-renderer-accessibility`, which Blue
Prism's integration guide warns "can result in high CPU overhead" and which a
Salesforce support article ties to *unresponsive pages*, because accessibility
mode continually updates across all browser processes. A continuous-capture tool
that makes every tab sluggish will be uninstalled. **Why not CDP:** attaching the
debugger either shows a permanent debugging banner or requires an open remote
debugging port, which is a real security exposure on an employee machine.

**Build steps**

1. **Scaffold an MV3 extension:** `manifest_version: 3`, a service worker, a
   content script injected at `document_idle` on all frames, permissions
   `activeTab`/`scripting`/`tabs`/`nativeMessaging`, plus host permissions
   governed by an enterprise-policy allow-list (Phase 1.8).
2. **Content script captures**, all natively and cheaply:
   - clicks (capture-phase listener) with a DOM path + accessible name for the
     target — compute the accessible name using the ARIA/HTML accname rules
     (`aria-label`, `<label for>`, `aria-labelledby`, placeholder, text content)
     so browser element identity is semantically comparable to desktop UIA
     `Name`. **This comparability is what lets Stage 3 match a field in App A to
     a field in App B.**
   - `selectionchange`, debounced on settle → `text_selected`;
   - `copy` / `paste` events — these give real `clipboardData`, which is both
     more reliable and cheaper than the OS path;
   - `input`/`change` on form fields → `field_value_changed`, skipping
     `type="password"` structurally;
   - visible field content at action time → the `context` array: nearest form,
     its labelled fields and their values, bounded exactly as in Phase 1.3;
   - navigation: `history.pushState`/`replaceState` patching plus
     `popstate`/`hashchange` for SPA route changes, which `webNavigation` alone
     misses. SPA route changes are frequently the real "screen change" in modern
     line-of-business apps, so do not rely on page loads.
3. **Service worker relays to the native host.** MV3 service workers are evicted
   after roughly 30 s idle, so the worker must not be the buffer.
   - **Test empirically whether a long-lived `chrome.runtime.connectNative` port
     keeps the worker alive** — this is widely believed but was **not verified**
     during research. If it does not hold: fall back to an **offscreen document**
     (designed for exactly this), and if that also fails, buffer in the content
     script's `IndexedDB` and flush opportunistically.
   - Respect the documented native-messaging limits: JSON UTF-8 with a 32-bit
     native-byte-order length prefix; **1 MB max per message from host to
     extension**. Batch and chunk accordingly.
4. **Native messaging host** registered by manifest in the Windows registry,
   receiving batches and writing them into the Phase 1.1 store with
   `producer = "browser"`.
5. **Clock alignment:** the extension stamps `performance.timeOrigin +
   performance.now()`; the native host records its own receipt time. Phase 1.7
   reconciles them. Never order browser events by their arrival time at the host.
6. **Firefox/Edge:** Edge is Chromium and should work with the same package;
   Firefox is a port, explicitly out of v1 scope.

**Reuse call.** SmartRPA ships its own Chrome/Firefox/Edge/Opera extensions
(MIT) — **read them first**; their event surface is a free checklist and may be
partly liftable. Do **not** use **rrweb**: it optimises for pixel-faithful DOM
replay, storing full DOM snapshots plus mutation streams, which reintroduces
exactly the heavyweight "recording" data profile Pulse exists to avoid. Borrow
its *masking conventions* (`data-*` ignore attributes, input blocking) for Phase
1.8 and nothing else.

**Expected output**

- An unpacked MV3 extension plus a registered native messaging host.
- Browser events flowing into the same store, schema-identical to desktop events.

**Validation checkpoint**

- **Parity test:** build a static test page with a form, a table, and an SPA
  route change. Perform 30 scripted actions (clicks, typing, selection, copy,
  paste, navigation). Pass = ≥ 95% captured with correct accessible names and
  correct URLs.
- **Cross-producer copy/paste:** copy a value in a desktop fixture app, paste it
  into the browser test page, and vice versa. Both directions must produce a
  correctly paired copy/paste across producers. **This is the single most
  important test in Stage 1** — it is the capability Stage 3 is built on, and it
  is the first point where the whole architecture is either real or not.
- **Survival test:** leave the browser idle for 10 minutes, then act. Pass = the
  action is captured (proves the service-worker lifetime solution actually works
  rather than being assumed).
- **Overhead:** measure page load and interaction latency on a heavy real
  application with the extension on vs. off. Pass = < 5% regression, and
  crucially, `chrome://accessibility` shows accessibility mode **off** — proving
  we did not accidentally reintroduce the cost we designed around.
- **Password guardrail:** sentinel typed into a `type="password"` field appears
  nowhere in the store.

---

### Phase 1.7 — Unified timeline: clock discipline, ordering, and session assembly

**Goal.** Turn three independent, asynchronous producers into **one unbroken
ordered timeline per person per session** — the literal deliverable of the
architecture's Stage 1 checkpoint.

**Build steps**

1. **One monotonic anchor.** At host start, record a single
   `(wall_utc, mono_ns)` pair and derive every producer's timestamps into that
   frame. Wall clock alone is unusable for ordering: NTP corrections and DST can
   move it backwards mid-session.
2. **Reconcile the browser's clock.** The extension's `timeOrigin + now()` lives
   in a different frame. Estimate offset with a periodic ping/pong through the
   native messaging port (measure round-trip, take the minimum-RTT sample as the
   best offset estimate — a simplified NTP/Cristian approach). Re-estimate every
   60 s and store the offset used with each batch, so the correction is auditable
   rather than silently applied.
3. **Bounded reorder buffer.** Events arrive out of order because
   `WINEVENT_OUTOFCONTEXT` delivery is asynchronous, the browser batches, and
   the UIA snapshot adds latency. Hold events in a small ordered buffer
   (default 2 s, configurable) before committing them as final order. Any event
   arriving later than the window is committed anyway and flagged
   `capture_meta.late_arrival = true` — never dropped, and never silently
   reordered after the fact.
4. **Session and actor assembly.** A session spans one capture-host run;
   emit explicit `session_start` / `session_end`, and on unclean shutdown mark
   the session `incomplete`. `actor_id` is a salted hash of machine + user SID,
   never a raw username.
5. **Gap accounting — the key deliverable for Stage 2.** Produce a per-session
   gap ledger: every interval > threshold with no events, classified as
   `idle` (the user was away — corroborated by `GetLastInputInfo`),
   `blind` (input occurred but capture produced nothing, e.g. an app with no
   accessibility tree), or `host_down` (the capture host was not running).
   Stage 2 treats idle gaps as possible episode boundaries and blind gaps as
   *missing evidence*; conflating them would make Stage 2 invent boundaries
   where the tool merely went deaf. This distinction is worth more to the rest
   of the system than any other output of this phase.
6. **Timeline API:** `get_timeline(actor, t0, t1) -> ordered events + gap ledger`.

**Reuse call.** Build custom, but it is small — this is standard distributed
log-merge work (offset estimation + bounded reorder buffer), not novel. Do not
pull in a stream-processing framework for three local producers; the operational
cost would dwarf the problem.

**Expected output**

- `timeline` module producing a single ordered event sequence across all three
  producers plus a classified gap ledger.
- Per-session summary: event counts by producer and type, gap ledger, clock
  offset history, degradation counts.

**Validation checkpoint**

- **Interleaving correctness:** scripted alternating actions across desktop and
  browser at ~1 s intervals for 5 minutes, with independently recorded ground
  truth. Pass = **100%** correct relative ordering of cross-producer event pairs
  whose true separation is > 500 ms, and ≥ 95% for pairs separated by 100–500 ms.
- **Clock robustness:** change the system clock by +10 minutes mid-capture.
  Pass = event ordering is unaffected (proves ordering really is monotonic-based).
- **Gap classification:** deliberately produce one of each gap type — walk away
  for 3 minutes (`idle`), interact for 2 minutes with an application known to
  expose no accessibility tree (`blind`, e.g. a canvas-rendered app or a remote
  desktop window), and kill the host for 2 minutes (`host_down`). Pass = all
  three correctly classified, zero misclassifications.

---

### Phase 1.8 — Privacy, redaction, and retention policy

**Goal.** Make continuous content capture defensible enough to run on a real
person's machine. **This phase is the gate that unlocks real-world capture** —
everything before it is fixture-only.

**Build steps**

1. **Application and site allow/deny lists,** enforced *before* content capture,
   not after. Default-deny content capture for: password managers, banking
   sites, HR/payroll systems, personal webmail, messaging apps. On a denied
   target, still record that an application was used and for how long (that is
   useful process context and is low-sensitivity), but capture no content and no
   element text. Paxray ships exactly this whitelist/blacklist model; matching it
   is table stakes for enterprise deployment, not innovation.
2. **Field-class policy.** Classify each captured field into
   `identifier_like` (matches configured ID patterns — loan IDs, ECN numbers,
   ticket IDs), `ui_chrome` (button labels, screen titles, column headers — not
   user data), `free_text`, or `sensitive`. **Policy differs by class**, which is
   the whole point:
   - `ui_chrome` → retain in clear. Stage 5 needs this on-screen language and it
     carries essentially no privacy risk.
   - `identifier_like` → retain per the §4.1 decision (dual-write, see below).
   - `free_text` → run through redaction; retain the redacted form.
   - `sensitive` → never retained.
3. **Redaction:** use **Microsoft Presidio** (MIT, analyzer + anonymizer,
   NER + regex + checksum with context) for free-text PII. Do not hand-roll PII
   detection — Presidio is maintained, covers credit cards, SSNs, phone numbers,
   names and locations, and supports custom recognisers for domain identifiers.
   **Run it in the writer pipeline, never in a hook callback** — it is
   spaCy-backed and far too slow for a hot path.
4. **Keyed HMAC at the point of capture — decided, replacing the earlier
   dual-write proposal.** For every `identifier_like` value, compute
   `content.value_hmac = HMAC-SHA256(key, normalise(value))` **inside the
   capture host, before the event reaches the store**. The key comes from the
   internal Vault through the `SecretsProvider` interface
   (`plans/platform-architecture.md` §4.1) — never hardcoded, never derived
   from the hostname.
   - **Normalise before hashing** (case-fold, strip separators and whitespace,
     optionally strip a known prefix) so `LN-00123`, `ln 00123` and `LN00123`
     produce one hash.
   - **Also hash token components** (`LN` + `00123`) so a bare `00123`
     appearing elsewhere can still match. This partially recovers the substring
     matching that hashing otherwise destroys.
   - **Stamp `capture_meta.hmac_key_generation`.** A key rotation changes every
     hash; without the generation stamp, historical data silently stops
     matching new data at the first rotation.
   - **Why this is stronger than the dual-write design it replaces:** dual-write
     kept a cleartext path alive inside the pipeline, so the whole pipeline had
     to be trusted. Hashing at capture means cleartext identifiers never enter
     it, making the security argument structural rather than procedural.
   - **What it costs, recorded plainly:** edit-distance/fuzzy matching between
     near-miss identifiers becomes impossible. Normalisation and token hashing
     cover the common cases. If a real corpus later shows significant unmatched
     near-miss identifiers, **escalate it — do not quietly reintroduce
     cleartext.**
5. **Reversal vault, off the main path.** A separate, narrowly-scoped, fully
   audited store mapping hash → encrypted real value, for the rare case a human
   reviewer must see a real value behind a flagged episode. Different service,
   different credentials, different network path; access requires an
   authenticated identity and a stated reason, and emits an audit record.
   **Not reachable from the main pipeline.** If it is being used routinely,
   something upstream is wrong.
5. **Retention and deletion:** configurable TTL on raw values (default:
   aggressive, e.g. 7 days) separate from TTL on events (long). Implement
   `purge(actor, t0, t1)` and a working subject-erasure path now, while the
   store is simple — retrofitting deletion into a system with derived artifacts
   downstream is far harder later.
6. **Transparency surface:** a local "what has been captured about me" viewer
   and a visible, reliable pause control. Beyond ethics, this is what makes the
   difference between a deployable tool and one a works council blocks.

**Reuse call.** Presidio: **reuse directly** — mature, MIT, actively developed,
exactly the right scope, and building PII detection is a bad use of this
project's effort. Policy engine, vault and purge: **custom**, but small and
specific to our schema.

**Expected output**

- `policy.yaml` — allow/deny lists, field-class patterns, retention TTLs, and
  the `retain_raw_identifiers` switch.
- A redaction stage in the writer pipeline.
- Encrypted value vault + `purge()` + a local transparency viewer.
- A short written statement of exactly what is captured and what is not — the
  thing a security reviewer or works council will actually ask for.

**Validation checkpoint**

- **Deny-list enforcement:** with a banking site and a password manager on the
  deny list, interact with both for 2 minutes. Pass = **zero** content or
  element-text events from either; application-usage events still present.
- **Redaction recall:** seed a fixture form with 50 synthetic PII values (names,
  SSNs, card numbers, emails, phone numbers — synthetic, never real). Pass =
  ≥ 95% redacted, **100% for structured high-risk types** (card numbers, SSNs),
  and every miss written up in the research log rather than quietly tolerated.
- **Hash linkability:** with `retain_raw_identifiers = off`, assert the same
  identifier copied in App A and typed in App B produces the **same**
  `value_hash`, and that the raw value appears nowhere in the store.
  This is the proof that the privacy-preserving mode still supports Stage 3.
- **Purge:** run `purge(actor, t0, t1)`, then assert zero matching rows remain
  in the store, the vault, **and** any exported Parquet in the export directory.

---

### Phase 1.9 — Stage 1 acceptance: the multi-application continuity test

**Goal.** Prove the architecture's Stage 1 checkpoint verbatim: *for one person
working continuously across multiple applications, produce one unbroken, ordered
timeline of everything meaningful they did, with no gaps and no reliance on
watching the screen.*

**Build steps**

1. **Write a realistic scenario script.** A ~30-minute QA/QC-shaped workflow:
   open a record in fixture App A, read a reference ID, search that ID in a
   browser-based system, copy a value back, open Excel, check a figure, record a
   decision (approve/reject) in App A. Repeat with variations: interruptions, a
   phone-call idle gap, a mistake and correction, a case abandoned midway. The
   variations matter more than the happy path — Stage 2 and Stage 4 exist to
   handle exactly those.
2. **Produce independent ground truth.** A human (or a driver script) records
   the intended action list with timestamps, separately from the capture host.
   Without independent ground truth this checkpoint is self-graded and worthless.
3. **Run the capture host end to end** with all three producers and Phase 1.8
   policy active.
4. **Compute acceptance metrics** and write them up:
   - **Coverage:** % of ground-truth actions present.
   - **Attribution accuracy:** % with correct application/window.
   - **Element resolution rate:** % of action events with a resolved element.
   - **Content capture rate:** % of ground-truth on-screen values that appear in
     a `context` snapshot.
   - **Copy/paste pairing accuracy**, cross-application specifically.
   - **Ordering accuracy** against ground truth.
   - **Gap ledger honesty:** every real gap classified correctly, with `blind`
     regions matching the applications known to lack accessibility support.
   - **Resource cost:** mean and p95 CPU, memory, and bytes/hour written.
5. **Publish a coverage map** in `/research/`: per application, what Pulse can
   and cannot see. This becomes a standing artifact — Stage 3 and Stage 4 both
   need to know where the blind spots are, and it is the honest answer to "does
   this actually work?"

**Expected output**

- `research/stage-1-acceptance.md` — full metric table, pass/fail per
  criterion, and the application coverage map.
- A checked-in sample capture dataset from the scenario run, which becomes the
  **fixture input for Stage 2's segmentation work** — Stage 2 should not have to
  generate its own data.

**Validation checkpoint (Stage 1 exit criteria)**

Stage 1 is **done** when all of these hold on the 30-minute scenario:

| Metric | Threshold |
|---|---|
| Action coverage | ≥ 95% of ground-truth actions |
| Application attribution | 100% |
| Element resolution | ≥ 90% of action events |
| On-screen value capture | ≥ 85% of ground-truth visible values |
| Cross-application copy/paste pairing | ≥ 95% |
| Ordering accuracy (> 500 ms separation) | 100% |
| Unexplained gaps (not in the ledger) | 0 |
| Mean CPU | < 5% of one core |
| Storage | < 100 MB/day/user pre-compression |

Any metric missing its threshold is written up with a diagnosis before Stage 2
starts. **Do not proceed on "close enough"** — Stage 2 and Stage 3 both amplify
capture defects rather than absorbing them, so an 80%-coverage timeline does not
produce an 80%-correct process map; it produces a confidently wrong one.

---

### Phase 1.10 — Sensing arbitration and the computer-vision tier

**Goal.** Extend capture to surfaces that expose no structural layer — Citrix,
VDI, mainframe terminals, canvas-rendered applications — without degrading the
exactness of everything else.

> **Sequencing note.** Build this **last**, and only after Phase 1.9's coverage
> map has measured how much real work the structural tiers actually reach. If
> T1/T2 cover well over 90% of target activity, this tier becomes a
> low-priority option rather than a core component, and the project gets
> cheaper and simpler. **Measure before building.**

**Build steps**

1. **Define the `Sensor` interface** (per `plans/platform-architecture.md` §4.1)
   with T1 (UIA), T2 (DOM) and T3 (CV) implementations behind it. Every tier
   returns the same shape: element identity, value, and a populated `sensor`
   object. Downstream code must not know which tier answered.
2. **Build the arbitration policy.** Per application-surface signature: probe
   structural availability; if a usable element tree exists, **use it and do not
   run CV** — CV costs orders of magnitude more compute for a worse value. Cache
   the decision per surface; re-probe when Stage 7 Phase 7.2 reports a
   capture-health change, because an application update can change availability
   in either direction.
3. **Record the fallback and its reason** on every T3-sourced value. A silent
   fallback is indistinguishable from a structural read in the data, which is
   exactly what the provenance rule exists to prevent.
4. **Implement the CV tier.** Screen-region capture plus text recognition and
   visual element detection, scoped to the focused window. Specific engine
   choice is deferred: **the honest position is that no engine should be
   selected until it can be benchmarked against real target surfaces**, since
   mainframe terminal text, Citrix-compressed screens and modern web canvases
   have very different recognition characteristics. Name candidates, benchmark,
   then choose.
5. **Cross-validation sampling.** Where a surface supports both a structural
   tier and CV, run both **periodically as a calibration sample** — not
   continuously. This yields a measured estimate of T3's real accuracy *on this
   bank's actual screens* rather than a vendor benchmark. Low default sample
   rate.
6. **Disagreement handling.** When two tiers observe the same identifier and
   disagree, emit **both readings with the disagreement flagged**. Never emit a
   single reconciled value. An averaged or arbitrated-away value is a fabricated
   value, and it would silently corrupt every Stage 3 link built on it.
7. **Apply the same data controls.** CV-extracted identifiers are hashed at
   capture exactly like structural ones (Phase 1.8); CV-extracted structural text
   stays readable. **Do not retain the captured screen region** beyond what
   recognition requires — retaining it would reintroduce the screenshot data
   profile this architecture avoids everywhere else.

**Reuse call.** Reuse an established OCR/vision stack rather than building
recognition from scratch — this is solved science and building it would be
indefensible. **Selection deferred to benchmark**, per step 4.

**Expected output.** A `Sensor` interface with three implementations; an
arbitration policy with a per-surface decision cache; calibration-sample
results; CV-sourced events carrying full provenance.

**Validation checkpoint**

- **Arbitration correctness:** on a surface with a healthy UIA tree, CV **never
  runs**. Instrument and assert zero CV invocations. (Cost control and a
  correctness property both.)
- **Provenance survival:** a CV-sourced value is still identifiable as `t3_cv`
  in Stage 6's output. Trace one end to end.
- **Disagreement test:** force a mismatch between a structural read and a CV
  read of the same field. The system emits both with a disagreement flag and
  **no merged value**. Automated, zero tolerance.
- **Accuracy, measured not assumed:** CV tier character/field accuracy on real
  target surfaces, reported **per surface type**, never blended with structural
  accuracy into one figure.
- **Untested-status honesty:** until the above runs against real Citrix/
  mainframe surfaces inside the bank, every status report states this tier is
  **unvalidated**.

---

## 3. Dependencies

**Needs from previous stages.** Nothing technical. Stage 0 is conceptual, and
its framing claim ("a sensing method no one else in our space is using") is
**contradicted by the prior-art findings** — see §4.2 and research log §6.

**Hands off to Stage 2 (episode segmentation):**

1. **The ordered timeline** — `get_timeline(actor, t0, t1)`, one row per event
   in committed order.
2. **The gap ledger**, with `idle` / `blind` / `host_down` distinguished. Stage 2
   treats idle gaps as candidate episode boundaries; it must **not** treat blind
   gaps the same way, or it will invent boundaries where the tool merely went
   deaf.
3. **Identifier-bearing content** — `content.value_hash` on every
   `identifier_like` value, so Stage 2 can detect "a brand-new identifier
   appeared on screen for the first time", its primary start-of-case signal per
   the architecture.
4. **Terminal-action signals** — `ui_chrome` text retained in clear, so Stage 2
   can find "Approve", "Reject", "Submit" as end-of-case signals.
5. **Stable element identity** (`element.path_hash`), so Stage 4 can recognise
   the same screen across people and days.
6. **A checked-in sample capture** from Phase 1.9 for Stage 2 to develop against.

**Anti-handoff — deliberately withheld.** Stage 1 does **not** assign case IDs,
episode boundaries, or XES/OCEL structure. That is Stage 2's job, and doing it
at capture time would destroy the evidence Stage 2 needs (research log §5.4).

---

## 4. Open questions and risks

Ordered by how much damage each does if it turns out badly.

### 4.1 Raw values vs. hashes — **RESOLVED**

**Decision: keyed HMAC at the point of capture**, key from the internal Vault,
normalised before hashing, with token-component hashing to recover common
substring cases, plus a separate audited reversal vault off the main pipeline.
Structural text (field names, button labels, screen titles) stays **readable** —
Stages 4 and 5 must read it, and hashing it would buy no security while breaking
event abstraction and process-type labelling.

Stronger than the dual-write design originally proposed here, because cleartext
identifiers never enter the pipeline at all — the security argument becomes
structural rather than procedural. Implemented in Phase 1.8 steps 4–5; rationale
in `research/deployment-sensing-and-data-controls.md` §5.3.

**Residual risk:** edit-distance matching between near-miss identifier variants
is lost. Normalisation and token hashing cover the common cases. If a real
corpus shows this matters, **escalate — do not quietly reintroduce cleartext.**

### 4.2 Stage 1 is not novel, and the architecture overstates it

Paxray states plainly that it captures only technical interactions and never
content; KYP.ai states it captures keyboard, mouse, clipboard and application
interactions continuously with no screenshots and on-device anonymisation. The
architecture's "no one else in our space is using this sensing method" is **not
supportable as written**. What is plausibly distinctive is narrower and lives
downstream: *retaining the copied/displayed value and using value identity as
cross-application linking evidence* — the thing Paxray deliberately refuses to
do. Per CLAUDE.md's "be suspicious of 'just apply AI to X'" test, this passes
(it is a capture-and-linking mechanism, not an LLM wrapper), but it only pays
off at **Stage 3**. Someone should decide whether to soften the architecture's
wording or re-point the claim.

### 4.3 Citrix / VDI blind spot — **RESOLVED by adopting tiered sensing**

In a Citrix or equivalent virtualised session the client receives screen
updates, not UI objects, so no accessibility layer exists client-side. SKAN's
product documentation explicitly claims coverage of "legacy systems, mainframes,
Citrix and VDI environments... and even tools with no API or event log" — so
this was not merely a risk for us, it was **a capability the main competitor
already advertises**.

**Decision: hybrid, metadata-first sensing.** Structural tiers (T1 accessibility,
T2 DOM) wherever they exist; a **computer vision tier (T3) only** on surfaces
with no structural layer. Specified in Phase 1.10 and
`plans/platform-architecture.md` §2.

**Two residual risks, both real:**

1. **The T3 tier cannot be validated outside the Wells Fargo environment** — the
   Citrix, VDI and mainframe surfaces it exists to read aren't available on a
   development machine. It must be flagged as untested in every status report
   and **never demonstrated as proven** until it has run against real surfaces.
2. **Where CV inference runs** (endpoint vs. central) is unresolved and drives
   endpoint footprint — the main objection an enterprise desktop team will
   raise. Tracked as PA-4 in `plans/platform-architecture.md`.

### 4.4 Windows-only scoping

My judgment call, not the architecture's. macOS (`AXUIElement`) and Linux
(AT-SPI) have equivalent layers, so the architecture ports in principle, but
every phase above is Windows-specific in implementation. If a target environment
is macOS-heavy, Phases 1.2–1.5 need a parallel track and the estimate roughly
doubles.

### 4.5 Unverified technical assumptions that could force redesign

- **MV3 service-worker lifetime.** Whether a long-lived native-messaging port
  prevents idle eviction is *recalled, not verified*. Phase 1.6 tests it; the
  offscreen-document fallback exists if it fails.
- **UIA latency from Python.** Every performance claim here comes from Microsoft
  documentation, not from a benchmark we ran. Phase 1.3's p95 < 150 ms gate is
  the real test, with C#/FlaUI as the documented fallback.
- **Electron applications** (Teams, Slack) expose accessibility trees only when
  assistive technology is detected — the same lazy-activation behaviour that
  makes UIA-over-Chrome expensive may make Electron apps invisible, or may make
  them expensive to see. Phase 1.3's coverage sample must include one.

### 4.6 Legal and organisational, not technical

Continuous content capture on employee machines engages GDPR/DPIA obligations,
US state monitoring-notice laws, and works-council consent in much of Europe.
**Content capture raises this bar materially above what Paxray faces** — that is
the price of the one thing that makes Pulse different. This is not a blocker to
prototype against fixtures, and it is not a decision for this document, but it
should be a named workstream rather than a surprise discovered at deployment.

### 4.7 Judgment calls I made that a reviewer should re-examine

- **No keystroke content capture** (research log §5.3). Costs edit history;
  buys password safety and a survivable security review. Reversible, but the
  Phase 1.2 sentinel test is deliberately written to make reversing it a
  conscious act rather than a drift.
- **SQLite over JSONL** as the live sink — mild; either works.
- **Adapt SmartRPA rather than adopt or rewrite.** If its maintenance status
  turns out to be strong and its logger quality high, adopting more of it is
  worth revisiting.
- **Context snapshot bounds** (12 elements, depth 3, 512 chars, 120 ms) are
  guesses, not measurements. Phase 1.3's coverage sample should tune them, and
  Phase 1.9's content-capture-rate metric is what tells you whether they are wrong.
