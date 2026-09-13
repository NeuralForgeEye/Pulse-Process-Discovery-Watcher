# Research Log — Stage 3: linking applications within one episode

**Stage / Phase:** Stage 3 — cross-application linking
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes; novelty finding in §6 is the most
consequential result in this repo so far

---

## 1. Question being investigated

The architecture names Stage 3 as "the piece least likely to already exist
off-the-shelf" and "the most promising place to look for a genuinely new,
defensible invention." So this log has to answer three things properly:

1. Is inferring *how a value moved between applications* already done, and by whom?
2. What is the right technical framework for combining evidence of different
   strengths (copy/paste vs. highlight vs. mere visibility)?
3. Is there anything left here that is actually new?

---

## 2. What was actually checked

**Verified:**

- **DLP clipboard monitoring.** Endpoint data-loss-prevention agents already do
  the core mechanism: "DLP agents can record the identity of the application that
  originally initiated the *copy* command to the clipboard. When a user attempts
  to use a *paste* command to copy text to a different application, the DLP agent
  submits the copied text to a content analysis module." Patent literature
  includes [US9672366 *Techniques for clipboard monitoring*](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9672366), Symantec's [*Technique for data loss prevention through clipboard operations*](https://www.freepatentsonline.com/y2016/0292454.html), and [US10255446 *Clipboard management*](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10255446). Commercial: [Microsoft Edge Protected Clipboard](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-management-protected-clipboard), SquareX Clipboard DLP.
