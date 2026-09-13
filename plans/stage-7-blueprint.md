# Stage 7 Blueprint — Keeping it current over time

**Source of truth:** `plans/pulse-architecture.md`, Stage 7 (optional for v1).
**Cross-cutting controls:** `plans/platform-architecture.md` — binding.
**Research backing:** `research/stage-7-keeping-current.md`.
**Plain-English version:** `manual-readable/stage-7.md`.
**Status:** blueprint only — no implementation code has been written.

> **Capture-health monitoring (Phase 7.2) is confirmed for v1**, and it now has
> a second job beyond detecting UI changes: **watching the sensing tier mix.**
> If a surface silently falls back from a structural read (T1/T2) to computer
> vision (T3) — because an application update broke its accessibility tree —
> data quality drops sharply while every count still looks healthy. A rising
> T3 share on a surface that used to be structural is a **capture regression
> alert**, and arguably the most actionable signal this stage produces.

> **Scoping recommendation, flagged for decision.** The architecture marks this
> stage optional for v1. I agree for *process-drift* detection. I **disagree for
> the capture-health half** (Phase 7.2): if a monitored application changes its UI
> and nobody notices, Stages 1–4 degrade silently and every later output is quietly
> wrong. That half should be in v1. See §4, OQ-17.

---

## 1. Stage goal

Because capture never stops, Pulse is positioned to notice when a real process
quietly changes — a new step appears, an old one stops happening, work moves to a
different system. Stage 7 watches new episodes against the established map,
detects meaningful divergence, works out *what* changed, and **flags it for human
review rather than silently trusting either the old or the new version**. It also
does something the general drift literature does not have to worry about:
distinguishes *the process changed* from *our ability to observe it changed*,
because Pulse senses through application UI structure and a vendor's UI update
looks, to every standard drift detector, exactly like a process change.

---

## 2. Phases

Four phases.

---

### Phase 7.1 — Baseline snapshots and model versioning

**Goal.** You cannot detect change without something to compare against.

**Build steps**

1. **Version every published process description** (from Stage 6) with an
   immutable snapshot: the model, activity dictionary, frequency statistics with
   intervals, quality metrics, the corpus it was mined from, and the capture
   configuration in force at the time.
2. **Record the capture context**, not just the model: application versions
   observed, Stage 1 coverage map, `capture_degraded` rates, Stage 2 residue rate,
   Stage 3 link-tier mix, Stage 4 activity-dictionary contents. **These are the
   control variables** — without them, a later divergence cannot be attributed to
   either cause, and the stage's central question becomes unanswerable.
3. **Build a diff function** over two snapshots: activities added/removed/renamed,
   transitions added/removed, frequency shifts with significance, link changes,
   quality changes.
4. **Keep every version.** The architecture requires never silently trusting one
   over the other; that requires both to exist.

**Expected output.** A versioned snapshot store; a model diff function with
human-readable output.

**Validation checkpoint**

- Diff two deliberately-constructed snapshots with known differences; every
  injected change is reported, and **nothing else is** — a diff that reports
  spurious changes will train its readers to ignore it.

---

### Phase 7.2 — Capture-health monitoring *(recommended for v1)*

**Goal.** Know when Pulse's ability to observe has changed, **before**
interpreting any behavioural signal as process drift.

