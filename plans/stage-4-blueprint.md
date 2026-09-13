# Stage 4 Blueprint — Finding the real process across many episodes

**Source of truth:** `plans/pulse-architecture.md`, Stage 4.
**Cross-cutting controls:** `plans/platform-architecture.md` — binding.
**Research backing:** `research/stage-4-process-mining.md`, and
`research/deployment-sensing-and-data-controls.md`.
**Plain-English version:** `manual-readable/stage-4.md`.
**Status:** blueprint only — no implementation code has been written.

> ### ⚠️ OPEN GOVERNANCE ITEM — the corpus model is a working assumption
>
> **OPEN GOVERNANCE ITEM: Stage 4 currently assumes pooling of HMAC-hashed
> identifiers across business units is permitted. This has not been confirmed by
> data governance/InfoSec. If later found not permitted, fall back to the
> federated local-mine-then-merge-models approach (candidate designs already
> drafted under PA-1) instead of pooled mining. Do not treat pooled mining as
> final/approved architecture until confirmed.**
>
> **What this means for building.** Every phase below may assume a single pooled
> corpus of episodes carrying HMAC-hashed identifiers. That is the working path,
> chosen to keep this stage tractable while the governance question is answered
> in parallel. It is **not** a finding that federation was rejected on its
> merits, and the federated candidate designs are retained in
> `plans/platform-architecture.md` §5.5 as the fallback plan.
>
> **Three constraints are in force so a later refusal is a boundary change, not
> a rewrite** (`platform-architecture.md` §5.4). They are cheap now and
> expensive to retrofit:
>
> 1. **The corpus sits behind a `CorpusProvider` port.** No phase below may
>    reach past it and assume it can enumerate every episode in the company.
>    `PooledCorpusProvider` today; `FederatedCorpusProvider` is the fallback.
> 2. **The activity dictionary (Phase 4.2) is globally versioned and shared from
>    day one.** This is the critical constraint. Under federation each business
>    unit would derive its own dictionary, and two units' models cannot be merged
>    if `Search loan document` in one is `Activity 17` in the other. A shared
>    dictionary is a hard prerequisite for **every** federated candidate, and it
>    costs almost nothing now because Phase 4.2 needs a reviewable dictionary
>    regardless.
> 3. **Prefer aggregatable statistics** (directly-follows counts, activity and
>    transition frequencies) where they are of comparable quality to trace-level
>    operations. They sum across units; traces do not.
>
> **Known blast radius if governance refuses:** Phases 4.4, 4.5 and 4.7 break
> outright (all need traces); 4.1 and 4.6 break partially; 4.2 works only if
> constraint 2 was honoured; 4.3 is unaffected.
>
> **One interaction to watch.** Pooling makes the minimum-episode gate in Phase
> 4.3 easier to clear, because a business unit that individually falls below the
> threshold contributes to a pooled total that clears it. That is a genuine
> benefit of pooling — and it is exactly the benefit that disappears if
> governance refuses. **Do not let a map that only exists because of pooling be
> presented as a per-unit finding**; record which units contributed and in what
> proportion.
>
> **A second, smaller change:** episodes now carry sensing provenance. Phase 4.5
> should report model quality **separately for structurally-sensed and
> vision-sensed episodes** — if fitness is materially worse on CV-sourced data,
> that is a finding about the sensing tier, not about the process, and blending
> them would hide it.

> **Deviation from the architecture, flagged per CLAUDE.md.** The architecture
> moves directly from episodes to frequency analysis. That skips **event
> abstraction** — converting raw UI events into named process activities — which
> the process-mining literature treats as a hard problem in its own right, and
> which SmartRPA's pipeline implements as a dedicated component. This blueprint
> adds it as **Phase 4.2**. Every downstream number depends on it, so it should
> not be a detail buried inside discovery. This is an addition, not a
> contradiction, but it changes the shape of the stage and needs confirmation.

---

## 1. Stage goal

