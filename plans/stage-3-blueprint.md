# Stage 3 Blueprint — Connecting the dots across applications

**Source of truth:** `plans/pulse-architecture.md`, Stage 3.
**Cross-cutting controls:** `plans/platform-architecture.md` — binding.
**Research backing:** `research/stage-3-cross-application-linking.md`, and
`research/deployment-sensing-and-data-controls.md`.
**Plain-English version:** `manual-readable/stage-3.md`.
**Status:** blueprint only — no implementation code has been written.

> **Three changes since this was written:**
>
> 1. **Linking runs on HMAC hashes, not values.** All four evidence tiers
>    compare `value_hmac` equality. Nothing is lost: hashing is normalised and
>    token-component hashes are stored, so `LN-48213` still matches a bare
>    `48213`. Term-frequency adjustment counts hash occurrences.
> 2. **Sensor provenance becomes a scoring feature.** A link between two
>    structural (T1/T2) reads is stronger evidence than one involving a
>    computer-vision (T3) reading, because a CV misread can manufacture a false
>    match. Add `sensor_tier` to the Phase 3.5 score, and **never** let a
>    T3–T3 link reach the `proven` band on value equality alone.
> 3. **Phase 3.6 federates cleanly, and that is worth noticing.** Population
>    corroboration needs `(from_path_hash, to_path_hash) → count` — a pair of
>    one-way hashes and an integer, containing no content. That is already a
>    pattern-level summary, so the mechanism that gives Pulse its distinctive
>    capability is also the one that survives the federation constraint. It was
>    not designed for that; it happens to fit.

> **Read §4 (OQ-3a) before building.** The research found that endpoint DLP products
> already track copy→paste across applications *with content*, and that Leno et
> al. (2020) published UI-log-based discovery of data transfers between
> applications. The architecture's expectation that this stage is "least likely
> to already exist" is **partly wrong**. What remains distinctive is narrower and
> is specified in §2, Phase 3.6.

---

## 1. Stage goal

