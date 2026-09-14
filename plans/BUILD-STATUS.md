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

**Phase 1.3 — UIA element resolution and on-screen content snapshot: FULLY
PASSED — all 4 checkpoints.**
- Correctness against fixtures (20 documented controls, 18 individually
  click-testable — the 2 populated ListBoxes are excluded from this specific
  check since a click inside one correctly resolves to the row under the
  cursor, not the container): **18/18**, confirmed across repeat runs.
- Content correctness (5 sentinel field values must appear in an *unrelated*
  click's context, without the user touching those fields): **5/5**.
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
- Real-world coverage sample (5 apps, real installations, this session):

  | App | UIA tree useful? | Notes |
  |---|---|---|
  | Microsoft Excel | Yes | 28 elements, real automation IDs, native Win32 |
  | Microsoft Word (substitute for Outlook — not installed on this machine) | Yes | 23 elements incl. page-level structure |
  | Windows Settings (substitute for a separate WPF app — none available) | Yes | 25 elements, native XAML labels |
  | File Explorer (substitute for an internal LOB app — none available) | Yes | 46 elements |
  | Microsoft Teams (Electron/web-hosted) | **Partial** | Outer native shell visible (44 elements to depth 8), but the actual chat CONTENT is not exposed — the tree bottoms out at an empty `RootWebArea` node. Confirms, empirically, the exact concern already on record in `research/stage-1-capture-layer.md` about Chromium's accessibility tree needing `--force-renderer-accessibility` to populate, which the same research log flags as a real CPU-cost tradeoff, not yet decided. |

**Phase 1.4 — Text selection and highlight capture: no-churn and source-honesty
checkpoints passed; selection-capture-accuracy checkpoint is a scoped, honest
partial (see below), and only 2 of the blueprint's 4 required apps were
tested.**
- Scope note stated explicitly: the blueprint specifies Notepad, WordPad,
  Excel and the fixture app. This session covered **Notepad and the fixture
  app only** (time-boxed); WordPad and Excel selection capture is **not yet
  verified** — an open gap, not a silent skip.
- No-churn check (one `text_selected` event per drag, not a stream):
  **passed, confirmed stable across 4+ repeat runs.**
- Source honesty (fallback-path selections labelled `inferred_selection`,
  never mislabelled as an observed TextPattern selection): **passed.**
- Selection-capture accuracy, split and reported honestly rather than forced
  to one number: **keyboard selection (Ctrl+A) ~93% (14/15 across 3 runs)**;
  **mouse-drag selection ~20-40%, inconsistent** — a synthetic-input/
  hit-testing timing issue against Windows 11 Notepad's WinUI3 rich-text
  control, not a capture-code defect (every drag that DID register produced
  the complete, exact, correct text — never a wrong or partial-but-uncaught
  value).

  **⚠️ Open item: this attribution is not yet confirmed.** The ~20-40% mouse-
  drag figure was produced entirely by scripted `SendInput` synthetic
  dragging, and the "it's a synthetic-input timing artifact, not a real
  capture defect" explanation is the most likely one given the evidence
  (every registered drag captured exact, correct text — never wrong or
  corrupted), but it has **not been verified with a real human dragging a
  real mouse**. That verification pass is still needed before this
  attribution is fully trusted — do not treat mouse-drag selection as
  "known good" until someone has actually tried it by hand.

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