**Why this comes before drift detection:** every drift method in the literature
assumes activity labels keep meaning the same thing. Pulse reads UI structure. If
LoanDesk ships a redesign, `element.path_hash` values change → screen identities
change → **activity names change** (Stage 4's abstraction) → nothing matches the
model → **fitness collapses and every detector reports a dramatic process
change**. Nothing about the process changed. A tool that cries wolf on every
vendor update gets its alerts ignored, which destroys the value of continuous
capture — the one advantage this stage exists to exploit.

**Build steps**

1. **Monitor, per application, continuously:**
   - `capture_degraded` event rate (Stage 1)
   - element-resolution rate and unknown-`path_hash` rate
   - application version where obtainable
   - activity-dictionary churn (Stage 4) — **the most direct signal**
   - Stage 2 residue rate and Stage 3 link-tier mix
2. **Alert on capture regression in its own right** — "we can see 40% less of
   LoanDesk than last month" is an actionable operational alert regardless of any
   process question, and arguably the most useful day-to-day output of this stage.
3. **Build the disambiguation rule set**, using the distinguishing signals:
   - **UI change:** vocabulary and element identities churn while the *sequence of
     intent* is stable; onset is **abrupt and simultaneous across all users** (a
     deployment); `capture_degraded` and unknown-element rates spike together.
   - **Process change:** element identities stay stable while the *order or
     presence of recognisable steps* changes; onset is typically **gradual and
     uneven across people** (a habit spreading), and capture-health metrics stay flat.
4. **Classify every divergence** as `capture_change`, `process_change`, or
   `ambiguous`. **Ambiguous is a legitimate answer** and should be common early —
   forcing a binary call would manufacture the false confidence this whole project
   is built to avoid.
5. **Support re-mapping after a confirmed UI change** — re-anchor the activity
   dictionary to the new element identities so history stays comparable rather
   than starting over. Without this, one vendor update erases the baseline.

**Reuse call.** Build custom — this is specific to our capture architecture and
has no equivalent in the general literature, which assumes stable system-generated
logs.

**Expected output.** A capture-health dashboard and alerts; a classifier over
divergences; a re-anchoring tool.

**Validation checkpoint**

- **The key test:** simulate a UI change by modifying the fixture application's
  control identifiers without changing the workflow at all. The system must
  classify it as `capture_change`, **not** `process_change`. This single test is
  what separates a useful alerting system from one nobody reads.
- Converse test: change the *workflow* in the fixture while leaving the UI
  identical. Must classify as `process_change`.
- Capture regression alerts fire when an application's element-resolution rate
  drops materially.

---

### Phase 7.3 — Process drift detection and characterisation

**Goal.** Detect that the real process has moved, and say *what* moved.

**Build steps**

1. **Primary signal: conformance-based drift.** Replay new episodes against the
   baseline model using PM4Py's alignment-based conformance checking, and track
   fitness over a sliding window.
   - *Why:* we already compute alignments in Stage 4; declining fitness directly
     means "real work no longer matches the map"; and alignments give
     **structural traceability** — *which* steps stopped matching, not just that
     something changed.
   - *Why that matters:* the literature notes that general-purpose detectors
     (ADWIN, Page-Hinkley, STUDD) "lack process awareness and structural
     traceability required in control-flow-driven environments." An alert that says
     "drift detected" without saying what changed generates work rather than
     insight.
2. **Secondary: statistical detectors over derived signals** — activity
   frequencies, transition probabilities, durations — as a cheap early-warning
   layer. ADWIN (adaptive sliding windows; ADWIN2 handles slow gradual drift by
   adapting window size to the observed rate of change) and the Page-Hinkley test
   (cumulative deviation of observed values from their running mean) are both
   established and cheap. Use them to look early, never to explain.
3. **Comparison arm: ProDrift-style windowing** — non-overlapping continuous
   fixed and adaptive-size windows with statistical testing and an oscillation
   filter. Documented limitation: it "only deals with linear changes". **Check
   availability and licence before planning around it.**
4. **Classify the drift type** — sudden, gradual, incremental, or recurring. This
   changes what a human should do about it: sudden usually means a policy or system
   change; gradual usually means a practice spreading person to person.
5. **Characterise, don't just detect.** Produce a diff in words: "since March, 40%
   of cases include a new step — checking the sanctions list in *[system]* — before
   approval; this step did not appear in the baseline."
6. **Mine a candidate new model** for comparison, but **do not publish it
   automatically** (see Phase 7.4).
7. **Cross-check against Phase 7.2 before raising anything.** If activity-dictionary
   churn spiked at the same moment fitness dropped, the first hypothesis is a UI
   change. **This check is mandatory, not advisory.**

**Reuse call.** **Reuse PM4Py conformance checking** for the primary signal;
`river` or an equivalent stream-detector library for ADWIN/Page-Hinkley (verify
availability). Characterisation logic is custom.

**Expected output.** Drift signals with onset, type, magnitude, localisation, a
plain-language characterisation, and a candidate new model.

**Validation checkpoint**

- **Synthetic drift injection:** construct corpora with a known sudden change, a
  known gradual change, and no change. Detect the first two with correct onset
  (±1 window) and correctly report nothing for the third. **The no-change case
  matters most** — a detector that finds drift in stable data is worse than none.
- Localisation: the reported changed activities match the injected ones.
- Every drift alert carries a plain-language description of what changed.

---

### Phase 7.4 — Review, decision, and acceptance

**Goal.** Put a human in the loop, as the architecture explicitly requires.

**Build steps**

1. **Never auto-replace a published model.** The architecture is explicit: flag
   for human review rather than silently trusting either version. A silently
   updated map has no version anyone ever agreed to — useless as a reference,
   dangerous as an audit artefact.
2. **Review screen:** side-by-side old and new, the diff in words, the drift
   evidence, the capture-health cross-check, and the candidate new model's quality
   metrics. Actions: accept new version, keep old, mark as capture issue, or
   request more data.
3. **Alert routing with an owner.** An alert with no owner is noise. Route
   capture-health alerts to whoever maintains the deployment; process-drift alerts
   to the process owner.
4. **Thresholds are configurable and must be set from real data.** Any number
   chosen now is a guess, and a guessed threshold produces either alert fatigue or
   silence.
5. **Keep an audit trail** of every alert, decision, and version transition —
   which, for a regulated QA/QC context, may be as valuable as the process map.

**Validation checkpoint (Stage 7 exit criteria)**

| Metric | Threshold |
|---|---|
| Injected sudden drift detected, correct onset | yes (±1 window) |
| Injected gradual drift detected | yes |
| **False positives on a stable corpus** | **zero** |
| Simulated UI change classified as `capture_change` | yes |
| Simulated workflow change classified as `process_change` | yes |
| Drift localisation matches injected change | ≥ 80% |
| No model auto-replaced without human decision | 100% |
| Every alert has an owner and a plain-language description | 100% |

---

## 3. Dependencies

**Needs from Stage 6:** the published process description and its version — the
baseline.
**Needs from Stage 4:** the model and conformance machinery (alignments), plus the
activity dictionary, whose churn is the primary capture-change signal.
**Needs from Stages 1–3, continuously:** new episodes, and — equally important —
the capture-health metrics (`capture_degraded` rates, element-resolution rates,
residue rate, link-tier mix) that make the disambiguation in Phase 7.2 possible.

**Hands off to:** a human, and — on acceptance — a new Stage 6 document version.

---

## 4. Open questions and risks

### OQ-17 — Split the stage for v1 scope *(recommendation, needs a decision)*

The architecture marks Stage 7 optional. I agree for process-drift detection.
**I disagree for capture-health monitoring** (Phase 7.2): without it, an
application update silently degrades every earlier stage and nobody finds out
until a customer notices the map is wrong. That is a v1 operational requirement,
not a nice-to-have. Flagged under CLAUDE.md's disagreement rule — **decision
needed before scoping v1.**

### OQ-18 — Thresholds and cadence

How much fitness decline over how long is drift? How often to check? Both need
real data. Everything proposed here is a placeholder.

### OQ-19 — Who owns alerts?

Unowned alerts are noise. Needs an operational answer, not a technical one.

### Risk — alert fatigue is the failure mode

If the system reports every UI tweak as a process change, its alerts will be
ignored within weeks and the whole stage becomes decorative. Phase 7.2 exists
specifically to prevent this, and its fixture test is the gate.

### Risk — drift detection needs volume, twice over

Detecting that a 5% branch grew to 12% requires enough episodes in both windows.
Early deployments will not have them, and the honest response is to report
"insufficient data to assess drift" rather than to report noise as signal — the
same discipline as Stage 4's minimum-episode gate.

### Risk — this could become employee monitoring

"Person X's work diverges from the process" is one query away from this stage's
data, and it would be a misuse: Stage 7 exists to notice *the process* changing,
not to score individuals. Same guard as Stage 4 Phase 4.7 — aggregate by default,
individual views only on an explicit, logged request.

### Judgment calls a reviewer should re-examine

- **Conformance-based detection as primary** over general-purpose detectors —
  chosen for structural traceability, which the literature identifies as the gap.
- **Capture-change disambiguation treated as a first-class requirement** rather
  than an edge case. I believe this is right and specific to our sensing method,
  but it adds real work to a stage the architecture called optional.
- **Never auto-updating the model** — follows the architecture, and it does mean
  the map goes stale if nobody reviews the alerts.
