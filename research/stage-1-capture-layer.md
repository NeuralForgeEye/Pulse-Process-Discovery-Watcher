# Research Log — Stage 1 capture layer: mechanism, libraries, and prior art

**Stage / Phase:** Stage 1 — continuous wide-net capture
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes; five items escalated to human decision (§8)

---

## 1. Question being investigated

Three things, all needed before Stage 1 can be blueprinted:

1. **Mechanism:** which capture technologies actually deliver Stage 1's five
   signal types (actions, text selection, copy/paste with values, on-screen
   field content, app/window attribution) on Windows + browsers, and what do
   they cost in latency, CPU, and deployment friction?
2. **Reuse:** does an open-source UI-log recorder already exist that we can
   take instead of writing one?
3. **Prior art:** is "capture process signals from the accessibility layer
   instead of pixels" — the core Pulse pitch — already claimed or shipped?

---

## 2. What was actually checked

**Verified (read the source):**

- Microsoft Learn, [SetWinEventHook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook) — event hook registration, cross-process / DLL-injection behaviour, `idProcess`/`idThread` = 0 for desktop-wide scope.
- Microsoft Learn, [Subscribing to UI Automation Events](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsforclients) — UIA removes the need to poll UI elements; scoped listening improves efficiency; a client should not add/remove event handlers from multiple threads; a hook function can re-enter before the original event finishes processing.
- Microsoft Learn, [Caching UI Automation Properties and Control Patterns](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-cachingforclients) and [IUIAutomationElement::BuildUpdatedCache](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationelement-buildupdatedcache) — property/pattern retrieval requires **cross-process calls**; retrieving properties one element at a time is explicitly documented as slow and inefficient; batch via `CreateCacheRequest`, refresh a snapshot via `BuildUpdatedCache`.
- Microsoft Learn, [AddClipboardFormatListener](https://learn.microsoft.com/en-us/windows/desktop/api/Winuser/nf-winuser-addclipboardformatlistener), [WM_CLIPBOARDUPDATE](https://learn.microsoft.com/uk-ua/windows/win32/dataxchg/wm-clipboardupdate), [Using the Clipboard](https://learn.microsoft.com/en-us/windows/win32/dataxchg/using-the-clipboard) — listener-based clipboard change notification; `GetClipboardSequenceNumber` increments on every clipboard change.
- Chrome for Developers, [Extension service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle) — MV3 service workers are evicted after roughly 30s idle; `chrome.alarms` minimum period is 30s; offscreen documents exist for longer-lived work.
- Chrome for Developers, [Native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging) — stdio transport; JSON, UTF-8, preceded by a 32-bit message length in native byte order; **max 1 MB per message from the native host to the extension**, 4 GB in the other direction.
- Blue Prism, [Automate Chrome and Edge with UI Automation (UIA)](https://documentation.blueprism.com/bp-7-4/en-us/Guides/chrome-firefox/chrome-firefox-uia.htm) and Salesforce KB [Unresponsive pages in Chrome/Edge when Accessibility Mode is enabled](https://help.salesforce.com/s/articleView?id=000389105) — driving Chrome through UIA requires `--force-renderer-accessibility`; that flag enables UIA at browser launch and can produce **high CPU overhead**, because accessibility mode continually updates and reviews all browser processes (an expensive synchronous operation). Corroborated by the [Chromium accessibility overview](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md): the browser-process accessible-tree cache is built only when assistive technology is detected or accessibility is explicitly enabled.
- [SmartRPA](https://github.com/bpm-diag/smartRPA) (bpm-diag / Sapienza) — MIT licensed, Python 3, Windows 10/11 + macOS. Action Logger with three logging modules (System, Office, Browser) plus its own Chrome/Firefox/Edge/Opera extensions; records mouse/keyboard interaction, screenshots, tagged actions; outputs CSV and XES; five pipeline components (Log Recording, Log Processing, Event Abstraction, Process Discovery, Script Generation) with pm4py downstream. Peer-reviewed (Agostinelli et al., CAiSE 2021 / SoftwareX 2024).
- [Paxray](https://paxray.com/) — commercial task mining: "Only technical interactions such as clicks, window switches, navigation steps and events are captured. Content itself is never processed or stored"; detects keyboard shortcuts such as Ctrl+C **to determine that a copy took place — not what was copied**; local pseudonymisation before transmission; process/application whitelisting and blacklisting.
- [KYP.ai task mining comparison](https://kyp.ai/task-mining-tools-compared/) — captures "keyboard, mouse, clipboard, application interactions, system calls — across every desktop and web application"; continuous and real-time; data anonymised on-device before it leaves the endpoint; **no screenshots stored or transmitted**.
- [WO2023111685A1 / US12169723](https://patents.google.com/patent/WO2023111685A1/en) — Realitymine Ltd, priority 2021-12-13, published 2023-06-22: "simultaneous recording of the pixels of a screen, in the form of a video... and simultaneously snapshots of the UI obtained via an accessibility API", timestamp-synchronised for retrospective replay; accessibility events (clicks, scrolls, changes to UI elements) recorded and synchronised to the video. **Dual-stream by construction** — it is not an accessibility-only capture claim.
- [UiPath Task Mining recorder docs](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/capture-a-trace-with-the-recorder-atm) — "the application will generate a screenshot of each action you perform — mouse clicks and keyboard events". The page does **not** state whether UI element metadata / accessibility data is also captured.
- [Microsoft Presidio](https://github.com/microsoft/presidio) — MIT, analyzer (NER + regex + rule + checksum with context) and anonymizer (replace/mask/redact operators); `pip install presidio-analyzer presidio-anonymizer`.
- [rrweb](https://rrweb.com/) — open-source DOM session replay; record-time masking (text masking, `data-rrweb-ignore` subtree exclusion, input blocking). Optimises for pixel-faithful replay from real DOM, not for semantic event extraction.

**Recalled, not verified — do not treat as fact:**

- That an open native-messaging port keeps an MV3 service worker alive past the idle-eviction window. Widely reported, not confirmed in current Chrome docs during this session. **Phase 1.6 must test this empirically rather than assume it.**
- Current versions of `pywinauto`, `uiautomation` (yinkaisheng), `comtypes`, `pm4py`, and the reported Presidio version 2.2.362 (from a secondary blog, not from PyPI). All named as options; **pin versions at implementation time**.
- SmartRPA's last-commit date and current maintenance status. The repo shows 541 commits on master and a "SmartRPA 2.0" feature line, but no date was surfaced.

**Not checked (known gaps):**

- Full-text patent claim searches for UiPath, Celonis, Automation Anywhere/FortressIQ, NICE, Kryon/Nintex. Only secondary product documentation was read. **Skan Technologies' Justia assignee page returned HTTP 403**, so Skan's portfolio — the single most relevant competitor named in the architecture — is **unexamined**.
- European / WIPO family members of anything above.
- macOS (`AXUIElement`) and Linux (AT-SPI) capture paths. Windows-first is a scoping judgment, see §8.
- **Any actual measurement.** Every performance statement here comes from vendor or OS documentation, not from a benchmark run in this repo. Phase 1.3's checkpoint exists specifically to replace documentation with a measurement.

---

## 3. Prior art / existing solutions found

| What | Who | Type | Relevance | Source |
|---|---|---|---|---|
| Simultaneous pixel + accessibility-API recording, timestamp-synced | Realitymine Ltd | Patent WO2023111685A1 / US12169723 (prio 2021-12) | **Closest patent found.** Same sensing layer; claims are constructed around recording video *and* accessibility data together. Accessibility-only capture is the thing it pairs video *with*, not the thing it claims alone. | [Google Patents](https://patents.google.com/patent/WO2023111685A1/en) |
| Metadata-only task mining — no screenshots, no content | Paxray | Product | **Same mechanism, deliberately weaker.** Captures clicks, window switches, navigation; knows Ctrl+C happened but never the copied value or field content. | [paxray.com](https://paxray.com/) |
| Continuous keyboard/mouse/**clipboard**/app capture, no screenshots, on-device anonymisation | KYP.ai | Product | **Same mechanism, closest product.** Clipboard explicitly in scope. Whether clipboard *values* are retained and used for cross-application linking is not publicly stated. | [kyp.ai](https://kyp.ai/task-mining-tools-compared/) |
| Screenshot per action + ML clustering of traces | UiPath Task Mining | Product | Same goal, pixel-based mechanism. | [UiPath docs](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/capture-a-trace-with-the-recorder-atm) |
| Computer-vision observation of desktop work | Skan.ai; FortressIQ (Automation Anywhere, acq. 2021) | Product | Same goal, different mechanism — the explicit foil in the architecture doc. Patents **not examined** (403). | [skan.ai](https://www.skan.ai/process-discovery-and-analysis) |
| UI-log recorder → event abstraction → pm4py discovery → RPA script | SmartRPA (bpm-diag / Sapienza) | OSS (MIT) + papers | **Most directly reusable artifact found.** System/Office/Browser loggers, own browser extensions, CSV + XES output. | [github.com/bpm-diag/smartRPA](https://github.com/bpm-diag/smartRPA) |
| DOM session replay with record-time masking | rrweb | OSS | Adjacent. Reusable ideas (masking conventions), wrong optimisation target (replay fidelity, not semantics). | [rrweb.com](https://rrweb.com/) |

**Same mechanism vs. same goal.** Paxray and KYP.ai are the same *mechanism*
(interaction/metadata capture, no pixels) — these are the ones that matter.
Skan, FortressIQ and UiPath pursue the same *goal* by a different mechanism —
competitors, not blocking prior art. Realitymine is the same mechanism inside a
patent, but bound to a simultaneous video stream.

---

## 4. Options considered

**Desktop action capture:** Win32 low-level hooks (`WH_MOUSE_LL` / `WH_KEYBOARD_LL`,
directly or via `pynput`) · Raw Input (`WM_INPUT`) · `SetWinEventHook` with
`WINEVENT_OUTOFCONTEXT` · UIA event subscriptions (focus changed, property
changed on `ValuePattern.Value`, text selection changed, structure changed).

**Desktop content capture:** UIA through `comtypes` · `uiautomation`
(yinkaisheng) · `pywinauto` backend `"uia"` · FlaUI (C#/.NET) · legacy
MSAA / IAccessible2.

**Browser capture:** Chrome MV3 extension + native messaging host · Chrome
DevTools Protocol attach · OS-level UIA over the browser · rrweb embedded in an
extension.

**Event storage:** append-only JSONL · SQLite in WAL mode · DuckDB/Parquet ·
XES at capture time · OCEL 2.0 at capture time.

**Redaction:** Presidio · regex-only rules · salted HMAC tokenisation ·
capture-nothing (the Paxray position).

---

## 5. Debate — for and against

### 5.1 Browser: OS-level UIA over Chrome vs. a Chrome MV3 extension

**UIA-over-Chrome — case for.** One capture mechanism for every application on
the machine. No per-browser engineering, no extension packaging, no enterprise
policy deployment. It survives a user switching browsers and picks up browsers
we never explicitly supported. Architecturally it is the tidiest possible answer
to Stage 1.

**UIA-over-Chrome — case against.** It only works when Chromium's accessibility
mode is on, and Chromium builds that tree lazily — only when assistive
technology is detected or accessibility is forced. Blue Prism's own integration
guide tells customers to launch Chrome with `--force-renderer-accessibility` and
warns it "can result in high CPU overhead"; a Salesforce support article
documents *unresponsive pages* in Chrome and Edge under accessibility mode,
attributing it to continual synchronous updates across all browser processes. A
continuous-capture tool that makes every tab sluggish gets uninstalled in week
one — and unlike a correctness bug, this one is felt by the user every second.
It also flattens DOM semantics (label ↔ field ↔ value relationships, URL, tab
identity, SPA route) into a generic control tree, discarding exactly the
structure Stage 3 will want.

**Call: Chrome MV3 extension for browsers, UIA for native apps.** The CPU
evidence is decisive. The cost of the split — two producers to merge — is paid
anyway, because native applications require UIA regardless of what we do in the
browser.

### 5.2 Chrome DevTools Protocol vs. extension

**CDP — case for.** Deeper instrumentation than any extension API: DOM, runtime,
network, input in one protocol; no store review, no extension policy.

**CDP — case against.** Attaching a debugger either raises a persistent "Chrome
is being debugged" banner or requires launching Chrome with an open remote
debugging port. On an employee's machine an open debug port is a genuine
security exposure — anything that can reach it can drive the user's
authenticated browser sessions. Security review would reject it, correctly.

**Call: extension.** CDP is the right tool for automating a browser you own, not
for quietly observing a browser a person is working in.

### 5.3 Raw keystroke logging vs. UIA value-change events for "typed values"

**Keylogging — case for.** Simple, universal, works where UIA exposes nothing,
and preserves edit history (typed-then-deleted), which is genuine evidence about
hesitation and rework.

**Keylogging — case against.** It captures passwords. There is no reliable way
to know a field is sensitive at keypress time — by the time UIA tells you
`IsPassword`, you have already logged the characters. It also produces character
streams that must be reassembled into field values anyway. And it is the single
feature most likely to get the whole tool blocked by a works council, a security
review, or a DPIA.

**UIA value-change — case for.** One event yields the *final field value plus
the field's identity* (`AutomationId`, `Name`, control type, parent window) —
precisely the tuple Stage 3 needs. Password fields are identifiable and
skippable. Event volume is an order of magnitude lower.

**UIA value-change — case against.** Not every control implements
`ValuePattern`; custom-drawn and canvas-based controls expose nothing; no edit
history.

**Call: UIA value-change as the primary source of typed content; the keyboard
hook is reduced to non-content signals only** — that a shortcut occurred
(Ctrl+C/V/X, Tab, Enter, Esc), and typing-burst boundaries and rates. Where UIA
yields nothing, emit `typed_into_unknown_field` with a character count, never
the characters.

### 5.4 Storage: JSONL vs. SQLite vs. XES/OCEL at capture time

**XES/OCEL at capture — case for.** pm4py reads them directly; they are the
standards of the field; Stage 4 would be unblocked on day one; OCEL 2.0's
multi-object model is a genuinely good fit for a UI event that relates to a
window, an application, a session, and possibly a case identifier at once.

**XES/OCEL at capture — case against.** Both require a **case notion**, and
determining what a case is *is Stage 2's entire job*. Writing a case ID at
capture time pre-judges segmentation and silently discards the evidence Stage 2
is supposed to learn from — the boundary signals only exist in the unsegmented
stream. This is an architectural trap, not a formatting preference.

**Call: SQLite (WAL) as the live sink; JSONL/Parquet as the export; convert to
XES or OCEL 2.0 only after Stage 2 assigns episodes.** pm4py supports OCEL 2.0
in SQLite, XML and JSON exchange formats, so deferring costs nothing.

### 5.5 Reuse SmartRPA vs. build custom

**Reuse — case for.** MIT licensed, Python, already has System/Office/Browser
loggers and its own browser extensions, already emits CSV and XES, already wired
to pm4py, and is backed by peer-reviewed publications — which also makes it a
citable baseline. Writing a UI logger from scratch is weeks of Win32 plumbing
with zero novelty payoff.

**Reuse — case against.** It is research-grade code aimed at *synthesising an
RPA script from one user's routine*, not at continuous multi-user capture. It
takes screenshots — the exact thing Pulse exists to avoid. Its maintenance
status is unconfirmed. And it does not appear to perform UIA-based on-screen
field-content snapshots, which is the one capture behaviour Pulse actually
depends on.

**Call: adapt, don't adopt, don't rewrite.** Take SmartRPA's event taxonomy and
its Office/browser logger structure as a reference implementation and a
correctness oracle; build our own capture host around UIA content snapshots.
Phase 1.1 must read `SmartRPA_events.pdf` before the schema is frozen — if their
taxonomy is sound, matching it buys free interoperability with published
research at no cost.

---

## 6. Novelty check (required)

**Is Stage 1 novel? No — and the blueprint says so plainly.**

"Capture process signals from application metadata instead of pixels" is
**already shipping commercially**. Paxray states it captures only technical
interactions and never content. KYP.ai states it captures keyboard, mouse,
clipboard and application interactions continuously with no screenshots and
on-device anonymisation. The architecture doc's framing — a sensing method "no
one else in our space is using" — is **too strong as written**, and this log is
the evidence for that.

What is *not* obviously covered by that prior art:

1. **Retaining the value, not just the gesture.** Paxray deliberately records
   that Ctrl+C occurred without recording what was copied. Pulse's Stage 3 is
   impossible under that policy. "Capture the copied value and the surrounding
   on-screen field content, then use value identity as the linking evidence
   across applications" is a *different technical mechanism* with a different
   privacy profile — not a rebranding of the same one.
2. **Accessibility-tree content snapshot at action time** — knowing what a field
   *displayed* even though the user never clicked or copied it. The Realitymine
   patent obtains this by pairing accessibility data with video; Pulse would
   obtain it from the accessibility layer alone.

Neither is "apply an LLM to task mining" — both are specific capture decisions
with specific downstream consequences. But **both only pay off at Stage 3**. On
its own, Stage 1 is competent engineering over well-trodden ground. It should be
built for reliability and defended as a foundation, not marketed as invention.

**Closest prior art:** KYP.ai (product; same mechanism; clipboard included) and
WO2023111685A1 (patent; same sensing layer; bound to simultaneous video).
**Concrete difference from the patent:** no video stream at all, and the
accessibility snapshot exists to support cross-application value linking rather
than synchronised replay.

---

## 7. Conclusion / recommendation

Build Stage 1 as a **three-producer capture host** — a Win32/UIA desktop
producer, a Chrome MV3 extension producer, and a clipboard producer — writing
into one schema-versioned SQLite (WAL) store, merged into a single ordered
timeline by a bounded reorder buffer over a shared monotonic clock anchor. Use
UIA `ValuePattern` change events instead of keystroke content for typed values,
and batched `CacheRequest` snapshots instead of per-property UIA reads for
on-screen content. Adapt SmartRPA's event taxonomy without adopting its
codebase. Defer XES/OCEL conversion until Stage 2 defines episodes.

**What would change this call (the falsifier):** if Phase 1.3's measurement
shows the Python/`comtypes` UIA path cannot snapshot a focused element's
neighbourhood within budget (p95 < 150 ms, zero dropped focus events over a
5-minute scripted workload), move the desktop producer to C#/FlaUI and keep
Python downstream. If Phase 1.6 shows an MV3 service worker cannot be held alive
reliably via a native-messaging port, fall back to an offscreen document — and
if that also fails, the browser producer must buffer in `IndexedDB` inside a
content script and flush opportunistically.

---

## 7a. Phase 1.3/1.4 implementation findings (this session — real measurements, not projections)

The falsifier in §7 has now actually been tested, not just proposed. Full
numbers are in `plans/BUILD-STATUS.md`'s "Stage 1 implementation progress"
section; the headline findings that change the picture in this log:

- **The latency gate: initially borderline, then fixed and re-measured —
  PASSED, no C#/FlaUI fallback needed.** First measurement, four real
  60-second runs: p95 = 161.7ms, 154.4ms (both over the 150ms line), 139.6ms,
  145.6ms (both under), with **zero real drops in any run** — every click
  resolved a real element every time; the entire gap was p95 timing, not
  correctness. Diagnosed cause: one shared UIA thread was also processing
  desktop-wide `AutomationFocusChangedEvent` traffic, not just this app's
  own (confirmed indirectly — a `field_value_changed` event was captured
  from an unrelated real application mid-test, proving system-wide UIA
  traffic reached this same thread). **Fix applied and confirmed**: the
  global `AutomationFocusChangedEvent` subscription was only ever needed to
  drive rescoping, and this session had already added a second, more
  reliable rescoping trigger (Phase 1.2's `window_activated` signal, which
  doesn't depend on UIA's narrower "something gained keyboard focus"
  semantics) — so the global subscription was removed entirely rather than
  kept alongside it. Re-measured with 4 fresh 60-second runs: p95 = 138.4ms,
  142.1ms, 129.6ms, 143.9ms — all comfortably under 150ms, zero drops in
  every run. This never met the falsifier's stated bar for moving to
  C#/FlaUI, and no such move was made; the fix was a contention/
  architecture correction, not evidence the Python/comtypes UIA path itself
  is too slow.
- **Electron/web-hosted content blind spot, confirmed empirically, not just
  theorised.** Microsoft Teams' native shell is visible to UIA (44 elements
  to depth 8), but the tree bottoms out at an empty `RootWebArea` node — the
  actual chat content is invisible without forcing Chromium's
  `--force-renderer-accessibility` mode, which §5.1 already flagged as a
  real CPU-cost tradeoff. This is no longer a prediction; it is a measured
  result against a real, currently-installed Teams client.
- **Three real, non-obvious implementation bugs worth recording for anyone
  building on `comtypes` + UI Automation again:**
  1. A DPI-unaware process gets Win32 coordinates virtualized while
     `IUIAutomation::ElementFromPoint` uses real physical coordinates — on
     any DPI-scaled display (the large majority of real Windows machines),
     every resolved element is wrong unless the process calls
     `SetProcessDpiAwareness` before any window/UIA call. Not mentioned in
     the Microsoft Learn UIA docs read for this log's §2; found only by
     testing against a real fixture app on a real scaled display.
  2. comtypes represents a NULL COM element out-parameter as a non-`None`
     Python object wrapping a null pointer — `is None` checks silently pass
     it through; only a truthiness check (`if elem:`) catches it correctly.
  3. A test-only finding, but a sharp one: the Alt-tap used to bypass
     Windows' foreground-stealing lock also activates Office's ribbon
     "KeyTips" overlay, silently swallowing the next real keystroke sent to
     an Office app (Ctrl+N was consumed as a KeyTip selector instead of
     opening a new workbook). Found only by testing against Excel; fixed
     by sending Escape immediately after the Alt tap.
- **Phase 1.4 extended to Excel** (formula bar, `FormulaBar` automation ID,
  which has TextPattern but NOT ValuePattern, so content had to go in via
  real keystrokes rather than `SetValue()`): keyboard selection 17/20 (85%)
  across 4 runs; mouse-drag selection **0/20 — never registered once**,
  a stronger, more clear-cut version of the same mouse-drag unreliability
  already seen in Notepad. **WordPad could not be tested at all**:
  confirmed absent from this machine (Microsoft removed it from Windows in
  2024), not a skipped test.
- **A real, load-correlated reliability gap found late in the same
  session, after Phase 1.3 had already been reported as a clean pass —
  since fixed and confirmed, in a follow-up session.** Re-running the
  content-correctness checkpoint on a machine that had become genuinely
  busy (confirmed via `Get-Counter`: 63-91% CPU from ordinary concurrent
  use, not from Pulse itself) reproduced only 3-4 of 5 sentinel fields in
  4 of 5 repeat runs; a quieter machine reproduced the original clean 5/5.
  Root cause: `build_context_snapshot`'s 120ms internal budget truncated
  the sibling walk earlier under real CPU contention, before reaching
  later-ordered fields.

  **The fix took three attempts, each measured, not assumed:**
  1. Batch the neighbourhood walk via UIA's `*BuildCache` tree-walker
     calls, reusing the acting element's full 9-property/2-pattern cache
     request (the same caching discipline blueprint step 2 already
     mandates for the acting element). Fixed completeness (0/122
     truncations under a real, artificially-induced 74-80% CPU load burst
     -- a genuine 6-thread PowerShell busy-loop, not a guess) but
     INCREASED measured end-to-end p95 latency from ~140ms to ~172ms,
     regressing the separate latency gate.
  2. Tried a second, deliberately lighter cache request (4 properties + 1
     pattern) scoped just to this walk. Latency stayed at ~171ms —
     confirming the cost was the `*BuildCache` mechanism's fixed per-step
     tax (the accessibility bridge still queries the target app's UI
     Automation provider for cached data on every node visited, even ones
     immediately discarded), not the size of what's requested.
  3. **Landed on**: keep the plain (uncached) walker for stepping --
     cheap per-step navigation -- and cut the NUMBER of live property
     calls per sibling instead: a single-property identity check
     (AutomationId only, replacing a two-property NativeWindowHandle+Name
     check) and never fetching both Name and Value for the same sibling
     (whichever supplies usable text is reused as both). Confirmed 5/5
     sentinel fields across 4 separate runs under the same real 60-80%
     CPU load burst, plus a clean 5/5 at normal load -- a real, reproduced
     fix.

  **A second real bug found during attempt 1, worth its own note**:
  caching a pattern's AVAILABILITY (`AddPattern(ValuePatternId)`) does
  NOT cache the pattern's own sub-properties -- calling `.CachedValue` on
  a `GetCachedPattern()` result raised `E_INVALIDARG` until
  `UIA_ValueValuePropertyId` was added to the cache request as its own
  property. Not documented in the Microsoft Learn pages read for this
  log's §2; found only by testing.

  **The latency gate's own re-measurement, on the other hand, was
  inconclusive** -- re-running it several times immediately after
  confirming the content-correctness fix produced wildly inconsistent
  numbers (200.9ms, 2095.4ms, briefly 20028.5ms with real drops) that did
  not correlate cleanly with measured CPU load, and one run coincided
  with active memory compression (~900MB) and elevated paging -- most
  plausibly this session's own accumulated resource footprint after many
  hours of repeated CaptureHost starts/stops, not a regression from the
  content-correctness fix (a separate code path). Recorded honestly as
  **not re-confirmed**, not as "still passing" -- see `plans/BUILD-STATUS.md`.

---

## 8. Open items requiring a human decision

1. **Raw values vs. salted hashes — flagged under CLAUDE.md's "when you
   disagree" rule; NOT decided here.** The architecture says to store "the
   actual value that was copied". For *linking* purposes a salted HMAC of a
   normalised value proves "the same value appeared in App A and App B" without
   retaining the value, which would put Pulse's privacy profile alongside
   Paxray's while preserving Stage 3's core evidence. But hashing destroys
   fuzzy/partial matching (`LN-00123` vs `00123`), blocks human-readable Stage 6
   output, and removes the on-screen language Stage 5 depends on. I did not make
   this call. The blueprint keeps both open with a dual-write design (encrypted
   local value vault + hash in the event log) and a per-field-class policy, so
   the decision can be made later without rework — **but it must be made before
   capture ever runs on real user data.**
2. **The novelty framing in the architecture doc.** Stage 0/1 claims a sensing
   method "no one else in our space is using". Paxray and KYP.ai contradict
   that directly. Someone should decide whether to soften that wording or to
   re-point the claim at the value-retention/linking mechanism, which is where
   the real difference lives.
3. **Citrix / VDI blind spot — the strongest argument against the premise.** In
   a Citrix or equivalent virtualised session the client receives screen
   updates, not UI objects; RPA vendors fall back to OCR and image recognition
   precisely because the accessibility layer is absent on the client side. QA/QC
   work in regulated industries frequently runs inside exactly such
   environments. Pulse would be **blind** there where Skan's computer-vision
   approach would not. Decision needed: scope VDI out of v1, or require an agent
   installed *inside* the virtual session.
4. **Windows-first scoping.** This blueprint assumes Windows + Chromium. macOS
   (`AXUIElement`) and Linux (AT-SPI) are out of scope for v1 — my judgment
   call, not something the architecture states.
5. **The patent search is incomplete and is not clearance.** Skan's assignee
   page 403'd; UiPath, Celonis, NICE and Automation Anywhere claim sets were not
   read. A real prior-art check before any filing needs full-text claim
   searching, ideally by a patent attorney. Nothing in this log should be
   treated as freedom-to-operate.
6. ~~Phase 1.3's latency gate is borderline — decision needed on how to
   proceed.~~ **Resolved.** The proposed lighter fix (remove the global
   `AutomationFocusChangedEvent` subscription, rely solely on
   `window_activated` for rescoping) was applied and re-measured: 4 fresh
   60-second runs all passed comfortably (p95 = 138.4/142.1/129.6/143.9ms,
   zero drops). No C#/FlaUI fallback needed. See §7a for the full numbers.
7. **Phase 1.4's mouse-drag selection-capture rate (Notepad ~20-40%, Excel
   0%) is not yet confirmed as a synthetic-input artifact.** The
   explanation on record — real hit-testing/timing mismatch between
   scripted `SendInput` dragging and each app's own text control, not a
   capture-code defect — is well-supported (every drag that DID register,
   in both apps, produced exact, correct text) but has **not been verified
   with a real human dragging a real mouse**. Needed before this
   attribution is fully trusted; tracked as an open item in
   `plans/BUILD-STATUS.md`.
8. ~~Phase 1.3's content-correctness checkpoint is not reliable under real
   CPU load.~~ **Resolved.** Root cause was per-sibling live COM call
   volume, not the budget value itself. Fixed by minimising live property
   calls per sibling (single-property identity check, never fetching both
   Name and Value for one sibling); two other approaches were tried and
   measured first (full and lightened `*BuildCache` batching), both fixed
   completeness but regressed the latency gate, and were reverted. See
   §7a for the full three-attempt account and the real bug found along
   the way (`AddPattern` alone does not cache a pattern's own
   sub-properties). Confirmed 5/5 across 4 runs under real, artificially-
   induced 60-80% CPU load.
9. **The latency gate needs a clean re-measurement.** Re-checking it
   immediately after confirming item 8's fix produced wildly inconsistent
   numbers (200.9ms to 20028.5ms, one run with real drops) that did not
   correlate cleanly with measured CPU, and coincided once with active
   memory compression and elevated paging -- most plausibly this
   session's own accumulated footprint after many hours of repeated
   CaptureHost starts/stops, not a regression from item 8's fix (a
   separate code path), but this is not proven. The gate's last clean,
   trustworthy result remains the 4-run table in `plans/BUILD-STATUS.md`
   (138-144ms) from before this session's changes. Needs re-running on a
   rested machine before being treated as reconfirmed.
