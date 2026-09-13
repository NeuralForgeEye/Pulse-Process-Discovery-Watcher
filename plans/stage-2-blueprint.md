# Stage 2 Blueprint — Finding where one task starts and ends (episode segmentation)

**Source of truth:** `plans/pulse-architecture.md`, Stage 2.
**Cross-cutting controls:** `plans/platform-architecture.md` — binding.
**Research backing:** `research/stage-2-episode-segmentation.md`, and
`research/deployment-sensing-and-data-controls.md`.
**Plain-English version:** `manual-readable/stage-2.md`.
**Status:** blueprint only — no implementation code has been written.

> **A conflict the hash-at-capture decision created, and its fix.** Phase 2.3
> originally scored identifier candidates partly by inspecting the *value* —
> character pattern, length, format stability. With identifiers hashed at the
> point of capture, those values no longer exist downstream, so that scoring is
> impossible as written.
>
> **Fix: extract the shape features at capture time, before hashing**, and store
> them beside the hash — a masked shape (`AA-99999`), length, character class.
> Cardinality, cross-application appearance and per-episode uniqueness are all
> computable from hashes alone, and field-label matching uses structural text
> that stays readable. Identifier discovery therefore still works, on shape
> metadata rather than values. **This requires a Stage 1 Phase 1.1 schema
> addition** (`content.value_shape`, `content.value_length`,
> `content.value_charclass`) — recorded here so the dependency isn't lost.
>
> **The residual leak, stated plainly:** a shape mask reveals an identifier's
> *format*. Formats are rarely secret, but for a low-cardinality field a shape
> plus surrounding context could narrow the possible values. Worth an InfoSec
> opinion rather than an assumption on my part.

---

## 1. Stage goal

Stage 2 turns Stage 1's undifferentiated stream into **episodes**: bounded
groups of events, each representing one complete handling of one case. This is
the step that does by signal what SKAN does by having a human pick a video
segment. Its output is what makes every later stage possible — Stage 3 links
applications *within* an episode, Stage 4 compares episodes against each other,
and both produce garbage if episodes are wrong. The stage must also be honest
about what it could not segment: real days contain email, interruptions, and
work inside applications Stage 1 cannot read, and forcing those into the nearest
episode would corrupt Stage 4's statistics with steps that were never part of the
process. **Per the research log, segmentation of UI logs is a crowded research
area with at least four published approaches — this stage is engineering, not
invention, and should be judged on accuracy and honesty rather than originality.**

---

## 2. Phases

Eight phases. Phase 2.1 builds the measuring stick before anything is measured,
which is the only way the later phases can be judged.

---

### Phase 2.1 — Episode data model and the labelled ground-truth set

**Goal.** Define what an episode *is*, and build a hand-labelled dataset to
evaluate every segmenter against. **Nothing else in Stage 2 can be honestly
evaluated until this exists.**

**Build steps**

1. **Define the episode record:**

   | Field | Notes |
   |---|---|
   | `episode_id` | UUID |
   | `actor_id`, `session_id` | inherited from Stage 1 |
   | `t_start`, `t_end` | monotonic bounds |
   | `event_ids` | ordered members (may overlap other episodes — see step 3) |
   | `anchor` | `{type: identifier \| structural \| changepoint, value_hash?, evidence}` |
   | `method` | which segmenter produced it (`identifier`, `rule`, `pelt`, `merged`) |
   | `confidence` | 0–1, with the contributing signals listed |
   | `boundary_evidence` | what marked the start and end, in words, for review |
   | `apps_touched` | set of applications |
   | `quality_flags` | `contains_blind_gap`, `contains_host_down`, `low_confidence`, `overlapping` |

2. **Define the residue set.** Events belonging to no episode are labelled and
   retained, never discarded and never force-fitted. The residue proportion is a
   reported metric.
3. **Decide the overlap rule.** Episodes **may overlap** (interleaved work is
   real). Downstream consumers that need disjoint cases flatten at the Stage 4
   boundary, not here. *(This is open question OQ-7 — see §4.)*
4. **Compare against the published UI-log data model.** Read *A Reference Data
   Model for Process-Related User Interaction Logs* ([arXiv 2207.12054]) and
   record where our Stage 1 schema and episode model agree and differ. Free
   interoperability if we align; a documented reason if we don't.