Stage 4 takes many connected episodes and finds the process that actually holds
across them: which steps happen nearly every time (the backbone), which happen
sometimes and under what conditions (branches), and which happened once and are
probably a mistake rather than part of the process. It produces a readable map
that spans applications, with the cross-application links from Stage 3 shown as
evidenced connections rather than assumed ones. **This is the least novel stage in
the project and should be built that way** — the algorithms are decades of
established science available in PM4Py, and the architecture's own instruction is
to investigate which existing method fits our data, not to invent the maths. The
work here is choosing correctly, measuring honestly, and refusing to produce a map
when there isn't enough data to support one.

---

## 2. Phases

Eight phases. 4.1–4.2 prepare the data (and 4.2 is where most of the risk is),
4.3–4.5 do the mining and measure it, 4.6–4.8 make it cross-application, explain
the branches, and accept.

---

### Phase 4.1 — Episode grouping

**Goal.** Separate "these are all loan reviews" from "these are complaint
investigations" before mining, so we don't average two different processes into
one meaningless map.

**Build steps**

1. **Flatten overlapping episodes first.** Stage 2 permits overlap (interleaved
   work); most miners require disjoint cases. Implement the flattening rule as an
   explicit, configurable choice — duplicate shared events into both cases, assign
   to the dominant case, or exclude them — and **record which rule was used in the
   output**, since each biases results differently. *(This is OQ-9; see §4.)*
2. **Baseline grouping by attributes**, as the architecture specifies: the set of
   applications touched, the identifier class involved (from Stage 2's
   catalogue), and the episode's terminal action. Cheap, explainable, probably
   right most of the time.
3. **Upgrade arm: HDBSCAN** over episode feature vectors (application set,
   activity multiset, duration, event count, link-tier profile from Stage 3).
   - *Why HDBSCAN over DBSCAN:* it sweeps epsilon continuously and extracts a
     stable flat clustering, so it finds clusters of differing densities and is
     **markedly less sensitive to parameter tuning**. DBSCAN's single `eps` must
     be guessed, and a wrong guess silently merges or shatters groups.
   - *Why not k-means/agglomerative-with-k:* both need the number of process types
     specified in advance, which is precisely what we are trying to discover.
   - *Why HDBSCAN's noise label is a feature, not a flaw:* some episodes genuinely
     are one-offs, and forcing them into a cluster corrupts that cluster's map.
4. **Add an order-aware distance** — Levenshtein (edit) distance over activity
   sequences — as an additional feature or a second clustering arm. Attribute
   vectors throw away sequence, and sequence is what distinguishes two processes
   that use the same applications in different orders.
5. **Name each group from evidence**: dominant applications, dominant identifier
   class, dominant terminal action. Groups must be human-nameable or they are not
   usable in Stage 6.

**Reuse call.** Reuse `scikit-learn` / `hdbscan` (pin and **verify availability
and licence**). Grouping logic is custom but thin.

**Expected output.** Episode groups with names, sizes, and membership confidence;
a flattening report stating how many episodes overlapped and how they were split.

**Validation checkpoint**

- On a synthetic corpus containing **two deliberately different processes that
  share applications** (e.g. loan review and complaint investigation, both using
  LoanDesk + DocVault), grouping must separate them with ≥ 0.85 adjusted Rand
  index. Attribute grouping is expected to fail this test and HDBSCAN to pass it —
  **if attribute grouping passes too, use it and drop the clustering.**
- Every group is nameable by a human from its evidence summary alone.

---

### Phase 4.2 — Event abstraction (raw UI events → process activities)

**Goal.** Turn `click on btnSearch in window "DocVault — Search"` into
`Search for loan document`. **This phase carries more risk than any other in
Stage 4** — get it wrong and every subsequent metric measures the wrong thing
while looking perfectly healthy.

**Build steps**

1. **Screen-based abstraction as the primary rule.** An activity is
   `(application, screen identity, action class)`, where screen identity comes
   from Stage 1's window title pattern plus the set of `element.path_hash` values
   present, and action class is one of: *open/navigate*, *read/inspect*,
   *search/query*, *enter data*, *transfer (copy/paste)*, *decide (terminal
   action)*.
   - *Why screen-based:* deterministic, explainable, built from what Stage 1
     already captures, and it maps onto how people describe their own work.
   - *Why not frequency-based pattern mining:* it produces activities with no
     natural names, which is fatal for Stage 6's requirement that a newcomer can
     *read* the output, and it stacks a second layer of statistical inference
     beneath the mining, compounding error invisibly.
