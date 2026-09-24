# Pulse — Build Status

Running log of what is decided, what is blueprinted, and what is still blocked
on a human decision. Read this first.

**Current pass: Stage 1 implementation has started. Phases 1.1-1.4 of Stage 1
are built and tested (see "Stage 1 implementation progress" below); every
other phase across all seven stages remains blueprint-only.**

---

## Stage 1 implementation progress

**Phase 1.1 — Event schema and local event store: fully passed.**
- Round-trip: 10,000/10,000 byte-identical.
- Schema enforcement: 20/20 malformed events rejected, 0 written.
- Crash safety: 5/5 kill-mid-transaction runs recovered with zero torn rows.
- Throughput: ~3,290 events/s sustained (threshold ≥2,000/s).

**Phase 1.2 — Desktop action and window-context capture: passed the app-switch/
attribution/no-keylogging portion of the checkpoint; the full 50-action
scripted ground-truth (≥98%) and 30-minute CPU-stability sub-checks were not
run.**
- App-switch capture: 100% (3/3) across 4 consecutive live runs.
- `app.process_name` attribution: 100% across all captured events.
- No-keylogging guardrail: zero sentinel occurrences, every run.

**Phase 1.3 — UIA element resolution and on-screen content snapshot: content-
correctness's CPU-load sensitivity is now FIXED and confirmed under real,
repeated load. The latency gate needs a clean re-measurement (see below) —
today's re-checks were too inconsistent to trust, for reasons that don't
look like a regression from this fix, but that isn't proven either.**
- Correctness against fixtures (20 documented controls, 18 individually
  click-testable — the 2 populated ListBoxes are excluded from this specific
  check since a click inside one correctly resolves to the row under the
  cursor, not the container): **18/18**, confirmed across repeat runs.