5. **Build the ground-truth set.** Three sources, in descending order of value:
   - **Scripted:** the Stage 1 Phase 1.9 dress rehearsal, where the case
     boundaries are known by construction because the scenario was scripted.
     This is the primary evaluation set.
   - **Synthetic-hard:** generate variants that stress the failure modes —
     interleaved cases, an abandoned case, a case spanning a lunch break, a case
     worked partly inside a `blind` application, two cases sharing one identifier.
   - **Human-labelled real:** a person watches/reads a real captured session and
     marks boundaries. Expensive; do a small amount and treat it as the
     acceptance set, kept separate from anything used for tuning.
6. **Build the annotation format and a minimal labelling tool** — a timeline view
   with "boundary here" marking, exporting `{session_id, boundary_times[],
   case_labels[]}`.

**Expected output**

- `schema/pulse-episode.v1.schema.json`
- `fixtures/ground-truth/` with at least: 1 scripted session (≥ 8 known cases),
  5 synthetic-hard sessions, 1 human-labelled real session.
- A labelling tool, however crude.

**Validation checkpoint**

- **Inter-annotator agreement:** two people independently label the same real
  session. Pass = boundary agreement ≥ 0.8 (Cohen's κ or boundary-F1 within a
  ±30 s tolerance). **If humans cannot agree where cases start, no algorithm can
  be held to a higher standard — and that result would itself be a finding worth
  logging rather than a failure to hide.**
- **Round-trip:** ground-truth files load, validate against the schema, and
  reproduce identical boundary lists.

---

### Phase 2.2 — Timeline enrichment (building the signals)

**Goal.** Turn the raw event timeline into the derived signals every segmenter
needs, computed once and reused.

**Build steps**

1. **Inter-event gap series** per actor: the distribution of time between
   consecutive events, per application-set and per hour-of-day.
2. **Learn the inactivity threshold** rather than hardcoding one. Fit the gap
   distribution and take a high percentile (start with p95) or the knee of the
   curve. **Do not hardcode 30 minutes**: that industry-standard number traces to
   Catledge & Pitkow's 1995 measurement of dial-up browsing (9.3 min mean + 1.5
   SD = 25.5, rounded to 30). It has no relationship to how a QA reviewer pauses.
   Store the learned value inside each episode so the result stays explainable.
3. **Application-switch series:** switches per minute, bucketed (default 10 s).
4. **Vocabulary-churn series:** how much the set of observed `element.path_hash`
   values changes between consecutive windows (Jaccard distance). A large churn
   means the person moved to a different kind of screen — the strongest purely
   behavioural boundary signal.
5. **Terminal-action lexicon.** Build a list of decision-ending UI labels from
   the `ui_chrome` text Stage 1 retains in clear: Approve, Reject, Submit, Save
   and Close, Complete, Sign Off, Send, Finish. Seed it manually, then **expand
   it by frequency analysis** — labels that repeatedly precede a long gap or an
   identifier change are terminal-action candidates. Keep it a reviewable data
   file, not code.
6. **Gap-ledger join.** Attach Stage 1's `idle` / `blind` / `host_down`
   classification to the timeline. **`blind` must never be treated as a boundary
   candidate** — it means we went deaf, not that work stopped. Conflating them is
   the single most damaging mistake available in this stage.

**Reuse call.** `numpy`/`pandas` for the series; nothing exotic. Build custom —
these are project-specific derived features, not a library-shaped problem.

**Expected output**

- An enrichment module producing, per session: gap series, learned thresholds,
  switch series, churn series, terminal-action hits, and the joined gap ledger.
- `config/terminal-actions.yaml` — reviewable, editable.

**Validation checkpoint**

- On the scripted session, the learned inactivity threshold must fall between the
  longest known intra-case pause and the shortest known inter-case pause. If no
  such value exists, that is a **real finding** — it means inactivity alone cannot
  separate these cases, which justifies the identifier-anchored primary design.
  Log it either way.
- Terminal-action lexicon recall: ≥ 90% of the scripted cases' known final
  actions are matched by the lexicon.
- Zero `blind` regions appear in the boundary-candidate list.

---

### Phase 2.3 — Identifier discovery and normalisation

