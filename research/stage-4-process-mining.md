# Research Log — Stage 4: finding the real process across many episodes

**Stage / Phase:** Stage 4 — process mining
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes; one significant gap in the
architecture identified (§5.1)

---

## 1. Question being investigated

The architecture is explicit that this stage should reuse established process
mining, not invent it. So the questions are:

1. Which discovery algorithm actually fits cross-application UI data, and what do
   published benchmarks say — not what do I remember them saying?
2. How do we group episodes into "the same kind of task"?
3. **What's missing from the architecture's plan for this stage?**

---

## 2. What was actually checked

**Verified:**

- **Augusto, Conforti, Dumas, La Rosa, Maggi, Marrella, Mecella, Soo, *Automated
  Discovery of Process Models from Event Logs: Review and Benchmark*, IEEE TKDE
  31(4), 686–705, 2019** ([arXiv 1705.02288](https://arxiv.org/abs/1705.02288),
  [dataset](https://data.4tu.nl/articles/dataset/Data_underlying_the_paper_Automated_Discovery_of_Process_Models_from_Event_Logs_Review_and_Benchmark/12712727/1)).
  Benchmark over **12 publicly available real-life event logs** from the IEEE
  Task Force on Process Mining (7 pre-processed to remove infrequent behaviour)
  and **nine quality metrics**. Its stated motivation: existing methods "have been
  evaluated in an ad-hoc manner, employing different datasets, experimental
  setups, evaluation measures and baselines, often leading to incomparable
  conclusions and sometimes unreproducible results."
  **The abstract's conclusion, quoted:** the results "highlight gaps and
  unexplored tradeoffs in the field, including the lack of scalability of some
  methods and a **strong divergence in their performance with respect to the
  different quality metrics used**."
  ⚠️ **I could not read the full paper** (only the arXiv abstract page). **I did
  not verify which algorithm ranked first.** Any claim that "Split Miner wins" is
  unsupported by what I actually read, and this blueprint does not make it.
- **Inductive Miner – infrequent (IMf / IMi), Leemans et al.** Models discovered
  by IMf are **guaranteed to be sound free-choice workflow nets**. IMf "applies
  log filtering in all three steps of IM, trading fitness for precision while
  discovering sound process models fast", controlled by a **filter threshold
  parameter**. Base Inductive Miner "provides rediscoverability and guarantees
  perfect fitness", rediscovering process trees under an **activity completeness**
  assumption (every leaf occurs at least once in the log). Sources:
  [Unblocking Inductive Miner While Preserving Desirable Properties](https://www.vdaalst.com/publications/p1367.pdf),
  [Locally Optimized Process Tree Discovery](https://leemans.ch/publications/papers/icpmw2024schroder.pdf).
- **PM4Py's available discovery algorithms:** alpha miner, inductive mining
  algorithms, heuristics miner, and **ILP miner**
  ([PM4Py implemented approaches](https://pm4py.fit.fraunhofer.de/implemented-approaches),
  [PM4Py SoftwareX paper](https://www.sciencedirect.com/science/article/pii/S2665963823000933)).
  **Split Miner was NOT confirmed present in PM4Py** by these sources.
- **PM4Py conformance checking:** evaluates log-model quality via **fitness**
  (token-based replay *or* alignments), **precision**, **generalization**,
  **simplicity**, plus anti-alignments and multi-alignments. Definitions
  confirmed: fitness = degree to which logged traces can be replayed on the
  model; precision penalises extra behaviour the model allows but the log never
  shows; generalization = support for unforeseen traces; simplicity =
  understandability. ([PM4Py evaluation docs](http://pm4py.pads.rwth-aachen.de/documentation/conformance-checking/evaluation-log-model/))
- **HDBSCAN vs DBSCAN vs agglomerative for trace clustering.** DBSCAN's main
  hyperparameter `eps` "regulates the maximum distance between two points for them
  to be considered of the same neighborhood". HDBSCAN "hierarchically extends
  DBSCAN by sweeping epsilon continuously through the data space, evaluates the
  stability of the resulting clusters, and finally extracts an optimal flat
  clustering, allowing clusters with different densities to be identified
  simultaneously and making the method **markedly less sensitive to parameter
  tuning** than DBSCAN", and it discerns clusters "without prior knowledge of the
  ideal cluster count". Agglomerative hierarchical clustering has been used in
  trace clustering with Maximal Repeat feature sets and with **Levenshtein (string
  edit) distance** as the similarity measure. Sources include
  [Selecting Optimal Trace Clustering Pipelines with AutoML](https://arxiv.org/pdf/2109.00635).
- **Object-centric discovery.** PM4Py fully supports **OCEL 2.0**, including
  object-centric process discovery and conformance checking using Petri nets,
  DFGs and object graphs, and **OC-DFG** discovery. Events in object-centric data
  "can reference multiple objects of varying types with arbitrary cardinality."
  Other tooling: OC-PM (ProM/web), `ocpa` (Python), PM4Py-MDL.

**Recalled, not verified:**

- Split Miner's benchmark ranking, its licence, and whether a maintained Python
  binding exists. **All unverified** — it is named in the blueprint only as
  something to evaluate, never as a recommendation.
- That the Alpha Miner is known to produce unsound models on real logs with
  noise. This is textbook knowledge and I am confident in it, but I did not
  confirm it from a source this session.
- `hdbscan` being available as a maintained Python package (and now in
  scikit-learn). Believed true; pin and verify at implementation time.

**Not checked:**

- The full TKDE benchmark results table — **the single most useful thing to read
  before choosing a miner**, and it should be read properly before Phase 4.4.
- Whether any event-abstraction technique has been validated specifically on
  UI logs at scale.
- Patent claim sets for UiPath's "clustering recorded user tasks into steps /
  extracting repeated step sequences" family (surfaced in the Stage 2 search) —
  **this is the closest commercial prior art to Stage 4 and remains unread.**

---

## 3. Prior art / existing solutions found

| What | Who | Type | Relevance |
|---|---|---|---|
| Alpha, Inductive (+ variants), Heuristics, ILP miners | Process mining field / PM4Py | OSS + decades of literature | **This is the science we reuse.** Nothing to invent |
| Benchmark of automated discovery methods, 12 logs, 9 metrics | Augusto et al., TKDE 2019 | Academic | Tells us there is **no universal winner** — performance diverges strongly by metric |
| Conformance checking (fitness/precision/generalization/simplicity) | PM4Py | OSS | Reuse directly as the quality gate |
| Object-centric discovery (OC-DFG, OC Petri nets) | PM4Py, ocpa, OC-PM | OSS | Reuse — matches the OCEL 2.0 Stage 3 emits |
| Trace clustering (HDBSCAN / agglomerative / edit distance) | Process mining + general ML | OSS + literature | Reuse for episode grouping |
| Clustering recorded user tasks into steps; extracting repeated step sequences | UiPath | Patent family | **Closest commercial prior art to this stage. Claims unread** |
| Concept drift in process mining | [Survey, arXiv 2112.02000](https://arxiv.org/pdf/2112.02000) | Academic | Belongs to Stage 7; noted here so it isn't lost |

**Conclusion:** Stage 4 is the *least* novel stage in the project, and that is
entirely appropriate. The architecture's own note — "the job later is to
investigate which existing method fits our cross-application data best, not to
invent this math from nothing" — is correct and should be followed literally.

---

## 4. Options considered

**Episode grouping:** attribute-based grouping (apps touched, identifier class) ·
feature-vector clustering with HDBSCAN · agglomerative clustering on Levenshtein
distance over activity sequences · no grouping at all (mine everything together).

**Event abstraction (raw UI events → process activities):** screen/window-based ·
frequency-based n-gram patterns · manual mapping · learned/embedding-based.

**Control-flow discovery:** Alpha · Heuristics · Inductive (IM / IMf) · ILP ·
Split Miner · object-centric DFG.

**Quality evaluation:** alignment-based fitness · token replay · precision ·
generalization · simplicity.

---

## 5. Debate — for and against

### 5.1 The gap in the architecture: event abstraction

**This is the most important finding in this log.** The architecture's Stage 4
moves straight from "episodes" to "find which steps appear in nearly every one."
That skips a step which the process-mining literature treats as a hard problem in
its own right: **event abstraction**.

Stage 1 captures things like `click on element "btnSearch" in window "DocVault —
Search"`. That is not a process activity. A process activity is
`Search for loan document`. Between those two sits an abstraction decision, and
**every downstream number depends on it**. Pick it badly and the discovered map is
either an unreadable 400-node hairball (too fine) or a four-box triviality that
tells you nothing (too coarse).

Notably, SmartRPA's pipeline has "Event Abstraction" as one of its five
components — the same conclusion reached independently by people who built this.

**Recommendation: make it an explicit phase (4.2) with its own validation**,
rather than a detail inside discovery. Flagging this as a genuine addition to the
architecture rather than a reinterpretation of it.

**Which abstraction, though?**

**Screen-based (activity = application + screen identity + action class) — for:**
deterministic, explainable, and built entirely from what Stage 1 already
captures (`element.path_hash`, window identity). A domain expert can read the
activity names and immediately say whether they're right. It also maps naturally
onto how people describe their own work ("I open the search screen, then I open
the document view").
**Screen-based — against:** one screen can host several distinct activities (a
single dashboard where you both review and approve), and one activity can span
several screens (a wizard). Screen identity is a proxy for intent, not intent.

**Frequency-based pattern mining — for:** finds recurring action sequences
empirically; doesn't assume screens correspond to steps.
**Frequency-based — against:** produces activities with no natural names, which
is fatal for Stage 6's requirement that a newcomer can *read* the output. It also
adds a second layer of statistical inference beneath the mining, compounding error.

**Call: screen-based abstraction, with configurable split/merge rules and a
human-reviewable activity dictionary.** Explainability wins here because the whole
project's deliverable is a document a human trusts. A pattern-mined abstraction
that improves fitness by 3% but produces activities called `cluster_17` is a net
loss for this product.

### 5.2 Which discovery algorithm

**Alpha Miner — for:** historically important, simple, in every toolkit.
**Alpha — against:** no noise handling, and on real logs it produces models that
are frequently unsound. Real UI logs are *nothing but* noise. Rejected — it is a
teaching algorithm, and the architecture naming it should not be read as a
recommendation.

**Heuristics Miner — for:** explicitly built for noisy real-life logs, frequency
thresholds on arcs, intuitive.
**Heuristics — against:** **no soundness guarantee.** It can produce a model that
deadlocks or that no human can follow. For a tool whose output is meant to be
read and trusted by a person, an unsound model is worse than a slightly less
accurate sound one.

**Inductive Miner – infrequent (IMf) — for:** **guaranteed to produce sound
free-choice workflow nets**, applies filtering in all three steps to trade
fitness for precision, discovers fast, has a single interpretable knob (the
filter threshold) that maps exactly onto the architecture's own
backbone/optional/noise distinction. Rediscoverability results exist under
activity completeness.
**IMf — against:** the block-structured process trees it produces cannot express
every real behaviour, so genuinely unstructured processes get approximated. Real
QA/QC work with ad-hoc jumping between systems may be exactly that. The filter
threshold is also a knob someone has to set, and fitness is deliberately traded
away.

**Split Miner — for:** reported as producing "accurate and simple" models, and
appears prominently in the benchmark literature.
**Split Miner — against:** **I could not verify its benchmark ranking, its
licence, or a maintained Python binding**, and PM4Py's listed algorithms do not
include it. Recommending it on memory would be exactly the failure this repo's
rules exist to prevent.

**Call: IMf as primary, for soundness and the interpretable filter threshold.
Heuristics Miner as a comparison arm. Split Miner evaluated only if availability
is confirmed.** And — critically — **the TKDE benchmark's actual finding is that
performance diverges strongly across quality metrics**, which means the honest
approach is to run several miners on *our* data and report the trade-off, not to
pick a winner from the literature.

### 5.3 Grouping episodes: simple attributes vs. clustering

**Attribute grouping (the architecture's proposal: same apps touched, same
identifier class) — for:** trivial, explainable, and probably right most of the
time. Two episodes that touch LoanDesk + DocVault + Excel and revolve around a
loan ID almost certainly are the same kind of work.
**Attribute grouping — against:** it cannot separate two genuinely different
processes that happen to use the same applications — e.g. a *new loan review* and
a *complaint investigation* both touching LoanDesk and DocVault.

**HDBSCAN on feature vectors — for:** no need to pick the number of clusters,
handles clusters of different densities, and is "markedly less sensitive to
parameter tuning" than DBSCAN. Labels outliers as noise rather than forcing them
into a cluster — which matches reality, since some episodes really are one-offs.
**HDBSCAN — against:** cluster labels are meaningless until a human names them,
and density-based methods can be unstable on small datasets. With 40 episodes it
may produce nothing useful.

**Call: attribute grouping as the baseline; HDBSCAN as the upgrade, evaluated
against it.** Same discipline as Stage 2 — build the simple thing, measure, and
only keep the complex thing if it wins. Use edit distance on activity sequences
as an additional feature, since that captures order, which attribute vectors lose.

### 5.4 Do we even have enough data?

**This is the risk nobody in the architecture mentions.** Process discovery needs
volume. The Inductive Miner's rediscoverability guarantee assumes **activity
completeness** — every activity appears at least once. Frequency-based separation
of "backbone" from "rare noise" needs enough episodes that a 5% branch is
distinguishable from chance.

With 400 episodes across 12 people, this is fine. With 20 episodes from one
person — which is what a pilot will realistically produce first — the "process
map" will mostly reflect that one person's habits, and the backbone/noise split
will be statistically meaningless.

**Call: define and enforce a minimum-episode threshold per group before
producing a map at all**, and report confidence intervals on branch frequencies
rather than bare percentages. Refusing to produce a map is a legitimate and
important output.

---

## 6. Novelty check (required)

**Stage 4 is not novel and should not attempt to be.** Alpha, Heuristics,
Inductive and ILP miners are decades of established science, all available in
PM4Py. Trace clustering is well-studied. Conformance checking is standard.
UiPath holds patents on clustering recorded tasks into steps and extracting
repeated step sequences.

The only thing distinctive here is the **input**: episodes that carry
cross-application links with evidence tiers (from Stage 3) and object-centric
structure. Mining over that produces a map that spans applications with *evidenced*
connections rather than assumed ones. That is a consequence of Stages 1–3, not an
independent contribution.

**Is it "just apply AI to X"? No — but only because we are choosing not to.**
The tempting move here is "feed the episodes to an LLM and ask it to describe the
process." That would be exactly the failure mode CLAUDE.md warns about: no
guarantees, no conformance metrics, no way to tell a hallucinated step from a real
one, and no defensibility. The established algorithms give measurable fitness and
precision. **Use them.**

---

## 7. Conclusion / recommendation

1. **Add an explicit event-abstraction phase** (the architecture's gap), using
   screen-based abstraction with a human-reviewable activity dictionary.
2. **Group episodes by attributes first**, HDBSCAN as a measured upgrade.
3. **Discover with IMf** (sound models, interpretable filter threshold), with
   Heuristics Miner as a comparison arm, and report the trade-offs across metrics
   rather than declaring a winner — because the TKDE benchmark's own conclusion is
   that performance diverges strongly by metric.
4. **Evaluate with PM4Py's conformance suite** (alignment-based fitness,
   precision, generalization, simplicity).
5. **Also discover an object-centric view** (OC-DFG) from Stage 3's OCEL, since
   that is where the cross-application structure actually lives.
6. **Enforce a minimum-episode threshold** and report frequency confidence
   intervals. Refusing to produce a map on thin data is a feature.

**What would change this call:** if screen-based abstraction produces activity
dictionaries a domain expert rejects, the abstraction layer needs rework before
anything else is worth measuring — abstraction errors propagate into every
downstream number and are invisible in the fitness score.

---

## 8. Open items requiring a human decision

1. **Read the TKDE benchmark properly before Phase 4.4.** I read only the
   abstract. Its results table is the single most useful document for this stage,
   and the choice of primary miner should be revisited against it.
2. **Flattening overlapping episodes.** Stage 2 permits overlapping episodes
   (interleaved work). Most miners expect disjoint cases. Someone must decide the
   flattening rule — duplicate shared events into both cases, assign to the
   dominant one, or exclude them — and each choice biases the result differently.
3. **Minimum episodes before publishing a map.** I propose 30 per group as a
   provisional floor. This is a judgment call with no evidence behind it and
   should be set from observed variance.
4. **UiPath's task-mining patent claims are unread**, and they are the closest
   commercial prior art to this stage.
