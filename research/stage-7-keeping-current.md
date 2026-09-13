# Research Log — Stage 7: keeping the map current over time

**Stage / Phase:** Stage 7 — drift detection (optional for v1)
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes; one architecture-specific risk
identified in §5.2 that does not appear in the general literature

---

## 1. Question being investigated

Because capture never stops, we can notice when a real process quietly changes.
Questions:

1. Is "concept drift in process mining" an established field with usable methods?
2. Which detector fits a control-flow process rather than a generic data stream?
3. **How do we tell a real process change from our own capture breaking?**

---

## 2. What was actually checked

**Verified:**

- **Survey: *A Survey on Concept Drift in Process Mining*, ACM Computing Surveys**
  ([arXiv 2112.02000](https://arxiv.org/pdf/2112.02000), [ACM](https://dl.acm.org/doi/10.1145/3472752)). Concept drift occurs "when a single event log includes data from multiple versions of a process, making the detection of such drifts essential for ensuring reliable process mining results."
- **Drift types:** techniques primarily focus on **sudden** and **gradual** drift;
  newer approaches also identify **incremental** and **recurring** drift.
- **ProDrift** — uses "non-overlapping continuous fixed and adaptive-size
  windowing, statistical testing, and an oscillation filter", but "only deals with
  linear changes." Related: [*A Robust and Accurate Approach to Detect Process Drifts from Event Streams*](https://arxiv.org/pdf/2103.10749).
- **ADWIN (adaptive windowing)** — adaptive sliding windows for drift detection;
  **ADWIN2** detects slow gradual drift and adapts window size dynamically
  according to the observed rate of change.
- **Page-Hinkley test** — "a sequential adaptation of the abrupt change detection
  in the average of a Gaussian signal, monitoring a cumulative variable defined as
  the cumulated difference between the observed values and their mean until the
  current moment."
- **EDDM** — designed for streaming classification, sensitive to gradual and
  recurring drift.
- **A stated limitation that shapes our design:** detectors such as "ADWIN,
  Page-Hinkley, and STUDD have proven effective in general-purpose data stream
  contexts, but they **lack process awareness and structural traceability**
  required in control-flow-driven environments"
  ([DriftXMiner, ScienceDirect](https://www.sciencedirect.com/org/science/article/pii/S1546221825010392)).
- Recent work: *Machine learning-based detection of concept drift in business
  processes* ([Process Science, Springer](https://link.springer.com/article/10.1007/s44311-025-00012-w)); DriftXMiner for incremental drift with transparency.

**Recalled, not verified:**

- Whether ProDrift is available as usable software (it is associated with the
  Apromore ecosystem). **Check availability and licence** before planning around it.
- Whether PM4Py includes drift detection. Not established this session — the
  conformance-checking primitives we need are confirmed, but a packaged drift
  detector is not.

**Not checked:**

- Any drift-detection method validated specifically on UI logs rather than
  system-generated event logs.
- Patents on process drift detection (UiPath/Celonis both market "process
  monitoring"). **Unsearched.**

---

## 3. Prior art / existing solutions found

| What | Who | Type | Relevance |
|---|---|---|---|
| Concept drift in process mining: types, detection, localisation | ACM CSUR survey | Academic | The field exists and is mature enough to reuse |
| ProDrift — windowing + statistical testing + oscillation filter | Apromore/academic | Tool + method | Process-aware; limited to linear changes |
| ADWIN / Page-Hinkley / EDDM | General data-stream literature | Methods | Usable on derived signals, but **not process-aware** |
| DriftXMiner — incremental drift with structural traceability | ScienceDirect 2025 | Academic | Addresses exactly the traceability gap we care about |
| Process monitoring / drift alerts | Celonis, UiPath | Commercial | Same goal commercially; **claims unsearched** |

**Conclusion:** not novel, and the architecture correctly labels this optional for
v1. Reuse established methods.

---

## 4. Options considered

- **Conformance-based drift:** replay new episodes against the existing model,
  watch fitness over time.
- **Feature-distribution drift:** statistical tests over behavioural features
  (activity frequencies, transition probabilities, durations).
- **Model re-discovery and comparison:** mine a fresh model periodically and
  compare structurally.
- **Generic stream detectors** (ADWIN / Page-Hinkley) over derived signals.

---

## 5. Debate — for and against

### 5.1 Conformance-based vs. generic stream detectors

**Conformance-based — for.** We already compute alignment-based fitness in Stage
4. Replaying new episodes against the established model and watching fitness
decline is cheap, directly meaningful ("the real work no longer matches the map"),
and **structurally traceable** — alignments tell you *which* steps stopped
matching, not merely that something changed. That traceability is exactly what the
literature identifies generic detectors as lacking.

**Conformance-based — against.** Fitness is a single aggregate; a large change in
a rare branch may not move it. It also needs a stable model to replay against,
which means it cannot detect drift in a process that was never well-modelled.

**Generic detectors (ADWIN, Page-Hinkley) — for.** Mature, cheap, well
understood, and good at spotting a change in a numeric signal quickly.

**Generic detectors — against.** The cited limitation is decisive for us: they
"lack process awareness and structural traceability required in control-flow-driven
environments." They can tell you *that* something changed, not *what* changed —
and "what changed" is the entire deliverable of this stage. An alert that says
"drift detected" with no structural explanation generates work rather than insight.

**Call: conformance-based detection as primary** (fitness over a sliding window,
with per-activity and per-transition alignment statistics for localisation),
**with generic detectors applied to derived signals as a cheap early-warning
layer.** Use ProDrift-style windowing and statistical testing as the comparison
arm if the tool is actually available.

### 5.2 The risk the general literature doesn't cover: our capture can break

**This is the most important point in this log, and it is specific to Pulse's
architecture.**

Every drift-detection method in the literature assumes the event log keeps meaning
the same thing over time. **Ours might not.** Pulse reads UI structure. If a
vendor ships a new version of LoanDesk with a redesigned screen:

- `element.path_hash` values change (Stage 1)
- screen identities change, so **activity names change** (Stage 4 abstraction)
- the new activities don't match the model
- **fitness collapses, and every drift detector screams "the process changed!"**

But the process did not change at all. **The application's UI changed.** A system
that reports a UI update as a process change will cry wolf until nobody reads its
alerts — which destroys the value of continuous capture, the one advantage this
stage exists to exploit.

**The distinguishing signal:** a genuine process change shows up as *the same
recognisable steps in a different order, or new/removed steps* — while the
vocabulary and element identities stay stable. A UI change shows up as
*vocabulary and element identities changing while the sequence of intent stays the
same*, and it typically appears **abruptly for all users at once** (a deployment)
rather than spreading gradually (a habit change).

So drift alerts must be cross-checked against **capture-health signals we already
have**: Stage 1 `capture_degraded` rates and application versions, Stage 2 residue
%, Stage 3 link-tier mix, and Stage 4 activity-dictionary stability. If activity
names churned at the same moment fitness dropped, the first hypothesis is a UI
change, not a process change.

I did not find this addressed in the drift literature — reasonably, since that
literature assumes system-generated logs with stable activity labels. **It is a
direct consequence of sensing through the UI**, and it should be treated as a
first-class requirement of this stage rather than an edge case.

### 5.3 Alert or re-mine automatically?

**Auto re-mine — for:** the map stays current with no human effort.
**Auto re-mine — against:** the architecture is explicit — "flag it for human
review rather than silently trusting either the old or new version." That is the
right call. A silently updated process map has no version a human ever agreed to,
which makes it useless as a reference document and dangerous as an audit artefact.

**Call: detect, characterise, alert. Never silently replace.** Keep both versions
with a diff and let a human decide.

---

## 6. Novelty check (required)

**Not novel.** Concept drift in process mining has a dedicated ACM Computing
Surveys review, multiple named detectors, and commercial equivalents in process
monitoring products.

**The one part that is ours** is the *UI-change-versus-process-change
disambiguation* described in §5.2 — and that is not an invention so much as an
obligation created by our sensing method. It is a specific mechanism
(cross-checking drift signals against capture-health and activity-dictionary
stability), so it is not "apply an LLM to X", but it is best described as
necessary engineering rather than a contribution.

---

## 7. Conclusion / recommendation

Build drift detection on **conformance-based signals** (alignment fitness over
sliding windows, localised per activity and transition), with generic stream
detectors as a cheap early-warning layer and ProDrift-style windowing as a
comparison arm if available. **Mandatory:** cross-check every drift signal against
capture-health metrics before raising it as a process change, and classify alerts
as `process_change`, `capture_change`, or `ambiguous`. Never auto-replace a model;
produce a diff and route it to a human, as the architecture requires.

**What would change this call:** if UI churn turns out to be frequent in the
target environment, capture-change detection stops being a filter on drift alerts
and becomes a primary feature in its own right — arguably more valuable
day-to-day than process drift, since it tells you when Pulse itself needs
attention.

---

## 8. Open items requiring a human decision

1. **Is Stage 7 in scope for v1 at all?** The architecture says optional. My view:
   the *capture-health monitoring* half is not optional — if applications change
   and nobody notices, Stages 1–4 silently degrade. The *process-drift* half can
   wait. Splitting it that way is a scoping decision worth making deliberately.
2. **Alert thresholds and cadence.** How much fitness decline over how long
   constitutes drift? Needs real data; any number now is a guess.
3. **Who receives drift alerts, and what are they expected to do?** An alert with
   no owner is noise.