- **Content correctness — FIXED.** Previously: missed 1-2 of 5 sentinel
  fields in 4 of 5 runs under real CPU load (63-91%, via `Get-Counter`).
  Root cause: `build_context_snapshot`'s 120ms budget truncated the
  sibling walk before reaching later-ordered fields under contention.
  **Real fix, arrived at after two false starts** (documented in full in
  `uia_client.py`'s docstring and `research/stage-1-capture-layer.md`):
  1. First tried batching the whole neighbourhood walk via UIA's
     `*BuildCache` tree-walker calls (matching blueprint step 2's caching
     discipline). Fixed completeness but INCREASED latency (~140ms →
     ~172ms) — a `*BuildCache` walker step carries a real fixed per-step
     cost regardless of how much is cached.
  2. Tried a lighter, walk-scoped cache request (4 properties instead of
     9) — same ~171ms; confirmed the tax was the BuildCache mechanism
     itself, not batch size.
  3. **Landed on**: stay with the plain (uncached) walker for stepping,
     and cut the NUMBER of live property calls per sibling instead — a
     single-property identity check (AutomationId only, not the previous
     two-property check) and never fetching both Name and Value for the
     same sibling. Also fixed a real bug found along the way: caching a
     pattern's AVAILABILITY (`AddPattern`) does not cache the pattern's
     own sub-properties (e.g. Value) — `UIA_ValueValuePropertyId` must be
     requested separately, or `.CachedValue` raises `E_INVALIDARG`.
  **Confirmed under real, repeated, artificially-induced CPU load** (a
  genuine 6-thread PowerShell busy-loop, not a guess): 5/5 sentinel fields
  found across 4 separate runs at 60-80% measured CPU load, plus a clean
  5/5 at normal load. This is a real, reproduced fix, not a one-off.
- Password guardrail: sentinel value **never** appears in the store; the
  `field_value_changed` event for the password field carries
  `value_readable: null`, `redaction_state: "password_field"`.
- **Latency gate (p95 < 150ms, zero dropped focus events) — PASSED, after a
  real fix.** Initial measurement was borderline (2 of 4 runs over 150ms:
  161.7ms, 154.4ms; 2 under: 139.6ms, 145.6ms), diagnosed as contention from
  UI Automation's global `AutomationFocusChangedEvent` firing constantly
  from unrelated desktop-wide activity on the same single UIA thread that
  also services on-demand snapshot requests. **Fix applied**: removed that
  global subscription entirely; UIA rescoping now runs solely from Phase
  1.2's own reliable `window_activated` signal (`notify_foreground_changed`
  in `uia_events.py`), which is app-scoped, not desktop-wide. Re-measured
  with 4 fresh 60-second runs, all passing comfortably:

  | Run | p95 | Context-truncated (element OK, neighbourhood walk hit its 120ms budget) | Dropped (no element at all) |
  |---|---|---|---|
  | 1 | **138.4ms** | 4/122 | 0/122 |
  | 2 | **142.1ms** | 6/122 | 0/122 |
  | 3 | **129.6ms** | 0/122 | 0/122 |
  | 4 | **143.9ms** | 9/122 | 0/122 |

  All 4 comfortably under the 150ms gate; zero real drops in any run, same
  as before the fix. No C#/FlaUI fallback was needed — the fix was a
  contention/architecture correction (a wrong, overly-broad event
  subscription), not a limitation of the Python/comtypes UIA path itself.

  **⚠️ Needs a clean re-measurement — today's re-checks were too noisy to
  trust, in either direction.** While confirming the content-correctness
  fix above (a separate, unrelated code path) on the same session, this
  gate was re-run several more times and swung wildly: 200.9ms, then
  2095.4ms, then briefly 20028.5ms with 17 real drops on one run, measured
  with system CPU checked immediately before each run ranging from 23% to
  85%+ with no clean correlation to the result. That 20-second run
  coincided with "Memory Compression" active at ~900MB and elevated paging
  — a real, observed system event, not invented — most likely from this
  session's own accumulated footprint (many hours, many repeated
  CaptureHost starts/stops and app launches/kills across Phase 1.3/1.4
  testing today). **This does not touch the content-correctness fix above,
  which was verified separately and repeatedly under controlled, measured
  load.** But it means the clean 4-run table above (138-144ms) should be
  treated as **not yet re-confirmed after today's code changes** — the
  honest state is "last known good, needs a fresh check on a rested
  machine," not "still passing." Do not treat this gate as settled until
  that recheck happens.
- Real-world coverage sample (5 apps, real installations, this session):

  | App | UIA tree useful? | Notes |
  |---|---|---|
  | Microsoft Excel | Yes | 28 elements, real automation IDs, native Win32 |
  | Microsoft Word (substitute for Outlook — not installed on this machine) | Yes | 23 elements incl. page-level structure |
  | Windows Settings (substitute for a separate WPF app — none available) | Yes | 25 elements, native XAML labels |
  | File Explorer (substitute for an internal LOB app — none available) | Yes | 46 elements |
  | Microsoft Teams (Electron/web-hosted) | **Partial** | Outer native shell visible (44 elements to depth 8), but the actual chat CONTENT is not exposed — the tree bottoms out at an empty `RootWebArea` node. Confirms, empirically, the exact concern already on record in `research/stage-1-capture-layer.md` about Chromium's accessibility tree needing `--force-renderer-accessibility` to populate, which the same research log flags as a real CPU-cost tradeoff, not yet decided. |

**Phase 1.4 — Text selection and highlight capture: no-churn and source-honesty
checkpoints passed; selection-capture-accuracy checkpoint now covers 3 of the
blueprint's 4 apps and, after fixing two real test-driver bugs found this
session, both apps' mouse-drag rates are now 95-100%, up from 0-40%.**
- Scope note stated explicitly: the blueprint specifies Notepad, WordPad,
  Excel and the fixture app. **WordPad is confirmed NOT INSTALLED on this
  machine** (`where.exe`, direct path checks, and `Get-Command` all come
  back empty) — Microsoft removed it from Windows in 2024. This is a real
  gap in what the blueprint's checkpoint can be run against on current
  Windows, not a skipped test. Notepad, Excel and the fixture app are
  covered.