2. **Normalise screen identity across sessions.** Window titles usually contain
   the case identifier (`Loan Review — LN-48213`). **Strip identifier values**
   using Stage 2's induced regexes, or every case produces a unique "screen" and
   the map explodes. This one detail will quietly wreck the stage if missed.
3. **Configurable split and merge rules.** One screen can host two activities (a
   dashboard where you both review and approve — split by action class); one
   activity can span several screens (a wizard — merge by sequence signature).
   Both live in an editable config file.
4. **Produce a reviewable activity dictionary:** activity name, defining screen
   and action class, occurrence count, example events. **A domain expert must be
   able to read this list and correct it in one place.**
5. **Collapse repetition** — 14 consecutive scroll/read events in one screen
   become one `read/inspect` activity with a duration, not 14 activities.

**Reuse call.** Build custom. This abstraction depends entirely on Stage 1's
element and window structure, which no library knows about. SmartRPA has an Event
Abstraction component worth reading for its approach, but its target (RPA script
synthesis from one user's routine) differs from ours.

**Expected output**

- `activity_dictionary.yaml` — reviewable and editable.
- Episodes re-expressed as activity sequences.
- An abstraction report: raw events in, activities out, compression ratio.

**Validation checkpoint**

- **Human agreement — the real test.** A domain expert reviews the activity
  dictionary for the scripted scenario and must accept ≥ 80% of activity names as
  "yes, that's a step in this process" without modification. **This is the gate;
  fitness scores mean nothing if the activities are wrong.**
- **Compression sanity:** a 30-minute episode of ~400 raw events should reduce to
  roughly 10–40 activities. Hundreds means too fine (unreadable map); under five
  means too coarse (map says nothing). Both failures are obvious here and invisible
  later.
- **Stability:** the same real-world step performed by three different people
  yields the same activity name ≥ 90% of the time. If it doesn't, the map will
  show three steps where there is one.
- **Identifier-stripping check:** no activity name contains a case identifier
  value. Automated test, zero tolerance.

---

### Phase 4.3 — Frequency analysis: backbone, branches, noise

**Goal.** The architecture's Stage 4 step 2, done with statistics rather than
eyeballing.

**Build steps**

1. For each group, compute per-activity **episode frequency** (in how many
   episodes does it appear at all) and per-transition frequency.
2. **Classify with stated thresholds** *and confidence intervals*:
   - **Backbone:** appears in ≥ 90% of episodes.
   - **Branch:** 10–90%.
   - **Rare/noise:** < 10%.
   Thresholds are configurable; **report Wilson confidence intervals**, because
   "appears in 8 of 12 episodes" is not the same knowledge as "appears in 340 of
   400" even though both are 67% and both look identical in a bar chart.
3. **Enforce a minimum-episode threshold before publishing any map** (provisional:
   30 per group). Below it, emit a "insufficient data" result with the count.
   **Refusing to produce a map is a legitimate and valuable output** — a confident
   map built from 12 episodes of one person's habits is worse than no map.
4. **Characterise branches, don't just count them.** For each branch, test what
   distinguishes episodes that take it: which identifier class, which application,
   which preceding activity, time of day, actor. This is what turns "31% open
   Excel" into "they open Excel *when the income figures disagree*" — and that
   conditional is the genuinely useful finding.
5. **Separate rare-but-real from noise** using the Stage 3 link confidence and
   Stage 2 episode confidence: a rare activity in high-confidence episodes is more
   likely real than one appearing only in low-confidence episodes.

**Reuse call.** `pandas` + `statsmodels` for the intervals. Custom logic, thin.

**Expected output.** Per-group activity/transition frequency tables with
intervals; branch condition hypotheses with support figures; explicit
insufficient-data results.

**Validation checkpoint**

- On the scripted corpus, where the intended process is known by construction,
  the classifier must place every intended core step in "backbone" and every
  intended optional step in "branch". Pass = 100% on core, ≥ 80% on optional.
- A planted one-off mistake (a misclick sequence inserted into one episode) must
  land in "noise" and **must not** appear in the published map.
- With a deliberately small group (10 episodes), the system **refuses** to publish
  and says why.

---

### Phase 4.4 — Control-flow discovery

**Goal.** Produce the actual process model.

**Build steps**

1. **Read the TKDE benchmark properly first** (Augusto et al., 2019 — 12 real-life
   logs, 9 quality metrics). Its abstract's own conclusion is that there is a
   **"strong divergence in performance with respect to the different quality
   metrics used"** — i.e. no universal winner. **Only the abstract was read during
   research; the results table should be read before this phase is built.**
2. **Primary: Inductive Miner – infrequent (IMf)** via PM4Py.
   - *Why:* models are **guaranteed sound free-choice workflow nets**. For a tool
     whose deliverable is a document a human must trust and follow, an unsound
     model — one that can deadlock or that nobody can read — is worse than a
     slightly less accurate sound one.
   - IMf applies filtering in all three steps of Inductive Mining, trading fitness
     for precision, with **one interpretable knob** (the filter threshold) that
     maps directly onto Phase 4.3's backbone/branch/noise distinction.
   - *Known limitation to document:* block-structured process trees cannot express
     every real behaviour, so genuinely unstructured ad-hoc work gets approximated.
     Real QA/QC work may be exactly that — which is why the fitness metric in
     Phase 4.5 matters and must not be waved through.
3. **Comparison arm: Heuristics Miner** — built for noisy logs, but **no soundness
   guarantee**. Run it, report it, and use the comparison to show what soundness
   costs in fitness.
4. **Rejected: Alpha Miner.** No noise handling and it frequently produces unsound
   models on real logs. Real UI logs are nothing but noise. The architecture names
   it as an example of the field, not as a recommendation, and it should not be
   read as one.
5. **Split Miner: evaluate only if availability is confirmed.** It appears
   prominently in the benchmark literature, but **its ranking, licence, and Python
   availability are all unverified**, and PM4Py's listed algorithms do not include
   it. Do not adopt on reputation.
6. **Run several miners and report the trade-off** rather than declaring a winner
   from the literature — that is the honest response to the benchmark's actual
   finding.

**Reuse call.** **Reuse PM4Py directly.** Alpha, Inductive (and variants),
Heuristics and ILP miners are all implemented there. Re-implementing any of them
would be indefensible.

**Expected output.** Per group: a sound process model (Petri net / process tree),
plus models from each comparison arm, plus a directly-follows graph for the
simplest possible view.

**Validation checkpoint**

- **Rediscovery test — the cleanest available.** Generate a synthetic log from a
  *known* process model, mine it, and check the discovered model matches. This is
  possible because the Inductive Miner offers rediscoverability under activity
  completeness. Pass = structural equivalence on the synthetic case.
- Every published model is **sound** (verify programmatically; do not assume it
  because IMf guarantees it — verify that we used IMf correctly).
- The discovered model for the scripted scenario is recognisable to the person who
  wrote the scenario.

---

### Phase 4.5 — Quality evaluation

**Goal.** Measure whether the map actually describes the data, using the field's
standard metrics rather than opinion.

**Build steps**

1. Compute all four standard dimensions via PM4Py:
   - **Fitness** (alignment-based; token replay as the cheap alternative) — can the
     recorded episodes actually be replayed on the model?
   - **Precision** — does the model allow behaviour the log never shows?
   - **Generalization** — will it support unseen but valid traces?
   - **Simplicity** — is it readable?
2. **Prefer alignment-based fitness** over token replay for reported figures;
   token replay is faster but less exact. Use token replay during iteration,
   alignments for anything published.
3. **Report all four together, always.** Optimising any single one is how you get
   a model that scores well and means nothing — a flower model has perfect fitness
   and zero precision.
4. **Set and publish acceptance thresholds per group** *before* looking at the
   results.
5. **Hold out episodes** — mine on 80%, evaluate fitness on the unseen 20%. A model
   that only fits the episodes it was built from has memorised, not discovered.

**Reuse call.** **Reuse PM4Py's conformance suite entirely.**

**Expected output.** A quality table per group per miner; held-out fitness;
published thresholds.

**Validation checkpoint**

- Held-out fitness ≥ 0.80 and precision ≥ 0.70 on the scripted corpus.
- The trade-off between arms is visible and explainable (e.g. Heuristics higher
  fitness, IMf sound and simpler) — a reviewer should be able to see *why* the
  primary was chosen, from the numbers.

---

### Phase 4.6 — The cross-application view

**Goal.** Make the map show what makes this project different: applications as
first-class parts of the process, connected by *evidenced* links.

**Build steps**

1. **Object-centric discovery.** Take Stage 3's OCEL 2.0 log and discover an
   **OC-DFG** (object-centric directly-follows graph) with PM4Py, where objects are
   case identifiers and documents. Object-centric event data is designed for
   events referencing multiple objects with arbitrary cardinality — which is
   exactly the shape of cross-application work.
2. **Annotate transitions with Stage 3 evidence.** Each cross-application
   transition in the map carries: how often it occurred, the dominant evidence tier
   (proven transfer / deliberate selection / observed visibility), and the mean
   link confidence. **A transition supported by copy/paste in 240 episodes is a
   different kind of claim from one supported only by co-occurrence, and the map
   must show that difference** — otherwise Stage 6 loses the evidential honesty
   the whole project is built on.
3. **Show unexplained transitions** from Stage 3 as explicit dashed/unknown edges.
   The map must be able to say "they moved from here to here and we don't know how
   they were connected."
4. **Produce the application-level summary** the architecture asks for: which
   applications, in what order, with what typically carried between them.

**Reuse call.** **Reuse PM4Py's object-centric discovery.** The annotation layer
is custom.

**Expected output.** An OC-DFG plus an application-flow view with evidence
annotations and explicit unknown edges.

**Validation checkpoint**

- The cross-application map for the scripted scenario shows the known
  LoanDesk → DocVault link with tier `proven_transfer`, and shows the Excel
  transition (which the scenario deliberately gives no linking evidence) as
  **unexplained** rather than inventing a connection.
- Every annotated transition's evidence summary traces back to real Stage 3 links.

---

### Phase 4.7 — Variants, branches, and exceptions

**Goal.** Explain the variation instead of averaging it away. The exceptions are
often the point — especially in QA/QC, where the interesting cases are the ones
that don't follow the script.

**Build steps**

1. **Variant analysis:** rank distinct activity sequences by frequency; report
   coverage (how many variants to cover 80% of episodes). A process needing 60
   variants to cover 80% is not really one process, and that is worth saying.
2. **Conditional branch explanation:** for each significant branch, report what
   predicts taking it, with support and confidence. Use a shallow decision tree or
   simple association rules — **explicitly kept shallow so the condition can be
   stated in one sentence** in Stage 6's output.
3. **Rework and loop detection:** where episodes revisit an activity, report it.
   In a QA context rework is a finding, not noise.
4. **Per-actor comparison:** does one person consistently do it differently?
   Report factually, and **flag the sensitivity** — this output can be misused as
   individual performance surveillance, which is both an ethical problem and a
   fast route to losing workforce consent. Aggregate by default; per-actor only on
   explicit request.

**Reuse call.** PM4Py for variants; `scikit-learn` for shallow trees.

**Expected output.** Variant table with coverage; branch conditions in plain
language; rework findings; optional actor comparison.

**Validation checkpoint**

- On the scripted corpus, the deliberately planted conditional branch (Excel is
  opened *when the income figures disagree*) must be recovered with its condition
  stated correctly. **This is the headline capability of the whole stage** — if the
  system can only say "31% open Excel" and never "31% open Excel *because*", it
  produces statistics rather than understanding.

---

### Phase 4.8 — Stage 4 acceptance

**Build steps**

1. Run the full pipeline over the largest available corpus.
2. Publish: group sizes, activity dictionary, models per arm, the four quality
   metrics, held-out fitness, variant coverage, branch conditions, and the
   cross-application map with evidence annotations.
3. **Expert review:** a domain expert reads the map and answers — is this the
   process? What's missing? What's wrong? Record the answers verbatim in
   `research/stage-4-acceptance.md`. **This is the only external validity check
   available**, and it outranks every internal metric.
4. **Failure gallery:** the worst-fitting episodes, with diagnoses.

**Validation checkpoint (Stage 4 exit criteria)**

| Metric | Threshold |
|---|---|
| Held-out alignment fitness | ≥ 0.80 |
| Precision | ≥ 0.70 |
| Discovered models sound | 100% |
| Activity dictionary accepted by expert | ≥ 80% unmodified |
| Backbone steps correct (scripted) | 100% |
| Conditional branch recovered with condition | yes |
| Cross-app transitions carry evidence tiers | 100% |
| Groups below minimum episodes | refused, not published |
| Expert verdict | "recognisably the process, with specific corrections" |

---

## 3. Dependencies

**Needs from Stage 3:** the OCEL 2.0 log; per-episode connected stories with typed
scored links; the established-relationship catalogue; per-episode quality metrics
so low-confidence episodes can be down-weighted or excluded rather than treated as
equal.

**Needs from Stage 2:** episode groups' raw material — bounds, identifier class,
terminal action, confidence, and **overlap flags** (which drive the flattening
decision in Phase 4.1).

**Needs from Stage 1:** `element.path_hash` and window identity — the entire event
abstraction in Phase 4.2 is built on these, which makes Stage 1 Phase 1.3's
element-identity work load-bearing for this stage in a way that isn't obvious.

**Hands off to Stage 5:** the process model (shape); the activity dictionary and
`ui_chrome` vocabulary (language); branch conditions; the cross-application map.
Stage 5 uses **shape + language** together to classify the process type, and both
come from here.

**Hands off to Stage 6:** everything above, plus quality metrics and the
insufficient-data verdicts, so the final document can state its own confidence.

---

## 4. Open questions and risks

### OQ-9 — The flattening rule for overlapping episodes

Stage 2 permits overlapping episodes because interleaved work is real; most miners
require disjoint cases. Duplicating shared events inflates frequencies; assigning
to the dominant episode loses real behaviour; excluding them biases against
multitasking. **Needs a decision, and it should be recorded in every output**,
because it changes the numbers.

### OQ-10 — Minimum episodes before publishing a map

Proposed floor: 30 per group. **This number has no evidence behind it** and should
be set from observed variance once real data exists. Too low and the tool
publishes one person's habits as organisational truth.

### Risk — event abstraction is where the errors will come from

If activities are wrong, every metric in this stage is measuring the wrong thing
while looking perfectly healthy. Fitness cannot detect a bad abstraction. The only
real defence is the human review in Phase 4.2's checkpoint, which is why it is a
gate rather than a nice-to-have.

### Risk — not enough data

Process discovery needs volume; the Inductive Miner's rediscoverability guarantee
assumes **activity completeness** (every activity appears at least once). A pilot
producing 20 episodes from one person cannot support a meaningful
backbone-vs-noise split. The minimum-episode gate exists for this, and it will be
tempting to lower it to produce a demo. **Don't.**

### Risk — block-structured models may misfit ad-hoc work

IMf produces block-structured process trees, which cannot express every real
behaviour. If QA/QC work is genuinely ad-hoc, fitness will show it. Watch that
number specifically rather than accepting a pretty model.

### Risk — per-actor analysis is a surveillance hazard

Phase 4.7 can compare individuals. That is one config flag away from a
productivity monitoring tool, which would both breach the trust the capture layer
depends on and likely breach worker-consent commitments. Default to aggregate;
make per-actor an explicit, logged request.

### Judgment calls a reviewer should re-examine

- **Adding the event-abstraction phase** — a genuine addition to the architecture.
- **IMf over Heuristics Miner** — soundness prioritised over raw fitness, on the
  grounds that the deliverable is a document a human must trust and follow.
- **Refusing to publish below a data threshold** — deliberately conservative, and
  it will be commercially unpopular in exactly the situations where it matters.
- **Screen-based abstraction over pattern mining** — explainability prioritised
  over statistical fit, because Stage 6's whole purpose is readability.