**Goal.** Work out which captured values are *case identifiers* — the anchors the
primary segmenter runs on. This phase carries the most risk in Stage 2.

**Build steps**

1. **Candidate generation.** For every captured value (from `content` and
   `context`), compute: character pattern (letters/digits/separators), length
   stability, cardinality across the corpus, how many distinct applications it
   appears in, how many distinct screens, and whether it appears in a field whose
   label matches identifier-ish words (ID, No., Number, Ref, Case, Claim, Loan).
2. **Score candidates as identifiers** using explicit, inspectable rules:
   - **high cardinality** (many distinct values) but **low repetition per
     episode-candidate** — an identifier appears in many cases but takes a
     different value each time;
   - **stable format** across occurrences (regex-learnable);
   - **appears in ≥ 2 applications** — the strongest signal, and the one that
     matters most for Stage 3;
   - **not** a date, currency amount, status word, or person name (exclude via
     pattern and via the Stage 1 PII classification).
   Keep this a scored rule set, **not a classifier**. It must be explainable to a
   domain expert who will say "no, that's the branch code, that's not the case
   key" — and that correction must be a one-line config change.
3. **Learn the format.** For each accepted identifier class, induce a regex
   (e.g. `LN-\d{5}`). Use it to catch occurrences the exact-value match misses —
   for example the same ID rendered as `LN 48213` or `ln48213`.
4. **Normalise before matching:** case-fold, strip separators and whitespace,
   optionally strip a known prefix. Hash *after* normalising, so `LN-48213` and
   `ln 48213` produce the same `value_hash`. (This is what preserves Stage 3
   linking under the privacy-preserving mode — see Stage 1 Phase 1.8.)
5. **Handle the sticky-identifier problem explicitly.** An ID pinned on a
   dashboard or a window title all day would swallow the whole session into one
   episode. Detect candidates whose occupancy exceeds a threshold (default: any
   single value present for > 40% of the session) and demote them from anchor
   duty, flagging them for review.
6. **Produce an identifier catalogue** per actor/corpus: the accepted classes,
   their induced regexes, their occurrence counts, their application coverage,
   and the rejected candidates **with the reason for rejection** — a domain expert
   reading the rejects is the cheapest possible bug-finder.

**Reuse call.** Build custom. This is close to "column type inference" in data
profiling, but the discriminating signals here (cross-application appearance,
per-episode uniqueness) are specific to our problem. Generic entity recognisers
(including Presidio) find *PII*, not *case keys* — different target. Presidio is
still used here in the negative direction: to **exclude** person names and other
PII from the candidate pool.

**Expected output**

- `identifier_catalogue.json` per corpus.
- A normalisation + hashing function shared with Stage 3.
- An occurrence index: `value_hash → [event_id, …]` with timestamps and apps.

**Validation checkpoint**

- **Precision/recall against the scripted set,** where the true case keys are
  known by construction: pass = recall ≥ 0.9 on the true identifier class, and
  **precision ≥ 0.8** on the accepted-candidate list (some false positives are
  tolerable because a human reviews the catalogue; missing the real key is not).
- **The sticky test:** plant a value that persists all session. It must be
  detected and demoted, not used as an anchor.
- **The normalisation test:** the same ID written five different ways
  (`LN-48213`, `ln 48213`, `LN48213`, ` LN-48213 `, `lN-48213`) must produce one
  hash. Five different IDs must produce five.
- **Coverage reality check:** report what fraction of the corpus's activity is
  covered by *any* accepted identifier. **If that is below ~60%, stop and
  escalate** — the primary design assumption is not holding, and the correct
  response is a rethink (which also weakens Stage 3), not a workaround.

---

### Phase 2.4 — Baseline rule segmenter (the scientific control)

**Goal.** Build the simplest defensible segmenter, so every later, cleverer
method has something honest to beat.

**Build steps**

1. Cut a new episode when **any** of: an inactivity gap exceeds the learned
   threshold; a terminal action from the lexicon occurs (cut *after* it); or the
   `host_down` gap ledger says capture stopped.
2. Never cut on a `blind` gap.
3. Apply minimum/maximum episode duration sanity bounds (configurable, derived
   from the ground-truth set — not invented).
4. Emit episodes with `method = "rule"` and a confidence derived from which
   signals fired.