- No-churn check (one `text_selected` event per drag, not a stream):
  **passed, confirmed stable across 4+ repeat runs** (one real debounce bug
  found and fixed along the way — see the bug list below).
- Source honesty (fallback-path selections labelled `inferred_selection`,
  never mislabelled as an observed TextPattern selection): **passed.**
- Selection-capture accuracy, split and reported honestly rather than forced
  to one number:
  - **Notepad** — keyboard (Ctrl+A) 100% (20/20 across 4 fresh runs this
    session); mouse-drag **95% (19/20 across 4 runs: 5/5, 5/5, 4/5, 5/5)**,
    up from an earlier-session figure of ~20-40% with no code change to the
    test or the capture path. The most likely explanation, though not
    formally isolated in a controlled A/B: Phase 1.3's later fix (removing
    the redundant global `AutomationFocusChangedEvent` subscription) reduced
    UIA-thread contention session-wide, and mouse-drag selection capture is
    an inherently timing-sensitive path (see the Excel finding below) — so
    a general latency improvement plausibly resolved most of what looked
    like a Notepad-specific problem. Not re-diagnosed further since the
    numbers are now good and stable.
  - **Excel** (formula bar, automation_id `FormulaBar`) — keyboard **85%
    (17/20 across 4 runs: 5/5, 4/5, 4/5, 4/5)**; mouse-drag **100% (20/20
    across 4 runs: 5/5, 5/5, 5/5, 5/5)**, up from a prior 0/20 (0%) — see
    "Real bugs found and fixed" below for the two real, distinct root
    causes found and fixed (a test-driver click-target bug and a
    drag-geometry bug), plus a third, genuine pipeline-timing
    characteristic that needed a longer settle window, not a code fix.
    `setup_failures` (text verified not to have landed in the formula bar
    after 3 retries) was 0 across every run once the verification fix was
    in place.
  - Both apps' figures come from scripted `SendInput` synthetic input, same
    as the rest of Phase 1.4's checkpoints, plus (for Notepad) a small
    amount of real-human confirmation already on record (see below).

  **Open item, downgraded from blocking to informational**: mouse-drag
  selection accuracy is no longer a real open risk (95-100% synthetic hit
  rates in both apps, with every miss producing a slightly-short-of-full
  selection rather than a wrong one), but a real-human manual pass with a
  known, counted number of attempts still has not been run end-to-end. The
  user's one earlier organic manual test (real mouse, real Notepad,
  unscripted: typed "hello world", dragged over it several times) captured
  3 real, exact, correct selections, but the total attempt count was not
  recorded, so a real hit rate from that test still cannot be computed.
  This no longer blocks marking the checkpoint passed, given the much
  stronger synthetic evidence now in hand, but remains worth doing for
  final sign-off.

### Real bugs found and fixed this session (Phase 1.3/1.4 implementation)

1. **DPI virtualization mismatch — a real production bug, not a test
   artifact.** Without declaring the process DPI-aware, Windows virtualizes
   coordinates for most Win32 APIs while UI Automation's `ElementFromPoint`
   uses real physical-monitor coordinates; on any DPI-scaled display (125%
   scaling here — the default on most modern Windows machines), every
   click resolved the WRONG element. Fixed with
   `src/pulse_capture/desktop/dpi.py`, called at the top of `run.py`'s
   `main()`. Without this fix, Phase 1.3 would be silently wrong on
   essentially any real deployment machine.
2. UIA subscription rescoping relied solely on UI Automation's own
   `AutomationFocusChangedEvent`, which tracks keyboard-input focus, not
   "the foreground window changed" — the two are not the same thing, and a
   window can become foreground with no element inside it ever gaining UIA
   focus. First fixed by also rescoping from Phase 1.2's already-reliable
   `window_activated` signal; then, once the latency gate showed the global
   focus-change subscription was itself contending for the same UIA thread
   with unrelated desktop-wide traffic, **removed entirely** — rescoping now
   runs solely from `window_activated`, which fixed both the correctness gap
   and the latency contention in one change.