- **Leno et al., *Automated Discovery of Data Transformations for Robotic Process
  Automation*** ([arXiv 2001.01007](https://arxiv.org/abs/2001.01007), 2020).
  Addresses "analyzing User Interaction (UI) logs in order to discover routines
  where a user transfers data from one spreadsheet or (Web) form to another",
  mapping it to **data transformation discovery by example**. Notes a naive
  application of state-of-the-art transformation discovery is computationally
  inefficient, and proposes optimisations exploiting the UI log and the fact that
  "data transfers across applications typically involve copying alphabetic and
  numeric tokens separately."
- **[US7693916B2 — *Correlating process instance data across multiple
  applications*](https://patents.google.com/patent/US7693916B2/en)** — an
  identifier associated with an instance by a first application and an identifier
  associated with the same instance by another application, indexed via a
  continuation data table. **Claims not read in full**; from the summary this
  appears to be server/middleware-side correlation, not desktop observation.
- **[US20090164522A1](https://patents.google.com/patent/US20090164522)** —
  computer forensics collection including *Clipboard Contents* alongside keystroke
  logs and process information.
- **Fellegi–Sunter probabilistic record linkage** and **Splink** (open source,
  UK Ministry of Justice) — [theory guide](https://github.com/moj-analytical-services/splink/blob/master/docs/topic_guides/theory/fellegi_sunter.md), [Linacre's introduction](https://www.robinlinacre.com/intro_to_probabilistic_linkage/). Models a comparison vector as arising from two distributions (matches and non-matches) with probabilities *m* and *u*; the weight is the ratio m/u. **Match weights are additive**: total = prior weight + per-feature partial weights. Splink estimates the model via **Expectation-Maximisation**, building on FastLink's R implementation, and supports blocking, similarity comparisons, and clerical review. Used at national-statistics scale (a 2026 German administrative-data study).
- **Dempster–Shafer evidence theory limitations.** Dempster's rule "may lead to
  counter-intuitive results when dealing with highly conflicting bodies of
  evidence"; it also requires "all sources of evidence to be combined have the
  same reliability; however, this is difficult to be satisfied in practical
  applications", and despite many proposed fixes, "this is still an open issue"
  ([survey](https://www.sciencedirect.com/science/article/abs/pii/S1568494622003696), [Information Sciences](https://dl.acm.org/doi/10.1016/j.ins.2021.08.088)).
- **Taint tracking / information-flow tracking** as the alternative mechanism.
  TaintDroid reports **32% overhead** on a CPU-bound microbenchmark; TaintART
  ~**14%**; Panorama does instruction-level whole-system tracking under QEMU with
  shadow memory for every byte. General finding: "static taint analysis suffers
  from a lack of precision while dynamic taint tracking has a high performance
  overhead."
- **Object-centric process mining / OCEL 2.0.** Events in object-centric event
  data "can reference multiple objects of varying types with arbitrary
  cardinality." **PM4Py fully supports OCEL 2.0**, including object-centric
  discovery and conformance checking (Petri nets, DFGs, object graphs), and
  OC-DFG discovery. Other tooling: OC-PM (ProM/web), `ocpa` (Python), PM4Py-MDL.
  Recent work adds drill-down / roll-up / unfold / fold granularity operations
  ([arXiv 2412.00393](https://arxiv.org/abs/2412.00393); [SLR arXiv 2311.08795](https://arxiv.org/pdf/2311.08795)).

**Recalled, not verified:**

- Splink 4's local DuckDB backend (i.e. that it runs without Spark). Believed
  true; **verify before relying on it**.
- Splink's licence (believed MIT). Not confirmed this session.

**Not checked (gaps):**

- **Full claim text of US9672366, US7693916B2, or the Symantec DLP clipboard
  application.** Only summaries were read. **This matters a great deal** and is
  the single biggest gap in this log.
- Whether any DLP vendor has patented *aggregating* clipboard-flow observations
  across many users into a process model (as opposed to per-event policy
  enforcement). This is the key differentiating question and it is **unanswered**.
- Skan, UiPath, Celonis, NICE claim sets — still unread across all stages.

---

## 3. Prior art / existing solutions found

| What | Who | Type | Same mechanism or goal? | Effect on us |
|---|---|---|---|---|
| Record copy source application + content, inspect on paste into a different application | Endpoint DLP (Symantec/Broadcom, Microsoft, others) | Patents + shipping products | **Same mechanism, different goal.** They track app→app value movement to *block leaks*; we do it to *build a process map* | **Significant.** Tier-1 evidence (copy/paste with value and source/destination app) is not new as a capture-and-correlate mechanism |
| Discover data transfers between forms/spreadsheets from UI logs, incl. the transformation applied | Leno et al., 2020 | Academic + technique | **Same mechanism, adjacent goal.** They infer the transformation function to synthesise an RPA script | **Significant.** "Detect that a value moved from field X in app A to field Y in app B, from a UI log" is published |
| Correlate process instance data across applications via shared identifiers | US7693916B2 | Patent | Same goal; appears to be middleware/server-side, not desktop observation | Moderate; claims unread |
| Forensic collection including clipboard contents | US20090164522A1 | Patent | Same capture, unrelated goal | Low |
| Probabilistic linkage with additive, EM-learned match weights | Fellegi–Sunter; Splink | Statistical framework + OSS | Neither — it's the *tool* for our scoring problem | Reusable framework |
| Object-centric event data: one event referencing many objects | OCEL 2.0 / PM4Py | Standard + OSS | Neither — it's the *representation* for our output | Reusable representation |
| System-wide dynamic taint tracking | TaintDroid, TaintART, Panorama | Academic systems | **Different mechanism, same question** ("where did this value go?") — by instrumenting execution rather than observing the user | Rules out an alternative approach on cost grounds |

---

## 4. Options considered

**For establishing that a value moved:**
- A1. Deterministic copy/paste pairing (Stage 1 Phase 1.5 already produces it).
- A2. Selection-then-appearance inference.
- A3. Visibility-then-appearance inference.
- A4. Timing/co-occurrence only.
- A5. OS-level taint tracking (instrument execution, don't infer).

**For combining evidence of differing strength:**
- B1. Fixed hand-set ranking (what the architecture describes).
- B2. Additive log-odds score, hand-set weights, calibrated.
- B3. Fellegi–Sunter with EM-learned weights (Splink).
- B4. Dempster–Shafer belief fusion.
- B5. Supervised classifier on labelled links.

**For representing the result:**
- C1. Custom link records.
- C2. **OCEL 2.0** object-centric event log.
- C3. W3C PROV provenance graph.

---

## 5. Debate — for and against

### 5.1 Infer from observation (A1–A4) vs. taint-track the real data flow (A5)

**Taint tracking — case for.** It answers the question *properly*. Instead of
inferring that a value probably moved, you follow the actual bytes. No evidence
ranking, no probability, no argument. For a patent claim, "we track the actual
data flow" is a much stronger sentence than "we infer it from circumstantial
evidence."

**Taint tracking — case against.** It is not available to us. Every working
system in the literature instruments the execution environment: TaintDroid needs
Android's VM, TaintART the ART compiler, Panorama a whole-system QEMU emulator
with shadow memory per byte. Windows line-of-business applications are
closed-source native binaries running on the user's real machine. Overheads of
14–32% are reported *in the environments where it works*; on an uninstrumented
desktop it does not work at any price. It would also require exactly the kind of
deep process instrumentation Stage 1 deliberately avoided in order to survive a
security review.

**Call: observational inference. A5 is not a real option** — but it is worth
naming in the blueprint, because a reviewer will ask "why not just track the
data?" and the answer needs to be evidence-backed rather than dismissive.

### 5.2 How to combine evidence of different strengths

**B1 fixed ranking (the architecture's proposal) — for:** simple, explainable to
a domain expert, needs no training data, and directly matches how a human would
reason about it.
**B1 — against:** it gives an *order*, not a *number*. You cannot answer "is one
highlight-based link worth more than three visibility-based links?" or set a
threshold for acting on a link. And it cannot express that evidence strength
differs by *context* — a copy/paste of `LN-48213` is strong; a copy/paste of the
string `0` is nearly worthless, because that value is everywhere.

**B4 Dempster–Shafer — for:** designed exactly for combining evidence with
explicit uncertainty, and it can represent "I don't know" separately from "50/50".
**B4 — against:** documented counter-intuitive behaviour under highly conflicting
evidence — an unresolved issue in the literature after decades of proposed fixes
— plus the requirement that combined sources have *equal reliability*, which our
sources explicitly do not. Our whole premise is that copy/paste and mere
visibility are **differently reliable**. Using a framework whose assumptions our
problem violates by design would be a bad trade for a mathematical veneer.
**Rejected, with evidence.**

**B3 Fellegi–Sunter (Splink) — for:** the established framework for exactly this
shape of problem — "do these two observations refer to the same thing?" —
expressed as **additive match weights** (prior + per-feature partial weights),
learnable from unlabelled data by EM, with mature open-source tooling and
national-statistics-scale validation. It naturally handles the "value `0` is
worthless, value `LN-48213` is decisive" problem through *term-frequency
adjustment*, which is a standard part of the framework.
**B3 — against:** the classic model assumes **conditional independence** between
comparison features, and ours are strongly correlated (a copy is usually preceded
by a selection). Applied naively it will double-count correlated evidence and
produce overconfident links. Splink is also built for comparing *records in
tables*, so our event-pair framing is an adaptation, not a drop-in.

**Call: B2 first, B3 as the principled upgrade.** Start with an explicit additive
log-odds score with hand-set weights — because it is debuggable, needs no
training data, and can be reasoned about by a domain expert — but **borrow two
specific things from Fellegi–Sunter immediately**: (a) express weights as log
odds so they add up meaningfully, and (b) **term-frequency adjustment**, so
common values contribute less than rare ones. Then, once candidate pairs exist,
run EM weight estimation as an experiment and compare calibration. Group
correlated evidence into a single feature with ordered levels (`copy_paste` >
`selection` > `visible` > `none`) instead of treating them as independent
features — this sidesteps the independence violation rather than ignoring it.

### 5.3 Representation: custom records vs. OCEL 2.0 vs. PROV

**Custom — for:** exactly fits our needs, no impedance mismatch.
**Custom — against:** Stage 4 would then need custom mining too, throwing away
PM4Py's object-centric discovery and conformance checking.

**OCEL 2.0 — for:** an event referencing *multiple objects of varying types with
arbitrary cardinality* is a precise description of our data — one UI event relates
to a case identifier, a document, an application, and a session at once. PM4Py
supports OCEL 2.0 discovery and conformance directly, so Stage 4 gets real
algorithms for free. It is also the field's direction of travel.
**OCEL 2.0 — against:** it represents *which objects an event touches*, not
*how a value moved between applications*. Our evidence strength and direction
have no native home in OCEL and must live in event attributes — a slight abuse of
the standard.

**PROV — for:** W3C standard designed precisely for "this thing derived from that
thing", which is literally what a link is.
**PROV — against:** essentially no process-mining tooling consumes it; we would
gain correctness and lose every downstream algorithm.

**Call: OCEL 2.0 as the handoff format to Stage 4, with link evidence carried as
event/relationship attributes, plus a native link table retained alongside it for
Stage 6's narrative.** Write both; they serve different consumers. Note the abuse
of the standard in the blueprint so nobody later mistakes it for conformance.

### 5.4 The weak-evidence problem — and where the real idea is

The architecture says timing-only links should be "used only to support a pattern
seen repeatedly across many episodes, never trusted alone." That instinct is
right and it is worth making precise, because it is the most defensible idea in
the project:

**Individually weak evidence can be promoted by recurrence across the
population.** One instance of "`LN-48213` was visible in LoanDesk, then typed in
DocVault" is circumstantial. But if that *same field-pair relationship*
(`LoanDesk.txtLoanId → DocVault.searchBox`) recurs across 300 episodes and 12
people, the *relationship* is established even though no single instance was
proven. The link's confidence therefore has two components: **instance evidence**
(what we saw this time) and **population evidence** (how often this field-pair
link is corroborated elsewhere, including by Tier-1 copy/paste proof in *other*
episodes).

That second component is what lets strong evidence in some episodes vouch for
weak evidence in others — and it is a specific, describable mechanism rather than
a vibe. It is also the part least likely to be covered by DLP prior art, because
DLP is per-event and policy-driven: it has no reason to aggregate across users to
establish that a field-pair relationship exists.

**Caveat, stated plainly:** this creates a feedback path between Stage 3 and
Stage 4 (population statistics inform individual links; linked episodes feed
population statistics). That must be a **two-pass** design with the passes kept
explicit, or it becomes circular reasoning that manufactures its own confidence.

---

## 6. Novelty check (required) — the important section

**Blunt summary: the mechanism is less novel than the architecture assumes, and
what remains novel is narrower and more specific than "cross-application
linking."**

What is **already done by others**:

1. **Tracking a value from the app that copied it to the app that pasted it,
   with the content** — this is what endpoint DLP agents do, it is in granted
   patents, and it ships commercially. Our Tier-1 evidence class is not new.
2. **Detecting that a user transferred data between applications from a UI log**
   — Leno et al. (2020) published this, and went further by inferring the
   *transformation* applied to the value.
3. **Correlating process instances across applications via a shared identifier** —
   US7693916B2, at least in a server-side context.

So the architecture's expectation that Stage 3 is "least likely to already exist"
is **partly wrong**: the individual evidence classes all exist somewhere. What
does not appear in anything found here is the **combination**:

> A ranked, calibrated evidence model over *heterogeneous and explicitly
> unequal* link evidence — proven transfer, deliberate selection, mere on-screen
> visibility, and co-occurrence — in which individually inadmissible evidence is
> **promoted to admissible by recurrence of the same field-pair relationship
> across a population of episodes**, producing a process-level link graph rather
> than a per-event policy decision.

Three honest qualifications on that:

- **It is a combination claim.** Combination claims are the weakest kind, and
  "obvious combination of known elements" is precisely how they get rejected.
- **The searches behind this were shallow.** No full claim text was read for any
  of the DLP patents. A real assessment needs full-text claim searching by a
  patent attorney. **Nothing here is clearance.**
- **It passes the CLAUDE.md "just apply AI to X" test** — the mechanism is
  evidence scoring plus population-level corroboration, with no LLM anywhere in
  the loop. That is a point in its favour for both defensibility and
  explainability, and it should be protected: proposing "have an LLM decide if
  these apps are linked" would destroy the only defensible thing here.

**Recommendation to the human:** if there is a filing decision to make, the
claim to pursue is the **two-component confidence with population-based promotion
of weak evidence**, not "cross-application linking" in general — and it should be
searched properly before any money is spent.

---

## 7. Conclusion / recommendation

Build Stage 3 as a **candidate-generation → tiered-evidence-scoring →
arbitration** pipeline:

1. **Blocking/candidate generation** on normalised value hashes within (and
   across concurrent) episodes — borrowed directly from record linkage practice,
   because comparing all event pairs is quadratic and unnecessary.
2. **Four evidence tiers** as the architecture specifies, implemented as a single
   ordered feature rather than four independent ones, to avoid double-counting
   correlated evidence.
3. **Additive log-odds scoring with term-frequency adjustment**, so rare values
   count more than common ones. Hand-set weights first; EM-learned weights
   (Fellegi–Sunter/Splink) as a measured comparison.
4. **Two-component confidence:** instance evidence + population corroboration,
   computed in two explicit passes to avoid circularity.
5. **Honest gaps:** transitions with no admissible evidence are recorded as
   `unexplained`, never bridged by assumption.
6. **Dual output:** OCEL 2.0 for Stage 4's algorithms, plus a native link table
   for Stage 6's narrative.

**What would change this call:** if Stage 2's identifier-coverage measurement
comes in low, Tier-1/2 evidence becomes rare, the model leans on visibility and
timing, and Stage 3's output quality — and its defensibility — drop together.
That measurement is the leading indicator for this entire stage.

---

## 8. Open items requiring a human decision

1. **The novelty finding above needs a real patent search before any filing
   decision.** DLP clipboard-tracking patents are close prior art on the
   mechanism, and I read summaries, not claims. This is the highest-value item in
   this repo for a patent attorney to look at, and the cheapest mistake to avoid.
2. **Direction of flow.** Evidence proves two applications shared a value; it does
   not always prove *which way it went* (both may read it from a third system).
   I propose recording direction only when Tier-1/2 evidence establishes it, and
   marking it `undirected` otherwise. A domain expert may have a better default.
3. **The two-pass feedback design** between Stage 3 and Stage 4 is where
   circular reasoning could creep in and silently inflate confidence. It deserves
   a skeptical review by a human before implementation, not after.