**Reuse call.** Build custom — it is ~100 lines and exists to be a control.
Importing a framework for this would be absurd.

**Expected output.** A working segmenter and its scores on the ground-truth set.
**This is the number every later phase must beat, and the number quoted if
someone asks "how much did the clever part actually buy you?"**

**Validation checkpoint**

- Runs end to end on all ground-truth sessions and produces a full metric row
  (boundary F1 at ±30 s, episode purity, residue %).
- **Record the score. Do not tune it to look bad or good.** A control that has
  been quietly nerfed makes every later comparison meaningless.

---

### Phase 2.5 — Identifier-anchored segmenter (primary)

**Goal.** Build episodes from observed identifier occurrences: the span over
which a case key is present *is* the episode.

**Build steps**

1. For each identifier value hash, collect all occurrences across the session
   (from Phase 2.3's index).
2. **Build the span.** Start at first occurrence; extend while occurrences
   continue within a *continuation window* (learned, not fixed). Close the span
   when a terminal action for that value occurs, or when the continuation window
   lapses, or the session ends.
3. **Extend the boundary to capture the run-up.** Sam opens LoanDesk, navigates,
   *then* the ID becomes visible — the navigation is part of the case. Extend the
   start backwards to the preceding boundary candidate (window activation or the
   end of an idle gap), capped by a learned maximum. **Record the extension as
   inferred**, distinct from the observed span, so Stage 4 can tell the
   difference between what we saw and what we reasonably added.
4. **Allow overlapping spans** — two identifiers active at once means two
   concurrent episodes, which is what actually happened.
5. **Assign non-identifier events to spans** by time containment, with events
   inside an overlap assigned to *both* and flagged `ambiguous_membership` rather
   than arbitrarily picked.
6. Emit with `method = "identifier"` and a confidence reflecting occurrence
   count, application coverage, and whether a terminal action closed the span.

**Reuse call.** Build custom. This is interval construction over an occurrence
index — straightforward code whose difficulty is in the rules, not the
algorithms. No library encodes our rules.

**Expected output.** Episodes anchored on identifiers, with observed vs. inferred
boundary portions distinguished.

**Validation checkpoint**

- **Must beat the Phase 2.4 baseline** on boundary F1 on the scripted set. If it
  does not, the core Stage 2 thesis is wrong and that must be reported, not
  patched around.
- **Interleaving test:** on a synthetic-hard session with two deliberately
  interleaved cases, both must be recovered as separate overlapping episodes with
  purity ≥ 0.9 each. This is the specific capability behavioural segmenters lack
  and the main justification for this design.
- **Run-up test:** on the scripted set, the extended start must land within 15
  seconds of the true case start in ≥ 80% of cases.

---

### Phase 2.6 — Change-point fallback for identifier-less stretches

**Goal.** Segment the parts of the timeline no identifier covers, so those
stretches are not simply lost.

**Build steps**

1. Take the residue regions from Phase 2.5 above a minimum duration.
2. Build the feature matrix from Phase 2.2: app-switch rate, vocabulary churn,
   event rate, and count of distinct applications per window.
3. Run **PELT** from the **`ruptures`** library — exact (not greedy),
   linear-time via its pruning rule, with `min_size` as the minimum episode
   length and a penalty tuned on the ground-truth set only.
   - *Versus binary segmentation:* greedy and approximate; PELT gives the optimal
     segmentation for the same cost model at comparable speed. No reason to
     accept approximation here.
   - *Versus window-based detection:* simpler but needs a window width that
     presupposes episode length — the thing we are trying to learn.
   - **Check the licence before adopting** — believed permissive, *not verified*.
4. **Evaluate DenStream as a comparison arm**, not as infrastructure — the
   published method of Rebmann & van der Aa (CAiSE 2023), whose code is on
   Mannheim's GitLab. **Check its licence first.** If it outperforms PELT on our
   ground truth, revisit the call; if not, we have a documented comparison
   against the state of the art, which is worth having either way.
5. Emit with `method = "pelt"` and a confidence systematically lower than
   identifier-anchored episodes — a statistical boundary is genuinely weaker
   evidence than an observed one, and the confidence should say so.

**Reuse call.** **Reuse `ruptures` directly** — implementing PELT correctly
(including the pruning proof) is a waste of effort when a documented library
exists. The custom part is the feature encoding, which is where the real
judgment lives.

**Expected output.** Episodes over identifier-less regions; a documented
comparison of PELT vs. DenStream on our ground truth.

**Validation checkpoint**

- On synthetic sessions with **identifiers deliberately stripped**, PELT must
  recover ≥ 70% boundary F1 — materially worse than identifier-anchored
  (expected) but materially better than nothing.
- Penalty sensitivity: sweep the penalty and plot F1. **A method whose accuracy
  swings wildly with an unlearnable parameter is not deployable** — if the curve
  has no stable plateau, say so rather than quoting the peak.

---

### Phase 2.7 — Arbitration, confidence, residue, and human review

**Goal.** Merge three segmenters' opinions into one answer, and make the shaky
parts visible instead of invisible.

**Build steps**

1. **Precedence:** identifier-anchored > rule > PELT. Where an identifier episode
   and a rule episode disagree by less than a tolerance, keep the identifier
   bounds and *raise* the confidence (two independent signals agreeing is real
   corroboration). Where they disagree by more than the tolerance, keep the
   identifier bounds and **flag for review** — quiet disagreement is exactly what
   you want surfaced.
2. **Confidence model.** Explicit and additive, not a black box: base score by
   method, plus bonuses for terminal-action closure, multi-application coverage,
   and agreement between methods; penalties for `blind` gaps inside the episode,
   ambiguous membership, and inferred (rather than observed) boundary extension.
   Every episode must be able to *explain its own score in words*.
3. **Residue handling.** Everything unassigned goes to the residue set with a
   reason. Report residue % per session; alarm above a configurable threshold
   (provisional 30%, to be set from real data — it is currently a guess).
4. **Human review tool.** List episodes sorted by ascending confidence, show the
   boundary evidence in plain words ("started when LN-48213 first appeared in
   LoanDesk; ended after clicking Approve"), and allow accept / adjust / split /
   merge. Feed corrections back as new ground truth.
   - The literature supports this: interactive segmentation is an established
     approach (ICSOC 2021), not an admission of failure.
5. **Never silently drop a low-confidence episode.** It is either reviewed,
   or passed downstream carrying its low confidence, and Stage 4 must be able to
   weight by it.

**Expected output**

- The final `episodes` table plus `residue` table.
- A review tool and a corrections file that feeds back into ground truth.

**Validation checkpoint**

- **Calibration:** bucket episodes by predicted confidence and measure actual
  accuracy per bucket against ground truth. Pass = monotonic — higher confidence
  really does mean more accurate. **A confidence score that isn't calibrated is
  worse than no score at all**, because downstream stages will trust it.
- **Review throughput:** a person can review 20 episodes in under 10 minutes
  using the tool. If review is slower than that, it will not happen in practice.

---

### Phase 2.8 — Evaluation and Stage 2 acceptance

**Goal.** Measure honestly, against ground truth, with the baseline in the table.

**Build steps**

1. **Metrics:**
   - **Boundary F1** at ±15 s, ±30 s and ±60 s tolerance (report all three;
     a single tolerance hides the shape of the errors).
   - **Episode purity** — fraction of an episode's events belonging to one true
     case.
   - **Coverage** — fraction of true cases recovered as an episode.
   - **Adjusted Rand Index / NMI** for the event-to-case assignment overall.
   - **Residue %**.
   - **Calibration curve** from Phase 2.7.
2. **Always report all four arms:** baseline rules, identifier-anchored, PELT,
   merged. Quoting only the best number is how a project fools itself.
3. **Ablations** — the questions a skeptical reviewer will ask, answered before
   they ask: without terminal actions; without learned thresholds (fixed 30 min);
   without identifier normalisation; with `blind` gaps deliberately misclassified
   as `idle` (this one should visibly *hurt*, proving the Stage 1 distinction was
   worth building).
4. **Failure gallery.** Collect the worst 10 segmentations and write up *why*
   each failed. This is more useful to the next session than the aggregate score.

**Expected output**

- `research/stage-2-acceptance.md` — metric table across all arms, ablations,
  failure gallery.
- A checked-in segmented dataset — **the input Stage 3 develops against.**

**Validation checkpoint (Stage 2 exit criteria)**

| Metric | Threshold |
|---|---|
| Boundary F1 (±30 s), merged | ≥ 0.85 on scripted, ≥ 0.75 on human-labelled real |
| Episode purity | ≥ 0.90 |
| True-case coverage | ≥ 0.90 |
| Interleaved cases recovered separately | ≥ 0.80 |
| Residue | ≤ 25% of events |
| Confidence calibration | monotonic across buckets |
| Beats the Phase 2.4 baseline | on **every** primary metric |

That last row matters most. **If the identifier-anchored approach does not beat
simple rules, the honest conclusion is that simple rules are enough** — and that
should be reported as the finding, not engineered around.

---

## 3. Dependencies

**Needs from Stage 1:**

1. The ordered timeline (`get_timeline`).
2. The **gap ledger** with `idle` / `blind` / `host_down` distinguished — Stage 2
   cuts on `idle`, must never cut on `blind`, and skips `host_down`.
3. `content.value_hash` on identifier-like values, normalised before hashing.
4. `ui_chrome` text retained in clear, for the terminal-action lexicon.
5. `element.path_hash` for vocabulary-churn features.
6. The Phase 1.9 scripted dataset, whose known case boundaries are Stage 2's
   primary ground truth.

**Hands off to Stage 3:**

1. **Episodes** with bounds, members, anchor identifier, method, and confidence.
2. **Overlap flags** — Stage 3 must know when two episodes ran concurrently, or
   it will mistake interleaving for a cross-application link.
3. **Quality flags** — an episode containing a `blind` gap has missing evidence,
   and Stage 3 must not infer a link across that hole.
4. The **identifier catalogue** and the occurrence index — Stage 3's linking runs
   on exactly this.
5. The **residue set**, so Stage 3 can check whether linking evidence sits in
   unassigned territory (a sign segmentation was too aggressive).

---

## 4. Open questions and risks

### OQ-6 — What counts as a case? *(needs a domain answer)*

Is a case one loan, one *review* of one loan (a loan reviewed twice = two cases),
or one sitting at the desk? This is a business definition that changes what
Stage 4 mines and what Stage 6 reports. Technical work can proceed on the
"one review" assumption, but it should be confirmed by someone who knows the
domain before Stage 4 consumes the output.

### OQ-7 — Overlapping episodes: truthful or inconvenient?

Overlap represents interleaved work honestly, but most process-mining algorithms
in Stage 4 expect disjoint cases. Recommendation: allow overlap here, flatten at
the Stage 4 boundary with the flattening rule recorded. The alternative — forcing
disjoint episodes — buys convenience by introducing silent error.

### OQ-8 — Residue tolerance

What fraction of unassigned events means "broken"? 30% is a placeholder guess and
should be set from real data.

### Risk — the identifier assumption may not hold

The whole primary design rests on a visible, capturable case key existing. If
Phase 2.3's coverage check comes in below ~60%, identifier-anchoring becomes a
fallback, a behavioural method becomes primary, **and Stage 3's evidence base
weakens at the same time** — because Stage 3 links on the same identifiers. These
two failures are correlated, which makes Phase 2.3's coverage number one of the
most important measurements in the whole project. It should be taken early.

### Risk — ground truth may not exist even for humans

If Phase 2.1's inter-annotator agreement comes in low, then "where does a case
start" is genuinely ambiguous for this process, and every accuracy number in this
stage becomes soft. That is a finding to report loudly, not a reason to pick the
labelling that flatters the algorithm.

### Risk — tuning on the evaluation set

Thresholds (inactivity, continuation window, PELT penalty) are tuned on ground
truth. Keep the human-labelled real session **strictly held out** from tuning,
or Stage 2's reported accuracy will be measuring memorisation.

### Judgment calls a reviewer should re-examine

- **Identifier-anchored as primary rather than the published behavioural
  methods.** Justified by our unusual data, but it is a bet against the direction
  of the literature. Phase 2.5's comparison against the baseline and Phase 2.6's
  comparison against DenStream are what make it falsifiable.
- **PELT before DenStream** as the fallback — chosen for cheapness and
  explainability, not superiority. The evaluation arm exists to test that.
- **Confidence as an explicit additive model** rather than a learned one. Less
  accurate in principle; far more debuggable, and debuggability matters more when
  a human is reviewing low-confidence episodes.