3. A debounce fix attempt used "is the last-seen time close to now" instead
   of an exact token match, letting multiple scheduled flush timers all
   fire; fixed with the standard exact-token debounce pattern.
4. `id(sender)` is not a stable identity for a UI element across separate
   COM callback invocations (comtypes can hand back a different wrapper
   object for the same real element); fixed using UIA's own
   `GetRuntimeId()`.
5. Element-neighbourhood text extraction preferred `CurrentName` over
   `ValuePattern.CurrentValue`, incorrectly reporting a WinForms TextBox's
   inherited label text instead of its actual typed value.
6. `CachedBoundingRectangle` returns a `ctypes.wintypes.RECT` struct, not a
   tuple — a naive unpack silently produced `bounds: null` everywhere.
7. comtypes null-element COM out-parameters are not Python `None` — every
   tree-walk in `uia_client.py` had to be corrected to check truthiness
   (`if elem:`), not `is not None`.
8. The test driver's foreground-forcing helper (`tests/_win_input.py`,
   `force_foreground`) taps the Alt key to bypass Windows' anti-focus-
   stealing lock — which is *also* the shortcut that activates Office's
   ribbon "KeyTips" overlay, so a following keystroke (e.g. Ctrl+N) got
   consumed as a KeyTip selector instead of running normally. Found while
   testing against Excel. Fixed by sending Escape immediately after, which
   dismisses any such overlay and is harmless when none is showing.
9. **A real, production data-quality bug**: `field_value_changed`'s typed
   content was being stored as a comtypes VARIANT's debug repr string
   (literally `"VARIANT(vt=0x8, 'hello world')"`) instead of the actual
   text, because the property-changed callback did `str(new_value)`
   instead of unwrapping via `.value`. Found by reading back a real
   capture session, not by a scripted test. Fixed in `uia_events.py`;
   every `field_value_changed` event captured before this fix has the
   ugly wrapper text in `content.value_readable` in any existing
   `pulse.db`, not the clean string.
10. `view_events.py` (the human-readable viewer, not the capture pipeline
    itself) ordered ALL events by `t_mono_ns`, which the schema is explicit
    is only valid for ordering *within one session* — a monotonic clock
    resets on every new capture-host run. Across a `pulse.db` accumulated
    over many separate runs/days, this could surface an old session's
    events ahead of ones from minutes ago. Found by checking a real user's
    live test and getting what looked like the wrong data. Fixed by
    re-sorting by `t_wall_utc` (the field the schema designates for
    human/cross-session reading) before display.
11. **Test-driver bug (Excel, not Pulse capture code)**: the click used to
    put keyboard focus in Excel's formula bar before typing occasionally
    landed on a ribbon control instead (confirmed directly: `field_value_
    changed` events showed ribbon font-name/size values like `"Calibri"`,
    `"11"` instead of the typed sentinel). Any drag issued afterward had
    nothing real to select, which is indistinguishable from a capture miss
    unless checked. Fixed in `tests/test_phase1_4_text_selection.py` by
    `_type_into_formula_bar_verified()`, which reads the formula bar's
    `TextPattern.DocumentRange.GetText(-1)` back after typing and retries
    (up to 3×) until the text is confirmed to have actually landed there.
12. **Test-driver bug (Excel, not Pulse capture code)**: even with focus
    verified, the mouse-drag's start x-coordinate reused the same point as
    the initial focus-click (`rect.left + 40`, chosen to avoid the fx
    icon) — but `TextPattern.DocumentRange.GetBoundingRectangles()` showed
    the actual typed text started only ~11px from the control's left edge,
    so the drag consistently began ~29px (about 3 characters) *inside* the
    text. The resulting selection was real and correct as a substring, but
    never a *prefix*, so it could never satisfy the checkpoint's
    prefix-based hit-check — a real, correctly-attributed near-100% miss
    rate caused entirely by test geometry. Fixed by `_formula_bar_drag_
    span()`, which reads the true bounding rectangle instead of guessing
    an offset.