Stage 3 takes one episode — a bounded set of events across several applications —
and works out **how those applications were actually connected**: which value
moved from where to where, on what evidence, and how strongly that evidence
supports the claim. Its output is a single connected account of the episode
("opened the record in LoanDesk, read the loan ID, switched to DocVault, searched
using that same ID, reviewed the result"), built only from what was observed, with
**honest gaps left as gaps**. This is the stage that turns "several applications
were used around the same time" into "these applications were part of one piece
of work, and here is the proof." Everything downstream depends on it: Stage 4
mines patterns over these connected accounts, and Stage 6 reports them. It is
also the stage where the project's claim to be doing something different from
click-counting actually has to hold up.

---

## 2. Phases

Eight phases. 3.1–3.3 build the certain parts, 3.4–3.6 handle the uncertain
parts honestly, 3.7–3.8 assemble and measure.

---

### Phase 3.1 — Link model, evidence taxonomy, and ground truth

**Goal.** Define what a link *is*, what evidence classes exist, and build the
labelled set everything is scored against.

**Build steps**

1. **Define the link record:**

   | Field | Notes |
   |---|---|
   | `link_id` | UUID |
   | `episode_id` | owning episode (may be two, if concurrent) |
   | `from_event_id`, `to_event_id` | the two endpoints |
   | `from_app`, `to_app`, `from_element`, `to_element` | including `path_hash` for both |
   | `value_hash` | normalised, from Stage 2's identifier work |
   | `evidence_tier` | `proven_transfer` \| `deliberate_selection` \| `observed_visibility` \| `co_occurrence` |
   | `evidence_detail` | what specifically was seen, in words, for review |
   | `direction` | `a_to_b` \| `b_to_a` \| `undirected` |
   | `instance_score` | log-odds from this episode's evidence alone |
   | `population_score` | corroboration from the same field-pair elsewhere (Phase 3.6) |
   | `confidence` | combined, calibrated |
   | `quality_flags` | `spans_blind_gap`, `common_value`, `inferred_direction` |

2. **Fix the four evidence tiers**, matching the architecture exactly:
   - **Tier 1 `proven_transfer`** — a copy in one application followed by a paste
     in another, paired by Stage 1 Phase 1.5 with the clipboard sequence number.
     This is proof, not inference.
   - **Tier 2 `deliberate_selection`** — the value was highlighted (Stage 1 Phase
     1.4) and subsequently appears elsewhere. Strong: highlighting is deliberate.
   - **Tier 3 `observed_visibility`** — the value was on screen (captured in a
     Stage 1 `context` snapshot) shortly before appearing elsewhere. Reasonable
     inference, not proof.
   - **Tier 4 `co_occurrence`** — same value in two applications, nothing else.
     **Never admissible alone**; only via Phase 3.6's population promotion.
3. **Define `unexplained_transition`** as a first-class record: the person moved
   from application A to application B with no admissible linking evidence. The
   architecture demands honest gaps; this is the record type that makes them
   visible instead of absent.
4. **Build ground truth.** Extend the Stage 1 Phase 1.9 scripted scenario: the
   script knows which value it moved, from where, to where, and by what means.
   Add adversarial cases — the same value appearing coincidentally in two
   unrelated applications; a value typed from memory (a real link with *no*
   digital evidence, which we must correctly report as unexplained rather than
   invent); a value transformed in transit (`LN-48213` → `48213`).

**Expected output.** `schema/pulse-link.v1.schema.json`; a ground-truth link set
with ≥ 50 known links across all four tiers plus ≥ 10 adversarial cases.

**Validation checkpoint**

- Ground truth loads and validates; every link in it is reproducible from the
  captured events by a human inspecting the timeline. **If a human cannot justify
  a ground-truth link from the evidence, it does not belong in ground truth.**

---

### Phase 3.2 — Candidate generation (blocking)

**Goal.** Find the pairs worth scoring, without comparing everything to
everything.

**Build steps**

1. **Block on normalised value hash.** Two events are candidates if they share a
   `value_hash` (from Stage 2 Phase 2.3's normalisation) and occur in *different
   applications* within the same episode, or within two concurrent episodes.
   - This is **blocking**, standard practice in record linkage: comparing all
     event pairs is quadratic and pointless when the vast majority share no value.
2. **Add a near-match block** for transformed values: same normalised token core
   (`LN-48213` vs `48213`), using the regexes induced in Stage 2 Phase 2.3. Leno
   et al. (2020) observed that cross-application transfers "typically involve
   copying alphabetic and numeric tokens separately" — tokenise accordingly rather
   than relying on whole-string equality.
3. **Compute term frequency per value** across the whole corpus. This feeds the
   scoring in Phase 3.5 and is what prevents the value `0`, `N/A`, or today's date
   from generating thousands of worthless candidates.
4. **Cap and report.** If any single value generates more than *N* candidates
   (default 100), flag it as a **common value** and down-weight rather than
   dropping it silently.

**Reuse call.** Build custom, but **borrow the record-linkage vocabulary and
technique** (blocking, term-frequency adjustment). Splink implements these for
table records; our unit is an event pair, so the concepts transfer but the code
does not.

**Expected output.** A candidate table with tier-relevant features attached,
plus a corpus-wide value frequency table.

**Validation checkpoint**

- **Recall:** ≥ 99% of ground-truth links survive blocking. Blocking that drops
  true links is unrecoverable downstream — this metric matters more than
  precision here.
- **Efficiency:** candidate count scales roughly linearly, not quadratically,
  with episode size. Measure on a session with 10× the events.
- **Common-value handling:** a planted junk value (`0`) appearing 500 times is
  flagged, not silently dropped and not allowed to dominate.

---

### Phase 3.3 — Tier 1: proven transfers

**Goal.** Turn Stage 1's copy/paste pairs into links. The certain part.

**Build steps**

1. Take `clipboard_copy` / `clipboard_paste` pairs with their `pair_id` and
   `pair_confidence` from Stage 1 Phase 1.5.
2. Emit a link where source and destination applications differ. Direction is
   **known** here — copy is the source, paste the destination.
3. Carry Stage 1's pairing confidence through; a pair matched only by the Ctrl+V
   shortcut without a value match is weaker than one matched by both, and the
   link score must reflect that rather than flattening it.
4. Handle the **same-application** case by recording it but excluding it from
   cross-application linking — it is still useful to Stage 4 as a within-app step.
5. **Note the prior art in the code comments and in Stage 6's output.** Endpoint
   DLP products already do source-app → destination-app clipboard tracking with
   content. We should not describe this tier as novel anywhere.

**Reuse call.** Nothing to reuse — this is a transformation of our own Stage 1
output. The mechanism is well-trodden; the code is ours and trivial.

**Expected output.** Tier-1 links with known direction.

**Validation checkpoint**

- **100%** of ground-truth Tier-1 links recovered with correct direction. This
  tier is deterministic; anything less than perfect indicates a Stage 1 pairing
  defect, and the fix belongs there, not here.
- Zero Tier-1 links asserted where no clipboard pair existed.

---

### Phase 3.4 — Tiers 2 and 3: selection and visibility evidence

**Goal.** Handle the links where something was clearly observed but nothing was
proven.

**Build steps**

1. **Tier 2 (selection).** A `text_selected` event carrying value V in app A,
   followed within a learned window by V appearing in app B (typed, pasted from
   elsewhere, or present in a `field_value_changed`). Require Stage 1's
   `source = "uia_textpattern"` for full weight; `inferred_selection` (the
   drag-heuristic fallback) gets reduced weight. **The honesty labelling built in
   Stage 1 Phase 1.4 pays off precisely here** — without it these two cases would
   be indistinguishable.
2. **Tier 3 (visibility).** V appeared in a `context` snapshot in app A, then
   appeared in app B within the window. Weaker: the person may never have looked
   at it.
3. **Learn the time window** from Tier-1 data — measure the observed distribution
   of copy→paste intervals in this corpus and use a high percentile. Do not invent
   a number. This is a nice property of the tier structure: the certain tier
   calibrates the uncertain ones.
4. **Order the tiers as one feature, not three.** A copy is usually preceded by a
   selection, which is preceded by visibility. Scoring them as independent
   evidence would triple-count one act. Each candidate gets **one** tier: the
   strongest applicable.
5. **Penalise crossing a `blind` gap.** If the interval between A and B contains a
   Stage 1 `blind` region, the person may have done something we cannot see, and
   the inference is weaker. Flag and down-weight.

**Reuse call.** Build custom. Leno et al. (2020) solve an adjacent problem
(inferring the *transformation* applied to a transferred value) and their
tokenisation insight is worth borrowing in Phase 3.2, but their goal — synthesising
RPA scripts — is not ours, and their assumption of a known routine does not hold
here.

**Expected output.** Tier-2 and Tier-3 candidate links with features attached.

**Validation checkpoint**

- **Adversarial test:** in the scripted scenario, a value the person typed *from
  memory* (no selection, no copy, never visible) must produce **no link above
  threshold** — it must appear as an `unexplained_transition`. Inventing a link
  here is the specific failure mode this stage must not have, because it is
  indistinguishable from success unless you test for it.
- **Coincidence test:** the same value appearing in two genuinely unrelated
  applications must score below threshold once term-frequency adjustment applies.
- Tier assignment is unique: no candidate carries two tiers.

---

### Phase 3.5 — Scoring and calibration

**Goal.** Turn evidence into a number that means something.

**Build steps**

1. **Additive log-odds score.** `score = prior + w(tier) + w(term_frequency) +
   w(time_proximity) + w(element_role_plausibility) + penalties`. Log odds
   because they add meaningfully — this is the core idea borrowed from the
   **Fellegi–Sunter** record-linkage framework, where match weights are additive
   (prior weight plus per-feature partial weights).
2. **Term-frequency adjustment is mandatory, not optional.** A shared value of
   `LN-48213` (seen twice in the corpus) is near-decisive; a shared value of `0`
   (seen 40,000 times) is worthless. Without this adjustment the whole model is
   dominated by junk. Fellegi–Sunter treats this as standard practice; so should we.
3. **Hand-set the initial weights and write down the reasoning for each.** They
   must be defensible to a domain expert, and they must be in a config file, not
   in code.
4. **Then run EM weight estimation as a measured experiment** — the
   Fellegi–Sunter approach as implemented in **Splink** (open source, EM-based,
   used at national-statistics scale). Compare its calibration against the
   hand-set weights on ground truth. Adopt only if it measurably wins.
   - **Verify Splink's licence and whether it runs on a local DuckDB backend
     before depending on it** — both are believed true but unverified.
   - **Known assumption violation:** Fellegi–Sunter assumes conditional
     independence between comparison features; ours are correlated. This is
     mitigated by step 4 of Phase 3.4 (one ordered tier feature instead of three
     independent ones). Document it rather than pretending it away.
5. **Reject Dempster–Shafer, with the reason recorded.** It is the obvious
   alternative for "combining evidence with uncertainty", and the literature
   documents counter-intuitive results under highly conflicting evidence plus a
   requirement that sources have *equal reliability* — which our design violates
   deliberately, since unequal reliability is the entire point of the tiers.
6. **Calibrate.** Bucket links by score, measure actual precision per bucket
   against ground truth, and publish the calibration curve.

**Expected output.** `config/link-weights.yaml`, a scoring module, a calibration
curve, and a documented comparison of hand-set vs. EM-learned weights.

**Validation checkpoint**

- **Calibration is monotonic** — higher score really does mean more likely
  correct. An uncalibrated confidence is worse than none, because Stage 4 will
  trust it.
- **Precision at the operating threshold ≥ 0.95** for links marked
  high-confidence. Stage 4 amplifies whatever it is given; a wrong link becomes a
  wrong process step that looks authoritative.
- **Ablation:** removing term-frequency adjustment must visibly degrade
  precision. If it doesn't, the corpus is unrealistically clean and the test set
  needs more junk values.

---

### Phase 3.6 — Population corroboration (the distinctive mechanism)

**Goal.** Let strong evidence in some episodes vouch for weak evidence in others —
and do it without circular reasoning.

**This is the mechanism identified in the research log as the most defensible
thing in the project. It is also the easiest to get subtly wrong.**

**Build steps**

1. **Define the field-pair relationship** as the unit of population evidence:
   `(from_element.path_hash, to_element.path_hash)` — e.g.
   `LoanDesk.txtLoanId → DocVault.searchBox`. Stage 1's stable `path_hash` is
   what makes this comparable across people and days.
2. **Pass 1 — establish relationships from strong evidence only.** Over the whole
   corpus, count how often each field-pair is linked by **Tier 1 or Tier 2**
   evidence. A field-pair crossing a support threshold (e.g. ≥ 10 occurrences
   across ≥ 3 actors) becomes an **established relationship**.
3. **Pass 2 — promote weak instances.** A Tier-3 or Tier-4 candidate whose
   field-pair is an established relationship gets a `population_score` boost, and
   may cross the admissibility threshold it could never reach alone.
4. **Keep the two passes strictly separate.** Pass 2's promoted links **must not**
   feed back into Pass 1's counts. Without this rule the system corroborates
   itself and manufactures confidence — the failure mode is a model that gets more
   certain the more it runs, which is indistinguishable from learning until you
   check.
5. **Record both components separately** in every link. A reviewer must be able
   to see "this link is weak on its own but this field-pair is proven 240 times
   elsewhere" — that sentence is the whole justification, and hiding it inside a
   single number destroys it.
6. **Never promote Tier 4 to "proven".** Cap it: co-occurrence plus population
   support reaches `probable`, never `proven`. The architecture is explicit that
   timing-only evidence is "never trusted alone", and a cap is how that survives
   contact with an optimistic implementation.

**Reuse call.** Build custom — nothing found does this. Frequent-pattern mining
libraries could count field-pairs, but the counting is trivial; the difficulty is
entirely in the two-pass discipline and the cap.

**Expected output.** An established-relationship catalogue; links carrying both
score components.

**Validation checkpoint**

- **Circularity test — the important one.** Run Pass 2. Recompute Pass 1 counts.
  They must be **identical**. Any change means feedback has leaked in.
- **Promotion works:** a synthetic corpus where a field-pair is proven by
  copy/paste in 20 episodes and only visible-then-typed in 5 must promote those 5
  above threshold.
- **Promotion is bounded:** a field-pair with *no* Tier-1/2 support anywhere must
  never be promoted, regardless of how often it co-occurs. Test with a planted
  coincidence that co-occurs 500 times.

---

### Phase 3.7 — Episode story assembly

**Goal.** Produce the architecture's stated Stage 3 deliverable: one connected
sequence of steps per episode, with gaps marked as gaps.

**Build steps**

1. Order the episode's events; collapse consecutive same-screen events into steps
   (open, read, search, compare, decide) using element roles and event types.
2. Attach links between steps, annotated with tier and confidence.
3. **Insert `unexplained_transition` markers** wherever the person moved between
   applications with no admissible link. This is required by the architecture and
   is the thing that keeps the output trustworthy: an account with three honest
   holes is worth more than a seamless one that guessed twice.
4. **Emit in two formats:**
   - **OCEL 2.0** for Stage 4 — object-centric event data, where one event
     references multiple objects (case identifier, document, application), which
     is a precise fit for our data and is directly supported by **PM4Py**'s
     object-centric discovery and conformance checking. *Caveat to record: OCEL
     represents which objects an event touches, not how a value moved; our
     evidence tier and direction live in attributes, which is a mild abuse of the
     standard.*
   - **A native link/story table** for Stage 6's human-readable narrative, which
     needs the evidence wording that OCEL has no place for.
5. Include per-episode quality: link count by tier, unexplained transitions,
   mean confidence, blind-gap coverage.

**Reuse call.** **Reuse PM4Py for OCEL 2.0 serialisation** — it supports the
standard's SQLite/XML/JSON exchange formats, and hand-rolling a standard format is
pure downside. The story assembly itself is custom.

**Expected output.** Per-episode connected story; an OCEL 2.0 log; a link table.

**Validation checkpoint**

- **The architecture's own checkpoint, verbatim:** for one episode spanning two or
  more applications, produce a single connected sequence — "opened record in App
  A, read loan ID, opened App B, searched using that same loan ID, reviewed
  result" — built from real evidence, with honest gaps marked as gaps. Verify by
  having a person who watched the scripted session read the generated story and
  confirm it matches what happened.
- The OCEL file loads in PM4Py and an object-centric DFG can be discovered from
  it. (This is a smoke test for Stage 4's viability, taken early and cheaply.)
- Every unexplained transition in ground truth appears as one in the output.

---

### Phase 3.8 — Evaluation and Stage 3 acceptance

**Build steps**

1. **Metrics:** link precision/recall per tier; direction accuracy; unexplained
   transition recall (did we correctly admit ignorance?); **false-link rate**
   (links asserted where ground truth says none — the most damaging error);
   calibration curve; population-promotion precision.
2. **Baselines to beat, both deliberately naive:**
   - *Timing-only:* any two applications used within 30 s are "linked". This will
     have high recall and terrible precision — it exists to show what the evidence
     model actually buys.
   - *Tier-1-only:* copy/paste links exclusively. High precision, low recall. This
     is the honest "what a DLP tool could already tell you" baseline, and the gap
     between it and our full model **is the actual contribution of this stage**.
     Quote that gap explicitly; it is the number that answers "so what is new?"
3. **Ablations:** without term frequency; without population corroboration;
   without blind-gap penalties; with Tier 4 admitted alone (should visibly hurt).
4. **Failure gallery:** the 10 worst false links and the 10 worst missed links,
   each with a written diagnosis.

**Validation checkpoint (Stage 3 exit criteria)**

| Metric | Threshold |
|---|---|
| Tier-1 link precision | 1.00 |
| Overall link precision at operating threshold | ≥ 0.95 |
| Overall link recall | ≥ 0.80 |
| Direction accuracy where direction asserted | ≥ 0.95 |
| False links on adversarial coincidence cases | 0 |
| Unexplained transitions correctly reported | ≥ 0.90 |
| Calibration | monotonic |
| Circularity test (Phase 3.6) | passes exactly |
| Beats Tier-1-only baseline on recall | with precision ≥ 0.95 maintained |

Recall is deliberately set lower than precision. **A missed link makes the map
incomplete; a false link makes it wrong**, and a wrong map that looks confident is
the worse outcome by a wide margin.

---

## 3. Dependencies

**Needs from Stage 2:** episodes with bounds and confidence; overlap flags (two
concurrent episodes must not be mistaken for one linked workflow); quality flags
marking blind gaps; the identifier catalogue and normalisation function; the
value occurrence index; the residue set (to check whether linking evidence sits
in unassigned territory).

**Needs from Stage 1 specifically:** copy/paste pairs with `pair_confidence`;
`text_selected` events with the `uia_textpattern` vs `inferred_selection`
distinction; `context` snapshots; `element.path_hash` — which is what makes
field-pair relationships comparable across people and is the foundation of Phase
3.6.

**Hands off to Stage 4:** an **OCEL 2.0 log** consumable by PM4Py; per-episode
connected stories with typed, scored links; the established-relationship
catalogue; per-episode quality metrics so Stage 4 can weight or exclude
low-confidence episodes rather than treating all episodes as equally trustworthy.

---

## 4. Open questions and risks

### OQ-3a — The novelty finding: read this before claiming anything

Endpoint DLP agents already record the copying application's identity and
inspect content on paste into a different application; this is in granted patents
and shipping products. Leno et al. (2020) published discovery of data transfers
between applications from UI logs, including the transformation applied.
US7693916B2 covers correlating process instance data across applications via
shared identifiers.

**Tier 1 is not new.** What appears to remain is the **combination**: a
calibrated model over explicitly unequal evidence in which individually
inadmissible evidence is promoted by **recurrence of the same field-pair
relationship across a population of episodes**, producing a process-level link
graph rather than a per-event policy decision.

Three caveats, all important: combination claims are the weakest kind; **no full
patent claim text was read** (summaries only); and this is not clearance. If
there is a filing decision, this specific mechanism — not "cross-application
linking" generally — is what should be searched by an attorney.

### OQ-3b — Direction of flow is often unknowable

Evidence frequently proves two applications shared a value without proving which
way it went — both may have read it from a third system. Proposal: assert
direction only on Tier-1/2 evidence, mark `undirected` otherwise. A domain expert
may prefer a different default, and Stage 6's readability depends on this choice.

### OQ-3c — Circular reasoning in population corroboration

The two-pass separation in Phase 3.6 is the only thing preventing the system from
corroborating itself into unwarranted confidence. The circularity test is
mandatory, and this design deserves a skeptical human review **before**
implementation.

### 4.4 Correlated evidence and the Fellegi–Sunter assumption

Fellegi–Sunter assumes conditional independence between features; ours are
correlated by construction. Mitigated by collapsing the tiers into one ordered
feature, but the mitigation should be verified empirically rather than assumed —
if EM-learned weights produce systematically overconfident scores, this is why.

### 4.5 Stage 3 inherits Stage 2's biggest risk

Every tier runs on identifier values. If Stage 2 Phase 2.3 finds that most real
work has no visible, capturable identifier, Tier-1/2 evidence becomes rare, the
model leans on the weakest tiers, and both quality and defensibility fall
together. **That measurement is the leading indicator for this stage and should
be taken as early as possible.**

### 4.6 Judgment calls a reviewer should re-examine

- **Log-odds with hand-set weights before EM-learned weights.** Chosen for
  debuggability over theoretical optimality. Phase 3.5 measures the cost of that
  choice rather than assuming it away.
- **Dempster–Shafer rejected** despite being the textbook answer for uncertain
  evidence fusion — on the documented grounds of counter-intuitive behaviour under
  conflict and its equal-reliability requirement. Worth re-checking if someone on
  the team knows the literature well.
- **OCEL 2.0 as the handoff format**, accepting a mild abuse of the standard to
  carry evidence attributes, in exchange for PM4Py's object-centric algorithms in
  Stage 4.
- **Precision prioritised over recall.** A deliberate asymmetry, on the grounds
  that a confidently wrong process map is worse than an admittedly incomplete one.
