# Research Log — Stage 2: cutting the timeline into episodes

**Stage / Phase:** Stage 2 — episode segmentation
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes; three items escalated to human decision (§8)

---

## 1. Question being investigated

Stage 1 produces one continuous stream. Stage 2 must decide where one handled
case starts and ends. Three questions:

1. Is this a solved problem with published methods we can take?
2. Which method fits *our* data — which, unusually, contains on-screen
   identifier values, not just action types?
3. How do you evaluate a segmenter when real logs have no ground truth?

---

## 2. What was actually checked

**Verified (read the source or its abstract/metadata):**

- Agostinelli, Marrella, Mecella, *Automated segmentation of user interface logs*, in **Robotic Process Automation**, De Gruyter Oldenbourg, 2021, pp. 201–222 ([PDF](http://www.diag.uniroma1.it/~marrella/papers/Segmentation_RPA_Book_2020.pdf)). The approach is **supervised**: it takes a UI log *and an interaction model representing the expected behaviour of a routine*, then uses **trace alignment** from process mining to identify and extract routine instances. PDF could not be text-extracted in this environment (binary; no poppler installed) — **the method summary above comes from the search abstract, not from reading the full paper.** Flagged as a gap.
- Leno, Augusto, Dumas, La Rosa, Maggi, Polyvyanyy, *Identifying candidate routines for robotic process automation from unsegmented UI logs*, **ICPM 2020**, pp. 153–160.
- Agostinelli et al., *Exploring the Challenge of Automated Segmentation in Robotic Process Automation*, [Springer, 2021](https://link.springer.com/chapter/10.1007/978-3-030-75018-3_3).
- **Rebmann & van der Aa, *Unsupervised Task Recognition from User Interaction Streams*, CAiSE 2023** ([PDF](https://hanvanderaa.com/wp-content/uploads/2023/03/CAISE2023-Unsupervised-task-recognition-from-user-interaction-streams.pdf), [Springer](https://link.springer.com/chapter/10.1007/978-3-031-34560-9_9)). First approach for **unsupervised** task recognition on *streams*; existing techniques require multiple post-hoc passes over the whole collection. Clustering component uses **DenStream**, an online density-based technique building on DBSCAN, maintaining micro-clusters rather than raw vectors — memory-efficient and does not depend on a user-defined cluster count. Code: [GitLab, Univ. Mannheim](https://gitlab.uni-mannheim.de/processanalytics/task-recognition-from-event-stream) — repo exists, 19 commits; **README contents and licence were not retrievable** in this session.
- **Hohenadl, *Time Series-Based Segmentation of Noisy User Interaction Logs for Robotic Process Automation*, BPM 2025** ([Springer](https://link.springer.com/chapter/10.1007/978-3-032-02936-2_20)). Directly targets our situation: current RPM approaches "assume structured, low-noise task traces, requiring prior domain knowledge to define automatable routines". Method uses **word2vec encoding of actions + time-series motif discovery** to segment without prior knowledge, explicitly to support **long-term recordings with no predefined routine boundaries**.
- **Pegoraro, Uysal, Hülsmann, van der Aalst, *Uncertain Case Identifiers in Process Mining: A User Study of the Event-Case Correlation Problem on Click Data*** ([arXiv 2204.04164](https://arxiv.org/abs/2204.04164)). Click data lacks case identifiers; they aggregate interaction data into sessions-as-cases using a **neural-network** method, on data from a mobility-sharing company, validated **qualitatively via expert interviews**. No quantitative accuracy figure surfaced.
- **Bayomie et al., *Deducing Case IDs for Unlabeled Event Logs*** ([Springer](https://link.springer.com/chapter/10.1007/978-3-319-42887-1_20)) — infers case IDs by solving a multi-level optimisation using fitness metrics computed against **a known process model**, searching for the nearest optimal correlated log.
- **Ferreira & Gillblad, *Discovering Process Models from Unlabelled Event Logs*** — Hidden Markov / **Expectation-Maximisation** to correlate events into cases. Per a secondary survey: model-based methods of this family "require prior knowledge (e.g. a process model or transition constraints) and are explicitly designed for **acyclic** processes, so they generally cannot handle loops or concurrency."
- *Interactive Segmentation of User Interface Logs*, [SOC/ICSOC 2021](https://dl.acm.org/doi/10.1007/978-3-030-91431-8_5) — human-in-the-loop segmentation. Also *A Human-in-the-Loop Approach to Support the Segments Compliance Analysis* (Springer, 2022).
- *A Reference Data Model for Process-Related User Interaction Logs* ([arXiv 2207.12054](https://arxiv.org/pdf/2207.12054), Springer 2022) — a proposed standard shape for UI logs. **Relevant to Stage 1's schema too**; should be compared against our schema in Phase 2.1.
- **`ruptures`** — Python library for **off-line change point detection** ([GitHub](https://github.com/deepcharles/ruptures), [paper](https://arxiv.org/pdf/1801.00826)). Implements **PELT** ("Pruned Exact Linear Time"), which computes the segmentation minimising a constrained sum of approximation errors, with a pruning rule that discards many candidate indexes while still returning the optimal segmentation; `min_size` sets minimum distance between change points, `jump` subsamples candidate indexes. Also binary segmentation, window-based, and dynamic programming.
- **The 30-minute session rule's origin.** Google Analytics' default session timeout is 30 minutes of inactivity. The number traces to **Catledge & Pitkow (1995)**, who measured mean time between user events at **9.3 minutes**, added 1.5 standard deviations to get 25.5 minutes, which was later "smoothed out to 30 minutes" ([Ringside](https://www.ringside.ai/articles/30-minute-sessions/), [Google Analytics docs](https://support.google.com/analytics/answer/9191807)). **This is important: the industry-standard inactivity threshold is a rounded number derived from 1995 dial-up browsing behaviour. It is not a law of nature and must not be hardcoded.**
- UiPath task-mining patents (via [Justia assignee listing](https://patents.justia.com/assignee/uipath-inc)) describe "receiving recorded tasks identifying user activity… clustering the recorded user tasks into steps by processing and scoring each recorded user task… extracting step sequences that identify similar or repeated combinations of the steps."

**Recalled, not verified:**

- That `ruptures` is BSD-2-Clause licensed and actively maintained. Plausible; **not confirmed** this session. Check before adopting.
- DenStream's original citation (Cao et al., SDM 2006). Named from memory.

**Not checked (gaps):**

- Full text of the Agostinelli/Marrella segmentation chapter (PDF extraction failed).
- The Mannheim GitLab repo's licence, language and dependency set — **must be checked before any reuse**, since a non-permissive licence would change the plan.
- Quantitative accuracy numbers for any of these methods on comparable data. No paper's reported F1 was actually read this session.
- Full-text claim searches on the UiPath task-mining patents.

---

## 3. Prior art / existing solutions found

| What | Who | Type | Same mechanism or same goal? | Blocking? |
|---|---|---|---|---|
| Supervised segmentation via trace alignment, **needs a routine model as input** | Agostinelli, Marrella, Mecella (2021) | Book chapter / academic | Same goal, opposite assumption — it requires knowing the routine in advance, which is precisely what we are trying to discover | No. Unusable for discovery, useful as a *validator* once we have a candidate model |
| Unsupervised task recognition on streams, **DenStream** micro-clustering | Rebmann & van der Aa, CAiSE 2023 | Academic + code | **Same goal, closest method.** Streaming, unsupervised, no cluster count needed | No, and it is the strongest reuse candidate |
| word2vec + time-series **motif discovery** on long unstructured recordings | Hohenadl, BPM 2025 | Academic | Same goal, same "no predefined boundaries" assumption as us | No |
| Neural event-case correlation on click data | Pegoraro et al. | Academic | Same goal; validated only qualitatively | No |
| Case-ID deduction against a **known process model** | Bayomie et al. | Academic | Same goal, needs a model | No |
| EM/HMM event correlation, **acyclic processes only** | Ferreira & Gillblad | Academic | Same goal, assumption we violate (our processes loop) | No |
| Human-in-the-loop segmentation | ICSOC 2021 | Academic | Complementary — supports our confidence/review design | No |
| Clustering recorded tasks into steps, extracting repeated step sequences | UiPath | Patent family | Overlaps **Stage 4** more than Stage 2; claims not read | Unknown — needs a real claim search |
| 30-minute inactivity sessionisation | Google Analytics et al. | Industry practice | Same goal, crude mechanism | No |

**Conclusion on prior art: segmentation of UI logs is an active, crowded
research area with at least four distinct published approaches.** We are not
first, and we should not pretend to be.

---

## 4. Options considered

- **A. Inactivity-gap rules** — cut on a long pause. Trivial, explainable.
- **B. Terminal-action rules** — cut after "Approve"/"Submit"/"Reject".
- **C. Identifier-anchored spans** — an episode is the span of events sharing one
  case identifier (loan ID, ECN, ticket).
- **D. Change-point detection** (`ruptures`/PELT) on a feature time-series.
- **E. Streaming density clustering** (DenStream, per Rebmann & van der Aa).
- **F. word2vec + motif discovery** (per Hohenadl).
- **G. Model-based correlation** (Bayomie / Ferreira & Gillblad) — needs a model.
- **H. Neural correlation** (Pegoraro et al.).

---

## 5. Debate — for and against

### 5.1 The central question: identifier-anchored (C) vs. behavioural methods (D/E/F)

**Behavioural methods — case for.** They are what the literature actually
does, they need no assumption that an identifier exists or is visible, and there
is published code (Mannheim GitLab) plus published methods to compare against.
They work on action *types* alone, so they degrade gracefully when content
capture is poor. If our Stage 1 content capture underperforms in the field, these
still function.

**Behavioural methods — case against.** They infer the boundary from the shape
of behaviour, which means a boundary is a *statistical guess* even when the
screen was literally displaying `LN-48213` the whole time. They also struggle
with the thing real office work does constantly: **interleaving**. A sequential
segmenter assumes one case at a time. Sam handling two loans in parallel, or
answering email mid-review, produces either one giant merged episode or a
spurious split.

**Identifier-anchored — case for.** Stage 1 captures something almost none of
this literature has: **the actual identifier values visible on screen**, not just
action types. If `LN-48213` is on screen from 09:02 to 09:08, the episode
boundary is not a guess — it is an observation. Crucially, identifier spans can
**overlap**, so interleaving is handled natively rather than being a failure
mode: two concurrent loans are simply two overlapping spans. It also produces
episodes that are *self-labelling* — each episode comes with the business key it
belongs to, which Stage 3 and Stage 6 both want anyway.

**Identifier-anchored — case against.** It assumes an identifier exists, is
visible, and is captured. Three real failure modes: processes with no visible
case key at all; identifiers that appear only on one screen and then vanish for
the rest of the case; and the reverse, a "sticky" identifier that stays on a
dashboard all day and would swallow everything into one enormous episode. It
also inherits every blind spot from Stage 1 — a case worked mostly in an
unreadable application has no anchor.

**Call: identifier-anchored as primary, behavioural as fallback, both reported
with their method and confidence.** The decisive argument is that we paid for
content capture in Stage 1 specifically so we would not have to guess — using a
statistical segmenter on top of observed identifiers would be throwing away the
evidence we went to the trouble of collecting. But because identifiers fail in
named, predictable ways, the fallback is not optional, and every episode must
carry *how it was derived*.

### 5.2 Which fallback: PELT change-point (D) vs. DenStream (E) vs. motifs (F)

**PELT — for:** in a maintained general-purpose library (`ruptures`), exact
rather than greedy, linear-time, one tunable penalty. Well understood, easy to
explain to a skeptic, and fast to try.
**PELT — against:** it segments a *numeric signal*, so we must first turn the
event stream into a feature series (app-switch rate, element-vocabulary churn).
That encoding choice does most of the real work, and a bad encoding produces
confident nonsense.

**DenStream — for:** purpose-built for this exact task by Rebmann & van der Aa,
streaming (matches Stage 1's continuous capture), needs no cluster count, and has
published code.
**DenStream — against:** it recognises *task types* by clustering behaviour, which
is arguably closer to Stage 4's job than Stage 2's; adopting it here risks
blurring the boundary between the two stages. Licence and maintenance unverified.

**Motif discovery (Hohenadl) — for:** explicitly designed for long, noisy,
unstructured recordings with no predefined boundaries — the closest problem
statement to ours in the literature.
**Motif discovery — against:** newest and least battle-tested; finds *repeating*
routines, so a rare-but-real case variant may be discarded as noise. For QA/QC
work, the exceptions are often the interesting part.

**Call: PELT first as the fallback, because it is the cheapest to build and the
easiest to falsify.** Evaluate DenStream as a comparison arm in the Stage 2
evaluation harness rather than as infrastructure. Revisit motif discovery in
Stage 4, where "find the repeating pattern" is genuinely the goal.

### 5.3 Fixed inactivity threshold vs. learned threshold

**Fixed (e.g. 30 min) — for:** trivial, predictable, and it is what the entire
web analytics industry does.
**Fixed — against:** the 30-minute standard is a rounded number derived from
1995 dial-up browsing (Catledge & Pitkow measured 9.3 min mean, added 1.5 SD,
got 25.5, which drifted to 30). It has no relationship to how long a QA reviewer
pauses mid-case. A threshold that is too long merges cases; too short shatters
one case into fragments. And **the right value differs per process and per
person.**

**Call: learn the threshold per actor and per application-set from the observed
inter-event gap distribution** (e.g. a high percentile, or the knee of the
distribution), with the fixed value only as a cold-start default. Keep the value
used in the episode record so results stay explainable.

### 5.4 Should every event belong to an episode?

**Force full coverage — for:** downstream stages get a clean partition; no
awkward "leftovers" to handle.
**Force full coverage — against:** it is a lie. Real days contain email, coffee,
Slack, and work on systems we cannot read. Forcing those into the nearest episode
poisons Stage 4's statistics with steps that were never part of the process.

**Call: do not force coverage.** Events that belong to no episode go into a
labelled **residue** set. The proportion of residue is itself a reported quality
metric — a sudden rise means either the person changed what they do, or capture
degraded, and both are worth knowing.

### 5.5 Reuse the Mannheim code or reimplement?

**Reuse — for:** it is the published implementation of the closest method;
comparing against the original beats comparing against my re-implementation of it.
**Reuse — against:** licence, language and dependencies are **unverified**; it is
research code targeting a streaming setting we are not yet in (Stage 2 runs
offline over a stored timeline).

**Call: use it as a comparison arm in evaluation if the licence permits; do not
build infrastructure on it.** Check the licence in Phase 2.1 before any code is
copied.

---

## 6. Novelty check (required)

**Is Stage 2 novel? No.** UI-log segmentation has at least four distinct
published approaches (supervised alignment, streaming density clustering, motif
discovery, neural correlation) plus a whole literature on deducing case IDs for
unlabelled logs. Anyone claiming segmentation itself as an invention would be
contradicted by a five-minute literature search.

**Is our twist novel?** The twist is *anchoring episodes on identifier values
observed in on-screen content*, which most of this literature cannot do because
their logs do not contain reliable content. That is a real difference in
capability — but it is a **consequence of Stage 1's capture decision, not an
independent invention**, and once you have the data, anchoring on it is the
obvious move. Obviousness is exactly the bar patents are judged against, so this
should not be presented as inventive.

**Is it "just apply an LLM to X"? No** — the proposed mechanism is span
construction over observed identifier occurrences plus change-point detection on
a feature series. No model is asked to "figure out where cases start". That
restraint should be preserved: an LLM proposal here would be a step backwards in
both explainability and defensibility.

**Where the novelty must live: Stage 3.** Stage 2 should be judged on accuracy
and honesty, not originality.

---

## 7. Conclusion / recommendation

Build a **three-signal segmenter with explicit arbitration**:

1. **Identifier-anchored spans** (primary) — an episode is the span over which a
   case identifier is observed, allowing overlapping spans so interleaved work
   survives.
2. **Structural rules** (corroborating) — learned inactivity thresholds and a
   terminal-action lexicon ("Approve", "Reject", "Submit") drawn from the
   `ui_chrome` text Stage 1 keeps in clear.
3. **Change-point detection via `ruptures`/PELT** (fallback) over stretches where
   no identifier is available.

Arbitrate between them, attach a **method label and confidence** to every
episode, leave unexplained events in a **residue** set, and route low-confidence
boundaries to a human review tool. Evaluate against the scripted ground truth
produced by Stage 1's Phase 1.9, using boundary F1 with a tolerance window plus
episode purity — never on "it looks about right".

**What would change this call:** if the Phase 2.3 identifier discovery finds that
fewer than ~60% of episodes in real data carry a visible, capturable identifier,
identifier-anchoring becomes the fallback and a behavioural method becomes
primary — which would also weaken the Stage 3 case and should trigger a rethink,
not a workaround.

---

## 8. Open items requiring a human decision

1. **What counts as a case?** For one loan review the answer seems obvious — but
   is a case *one loan*, *one review of one loan* (a loan reviewed twice = two
   cases), or *one sitting*? This is a business definition, not a technical one,
   and it changes what Stage 4 mines and what Stage 6 reports. **Needs an answer
   from someone who knows the domain.**
2. **Interleaving policy.** If Sam works two loans in parallel, overlapping spans
   represent it truthfully but make Stage 4's mining harder (most process-mining
   algorithms expect disjoint cases). Options: allow overlap and flatten later,
   or force disjoint episodes and accept inaccuracy. I recommend allowing
   overlap and flattening at the Stage 4 boundary, but it is a real trade.
3. **Residue tolerance.** What proportion of unassigned events is acceptable
   before we call capture or segmentation broken? I have proposed 30% as a
   provisional alarm threshold; it is a guess and should be set from real data.