13. **Genuine pipeline-timing characteristic (not a bug, and not fixed in
    production code)**: even with both of the above fixed, the mouse-drag
    loop still measured a reproducible 0/5 at the same `settle_s=0.5` used
    successfully by the keyboard loop. Root cause: a real drag-selection
    fires the primary `UIA_Text_TextSelectionChangedEvent` path *and* the
    Phase 1.4 mouse-drag-heuristic fallback (`_on_drag_click`, triggered by
    the physical mouse-up); the fallback's later debounce call resets the
    shared per-element token and supersedes the primary's already-scheduled
    flush, so the actual emission waits a fresh 300ms settle measured from
    the fallback's later timestamp, not from the drag's end. Confirmed by
    directly dumping the written events at `settle_s=0.5` (zero rows) vs.
    `settle_s=1.0`/`1.5` (every run 5/5). The test's wait was increased to
    `1.0s` for the mouse-drag loop only; this is a real, measured capture-
    to-database latency floor for the drag path worth keeping in mind for
    any real-time consumer, not something to silently paper over.

### Local capture-health report — `capture_health.py`

Built as the single-machine building block for Stage 7 Phase 7.2
(capture-health monitoring), after the content-correctness CPU-load
investigation above made clear that a standing way to check "how healthy
has capture actually been" — without re-running pytest — was worth having.

```
uv run python capture_health.py [--db pulse.db] [--session <id-prefix>]
```

Reads one local `pulse.db` and reports, per the real terms established
above: **clean** (element resolved, full context) / **degraded** (element
resolved, context truncated — the same `snapshot_timeout` finding) /
**dropped** (no element resolved at all), plus end-to-end latency
percentiles and a breakdown by session so a specific bad run can be
spotted. **This is explicitly NOT the fleet-wide, across-many-machines
dashboard** the full Phase 7.2 design calls for — every capture host still
only writes to its own local file; nothing is transmitted anywhere. That
larger version needs a central collection point, which does not exist and
is a data-governance decision (CLAUDE.md's "Data controls" point 4), not
something to wire up unilaterally.

**Real output against this project's own accumulated `pulse.db`** (696
events, spanning this whole engagement) surfaced something genuinely
useful on the first run: one old session (`f5e819a1`, from before the
DPI-awareness fix earlier in this project) shows **100% dropped (10/10)**
— concrete, after-the-fact confirmation of exactly how broken element
resolution was before that fix, visible directly in the data rather than
asserted. Overall across all sessions in the file: 72.3% clean, 7.7%
degraded, 20.0% dropped (dominated by that one pre-fix session).

---

## Decisions taken (do not re-litigate)

| # | Decision | Recorded in |
|---|---|---|
| **D-A** | **Deployment is internal to Wells Fargo.** Not a product sold externally. No cross-boundary data problem, but the controls external vendors must meet define the internal bar. Target shape is clustered, multi-datacenter, large internal audience. | `platform-architecture.md` §1 |
| **D-B** | **Sensing is tiered and arbitrated** — T1 accessibility → T2 DOM → T3 computer vision, CV used **only** where no structural layer exists (Citrix, VDI, mainframe, canvas). | `platform-architecture.md` §2, S1 Phase 1.10 |
| **D-C** | **Provenance tagging is mandatory.** Every value carries its sensor + confidence. **Values of different provenance are never merged.** Disagreement is flagged, never averaged. | `platform-architecture.md` §2.3 |
| **D-D** | **Identifiers hashed at the point of capture** (keyed HMAC, Vault key, normalised, token components hashed). Cleartext never enters the pipeline. Structural text stays readable. Audited reversal vault off the main path. | `platform-architecture.md` §3, S1 Phase 1.8 |
| **D-E** | **Federation is the default posture for data sharing** — local per business unit, pattern-level summaries centrally. **Superseded for Stage 4 mining specifically by D-K** (pooled, pending governance). The principle still governs everything else. | `platform-architecture.md` §5 |
| **D-F** | **Environment-agnostic architecture** — ports/adapters, one environment config file, containerised from the start. | `platform-architecture.md` §4 |
| **D-G** | **Four differentiators as one integrated capability** — sensing-tier arbitration · field-pair relationship graph · evidence-graded output · capture-health self-awareness. | `CLAUDE.md`, `platform-architecture.md` |
| **D-H** | **Event abstraction is an explicit Stage 4 phase** (4.2). Addition to the original architecture. | S4 blueprint |
| **D-I** | **Capture-health monitoring is in v1** (Stage 7 Phase 7.2), though drift detection stays optional. | S7 blueprint |
| **D-J** | **Architecture doc moved to `plans/pulse-architecture.md`** and its "no OCR, no video" framing corrected. | `pulse-architecture.md` |
| **D-K** | **Stage 4 is built against a single pooled corpus of HMAC-hashed identifiers** — working assumption, **not** an approved architecture. See the open governance item below. Federated fallback designs retained. | `platform-architecture.md` §5.3–5.5 |

---

## Artifacts

| Document | Blueprint | Research | Plain-English |
|---|---|---|---|
| **Platform (cross-cutting)** | `plans/platform-architecture.md` | `research/deployment-sensing-and-data-controls.md` | `manual-readable/platform.md` |
| Stage 1 — capture | ✅ 10 phases | ✅ | ✅ |
| Stage 2 — segmentation | ✅ 8 phases | ✅ | ✅ |
| Stage 3 — cross-app linking | ✅ 8 phases | ✅ | ✅ |
| Stage 4 — process mining | ✅ 8 phases | ✅ | ✅ |
| Stage 5 — type labelling | ✅ 5 phases | ✅ | ✅ |
| Stage 6 — output | ✅ 5 phases | ✅ | ✅ |
| Stage 7 — keeping current | ✅ 4 phases | ✅ | ✅ |

---

## ⚠️ OPEN GOVERNANCE ITEM — read before building Stage 4

> **OPEN GOVERNANCE ITEM: Stage 4 currently assumes pooling of HMAC-hashed
> identifiers across business units is permitted. This has not been confirmed by
> data governance/InfoSec. If later found not permitted, fall back to the
> federated local-mine-then-merge-models approach (candidate designs already
> drafted under PA-1) instead of pooled mining. Do not treat pooled mining as
> final/approved architecture until confirmed.**

**Status:** pooled mining is the current working path, taken to keep Stage 4
tractable while the governance question is answered. It is **not** a conclusion
that federation was rejected on its merits, and the federated candidate designs
in `platform-architecture.md` §5.5 are **retained as the fallback plan — do not
delete them.**

**Cheap-insurance constraints now in force** (`platform-architecture.md` §5.4),
so that a later refusal is a boundary change rather than a rewrite:

1. The corpus sits behind a `CorpusProvider` port; no Stage 4 phase reaches past
   it to assume it can enumerate every episode company-wide.
2. **The activity dictionary is globally versioned and shared from day one.**
   This is the critical one — two business units' models cannot be merged if
   their activity names were derived independently. It costs almost nothing now
   because Phase 4.2 needs a reviewable dictionary regardless.
3. Prefer aggregatable statistics (directly-follows counts, frequencies) where
   they are of comparable quality to trace-level operations.

**Known blast radius if governance refuses:** Phases 4.4, 4.5 and 4.7 break
outright (all need traces); 4.1 and 4.6 break partially; 4.2 works only if
constraint 2 was honoured; 4.3 is unaffected.

---

## Open questions — blocked on a human decision

### Blocking / high value

| # | Question | Owner | Blocks |
|---|---|---|---|
| **PA-1** | **OPEN GOVERNANCE ITEM — pooled vs federated mining.** Stage 4 proceeds on pooled hashed data as a working assumption. **Unconfirmed.** Federated fallback designs retained in `platform-architecture.md` §5.5; cheap-fallback constraints in §5.4. | **Data governance / InfoSec** — confirm or refuse | Nothing now; **invalidates Stage 4's corpus model if refused** |
| **PA-2** | Data classification and storage location — policy lookup via the db_discovery approval path. | InfoSec / data governance | Real-data capture |
| **PA-3** | Works council / employee consent posture for content-bearing capture. SKAN treats works-council approval as a selling point, which indicates a real gate. | Legal / HR | Real-data capture |
| **PA-6** | Freedom-to-operate on the DLP clipboard patents. **Internal use is not exempt from infringement under US law.** Claim text unread — summaries only. | Internal IP counsel | Commercial/legal risk, not the build |
| **OQ-11** | APQC PCF licensing for internal use. | Legal / procurement | Stage 5 taxonomy |

### Design decisions still open

| # | Question | Where |
|---|---|---|
| **PA-4** | Where CV inference runs — endpoint vs central. Drives endpoint footprint, the main objection a desktop team will raise. | Platform §7 |
| **PA-5** | HMAC key rotation and re-hash strategy. | Platform §7 |
| **OQ-6** | What counts as a case — one loan, one review of a loan, or one sitting? | S2 §4 |
| **OQ-7 / OQ-9** | Overlapping episodes: allow (truthful about multitasking) or force disjoint (convenient for miners)? And the flattening rule. | S2 §4, S4 §4 |
| **OQ-8** | Residue tolerance — what % unassigned means "broken". | S2 §4 |
| **OQ-3b** | Direction of flow — assert only on Tier 1/2 evidence, else `undirected`? | S3 §4 |
| **OQ-3c** | Two-pass population design needs a skeptical review **before** implementation, to prevent circular confidence. | S3 §4 |
| **OQ-10** | Minimum episodes before publishing a map (30 proposed, no evidence). | S4 §4 |
| **OQ-12** | Is an LLM permitted in the product? Defaulted **off**. | S5 §4 |
| **OQ-13** | Which process categories matter for v1. | S5 §4 |
| **OQ-14/15/16** | PDD skeleton · delivery format · who the reader is. | S6 §4 |
| **OQ-18/19** | Drift thresholds · who owns alerts. | S7 §4 |
| **NEW** | Shape-mask leak: storing `AA-99999` beside a hash reveals identifier *format*. Usually acceptable; for low-cardinality fields it could narrow values. Needs an InfoSec opinion. | S2 header |

### Resolved

| # | Was | Resolution |
|---|---|---|
| **OQ-1** | Raw values vs hashes | **HMAC at capture** + audited reversal vault (D-D) |
| **OQ-2** | Novelty framing overstated | Architecture doc corrected; claim re-pointed at the four-part combination |
| **OQ-3** | Citrix/VDI blind spot | **Tiered sensing with CV fallback** (D-B) |
| **OQ-4** | Windows-only | Structural tiers Windows+Chromium; CV tier covers the rest |
| **OQ-5** | Patent search incomplete | Still incomplete — **reclassified as PA-6**, routed to IP counsel |
| **OQ-17** | Stage 7 scope | Capture-health in v1, drift detection optional (D-I) |
| **Repo layout** | Architecture doc at root | Moved to `plans/` (D-J) |

---

## Cross-cutting risks

- **Pooled mining is unconfirmed.** Stage 4 is being built on an assumption that
  data governance has not yet ratified. The cheap-insurance constraints above are
  what keep this from becoming a rewrite. **Get the governance answer early** —
  it is a conversation, not a research project, and it de-risks the largest
  single structural assumption in the plan.
- **The identifier-coverage measurement (Stage 2 Phase 2.3) is still the single
  most important early number.** If fewer than ~60% of real episodes carry a
  visible, capturable case identifier, Stage 2's primary design *and* Stage 3's
  evidence base weaken **together**. Take it early.
- **The CV tier is unvalidated and cannot be validated outside the bank.** It
  must be flagged as untested in every status report and never demoed as proven.
- **Over-hashing is a real failure mode.** A system that hashes button labels
  cannot tell a QA/QC process from data entry and cannot produce a readable
  document. Protect what is sensitive; leave readable what is procedural.
- **Precision over recall, everywhere.** A missed link makes the map incomplete;
  a false one makes it wrong.
- **Honest-uncertainty sections will be under pressure.** Stage 1's coverage
  map, Stage 3's unexplained transitions, Stage 4's insufficient-data verdicts,
  Stage 6's "what we don't know". Structurally mandatory by design.
- **Surveillance drift.** Stage 4 Phase 4.7 and Stage 7 make individual
  comparison technically trivial. Aggregate by default; enforce in code.

---

## Unverified assumptions

| Assumption | Stage | Status |
|---|---|---|
| MV3 service-worker kept alive by native-messaging port | 1 | Recalled, not verified. Tested in 1.6 |
| UIA latency from Python/comtypes | 1 | **Benchmarked this session — borderline.** p95 across 4 real 60s runs: 161.7/154.4ms (fail), 139.6/145.6ms (pass), 150ms gate. Zero real drops in any run. See "Stage 1 implementation progress" above |
| Electron app accessibility | 1 | **Tested this session (Teams).** Outer shell visible; actual web/chat content NOT exposed without forcing Chromium accessibility mode — confirmed, not just theorised |
| Where SKAN runs CV inference (endpoint vs gateway) | — | Ambiguous in their materials. Don't assert either way |
| SKAN patent portfolio | — | **Unexamined** (Justia 403). Retry another route |
| `ruptures`, `hdbscan`, Splink, ProDrift licences | 2,3,4,7 | Unverified |
| DenStream repo licence/language | 2 | Unretrievable |
| DLP patent **claim text** | 3 | Summaries only |
| TKDE benchmark results table | 4 | **Abstract only.** Read before choosing the miner |
| Split Miner ranking/licence/availability | 4 | All unverified |
| APQC PCF redistribution rights | 5 | Unverified |
| Validated comprehension-test instrument | 6 | None found; our design is bespoke |
| Library versions generally | all | **Not pinned** |

---

## Conventions

- **No dates** in file contents or filenames. Git records history.
- Every stage has three artifacts (blueprint, research, plain-English); a change
  to one usually needs the other two.
- Validation checkpoints are **gates, not suggestions** — including the ones
  needing a human (activity dictionary review in 4.2, comprehension test in 6.5).
- Nothing in `research/` is legal clearance.

---

## Suggested build order

Risk-first, not document order. Both of the project's biggest uncertainties are
measurable long before the full pipeline exists:

1. **Stage 1 Phases 1.1–1.3** + the Phase 1.9 coverage sample — does the
   accessibility layer actually reach the target applications? This also sizes
   how much work the CV tier has to do, which determines whether Phase 1.10 is a
   core component or an option.
2. **Stage 2 Phase 2.3** on that sample — the identifier-coverage number that
   Stages 2 and 3 both depend on.
3. **Then** commit to the rest of Stage 1, with the platform interfaces
   (§4.1) in place from the first commit so nothing needs retrofitting.

Do **not** build the CV tier (1.10) before step 1 reports. If structural sensing
covers well over 90% of real work, the project gets materially simpler.

---

## Next action

Awaiting direction. The open questions above are decisions and policy lookups,
not unknowns requiring more research.

**PA-1 is now unblocked for building** — Stage 4 proceeds on pooled hashed data
as a working assumption, with the federated fallback retained and the
cheap-insurance constraints in force. The governance confirmation should be
sought in parallel rather than waited on.
