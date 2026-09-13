# Stage 6 Blueprint — Producing the final output

**Source of truth:** `plans/pulse-architecture.md`, Stage 6.
**Cross-cutting controls:** `plans/platform-architecture.md` — binding.
**Research backing:** `research/stage-6-output.md`.
**Plain-English version:** `manual-readable/stage-6.md`.
**Status:** blueprint only — no implementation code has been written.

> **Three additions from the platform decisions:**
>
> 1. **Report accuracy per sensing surface, never blended.** "Exact on modern
>    applications, approximate on mainframe screens, and here is which is
>    which" is a checkable statement; a single averaged accuracy figure is not.
>    Every claim derived from computer-vision readings is marked as such.
> 2. **Identifiers appear as hashes or as shape-masked references**, never as
>    cleartext values. Where a reader genuinely needs a real value, they use the
>    audited reversal vault — which produces an audit record. The document
>    itself never embeds one.
> 3. **The "what we don't know" section gains a sensing row:** which surfaces
>    were read structurally, which by vision, and which could not be read at
>    all. That row is the honest answer to "how much of this can I trust?"

---

## 1. Stage goal

Stage 6 produces the thing the whole tool exists to make: **one clear, structured,
trustworthy written description of a discovered process** — which applications it
touches, the backbone steps in order, the cross-application links and how strongly
each is evidenced, the branches and the conditions that trigger them, the process
type, and, crucially, **an honest account of what is not known**. It must be
understandable to someone who has never watched the work being done. It is not a
video and not a vague summary. The stage ends here on purpose: turning this
description into running automation, agents, or an ingestion pipeline is
explicitly out of scope, and that boundary should be stated inside the document
itself so nobody mistakes it for an automation specification. **Automated process
documentation is not new** — UiPath Task Mining exports Process Definition
Documents today — so the distinguishing standard here is editorial: every claim
carries its support, and every uncertainty survives to the page.

---

## 2. Phases

Five phases.

---

### Phase 6.1 — The process description model and its provenance chain

**Goal.** Define the authoritative artefact everything else renders from, and
guarantee that every claim in it can be traced back to evidence.

**Build steps**

1. **Define the native process description** as versioned JSON — the single source
   of truth. Sections: identity and scope, applications, activities, control flow,
   cross-application links, branches and conditions, exceptions and rework,
   process type, quality and coverage, known gaps.
2. **Every quantitative claim carries its support**: numerator, denominator,
   confidence interval, and the source stage. `"97%"` alone is not permitted in
   the model; `{value: 0.97, n: 388, of: 400, ci: [0.94, 0.98], source: "stage4.frequency"}`
   is. **Enforce this in the schema** so the rule can't erode under deadline
   pressure.
3. **Every cross-application link carries its evidence tier** from Stage 3
   (`proven_transfer` / `deliberate_selection` / `observed_visibility` /
   `co_occurrence`), its episode count, and its confidence. A link proven by
   copy/paste in 240 episodes and one inferred from visibility in 8 are different
   kinds of claim and **must not render identically**.
4. **Build the provenance chain end to end**: document claim → Stage 4 model
   element → episodes → events. A reader asking "how do you know that?" gets an
   answer, and a developer debugging a wrong claim can walk back to the raw
   capture. This is also what makes the output defensible in an audit context.
5. **Carry the process-type label with its confirmation status** from Stage 5 —
   "confirmed by a person" and "proposed, not yet reviewed" must be visibly
   different in the output.

**Expected output.** `schema/pulse-process-description.v1.schema.json`; a builder
that assembles it from Stages 3–5 outputs; a provenance index.

**Validation checkpoint**

- **Provenance test:** pick 20 claims at random from a generated description and
  trace each back to the underlying events. Pass = 20/20 traceable.
- **Schema enforcement:** a claim without support figures is rejected at build
  time. Test with a deliberately malformed claim.

---

### Phase 6.2 — The written document

**Goal.** Render the model as something a person actually reads.

**Build steps**

1. **Deterministic templating** (Jinja2 → Markdown, with HTML as a rendering
   target). Every sentence is a template filled from the model.
2. **Structure the document for the reader, not for the pipeline.** Proposed
   sections:
   - **In one paragraph** — what this process is, who does it, how often, and how
     confident we are.
   - **The systems involved** — each application, what it is used for here, how
     much of the process happens in it.
   - **The main path** — backbone steps in order, each with what the person does,
     in which system, and how consistently it appears.
   - **How information moves between systems** — the cross-application links,
     each with its evidence in plain words.
   - **Where it varies** — branches with their trigger conditions, stated as
     sentences, plus frequency.
   - **Exceptions and rework** — what goes wrong and what people do about it.
   - **What kind of process this is** — the Stage 5 label with its reasoning and
     confirmation status.
   - **What we don't know** — Phase 6.4, mandatory.
   - **How this was produced** — capture period, episode count, people, method
     summary, and the explicit statement that this describes observed reality, not
     policy.
3. **Write evidence into the prose, not into footnotes.** "In 388 of 400 observed
   cases (97%), the reviewer opened the document library before deciding" reads
   naturally *and* carries its support. Footnoted evidence gets skipped.
4. **No generated prose for factual claims.** Templates only. An LLM may be used
   at most to *rephrase* a sentence whose facts are fixed, and that use must be
   off by default. **Fluent invented prose would break the single property that
   makes this document worth more than a competitor's** — that every sentence is
   traceable to a number.
5. **Obtain and review a sample UiPath PDD** before finalising the structure. It
   is the de facto industry format; matching its skeleton where sensible aids
   adoption, and diverging where we have better material should be a deliberate
   choice rather than ignorance of the convention. *(OQ-14.)*
6. **State the scope boundary in the document itself** — this describes the
   process; it is not an automation specification.

**Reuse call.** Jinja2 for templating. Document structure is custom, informed by
the PDD convention.

**Expected output.** Generated Markdown/HTML document per discovered process.

**Validation checkpoint**

- Every section populated or explicitly marked "not enough data" — never silently
  absent, because a missing section reads as an absence of the phenomenon rather
  than an absence of evidence.
- Zero sentences containing an unsupported quantitative claim (automated check
  against the schema rule from 6.1).

---

### Phase 6.3 — Diagrams and machine-readable exports

**Goal.** Give the reader a picture, and give other tools a file.

**Build steps**

1. **BPMN 2.0 XML export** via PM4Py — convert the Petri net to BPMN
   (`petri_to_bpmn`, which supplies **correspondence dictionaries** between Petri
   net and BPMN elements, preserving our provenance chain across the conversion)
   and export with `export_bpmn`. Frequency and performance information can be
   written into the BPMN 2.0 XML directly.
2. **Record BPMN's limits in the output.** BPMN has no native way to express
   "this link is supported by copy/paste evidence in 240 episodes" or "we don't
   know how these connect". Our evidence goes into extension attributes that most
   tools will drop on import. **The native JSON remains authoritative**; BPMN is a
   view. Say this in the export header so nobody round-trips through BPMN and
   loses the evidence silently.
3. **Also export** OCEL 2.0 (from Stage 3, for object-centric analysis) and the
   native JSON description.
4. **Diagrams for the document:**
   - A **swimlane-style view by application** — the picture that shows what makes
     this project different: steps grouped by system, with links between lanes
     annotated by evidence tier.
   - A **main-path diagram** with branches, frequency-annotated.
   - **Render deterministically** (Graphviz or Mermaid). Distinguish proven links
     (solid), inferred links (dashed), and unexplained transitions (dotted with a
     question mark) — **visually, not only in a legend**, since diagrams get
     screenshotted away from their legends.
5. **Accessibility:** every diagram needs a text equivalent, because the document
   must work for a reader who cannot see it and because screenshotted diagrams
   lose their data otherwise.

**Reuse call.** **Reuse PM4Py's BPMN conversion and export.** Graphviz/Mermaid for
diagrams. Do not hand-roll BPMN XML.

**Expected output.** `process.bpmn`, `process.ocel`, `process.json`, plus rendered
diagrams and their text equivalents.

**Validation checkpoint**

- The BPMN file opens in at least one third-party tool (bpmn.io or Camunda
  Modeler) without errors.
- Evidence tiers are visually distinguishable in the diagram **when printed in
  greyscale** — colour-only encoding fails this deliberately.
- Each diagram's text equivalent conveys the same information.

---

### Phase 6.4 — The "what we don't know" section

**Goal.** Carry every uncertainty the previous five stages recorded into the
final document, where a reader will actually see it.

**This section is the reason the output can be trusted. It is mandatory and must
never be suppressed for a customer-facing version.**

**Build steps**

Assemble automatically from each stage's honest outputs:

1. **Blind applications** (Stage 1 coverage map) — "activity in *[application]*
   could not be observed; steps performed there are missing from this description."
   This is the most important single sentence in the document for a reader
   deciding how much to trust it.
2. **Unexplained transitions** (Stage 3) — "in N cases the reviewer moved from A
   to B and we could not determine how the two were connected."
3. **Low-confidence episodes** (Stage 2) and how many were excluded.
4. **Insufficient-data verdicts** (Stage 4) — process variants seen too rarely to
   describe.
5. **Model quality** (Stage 4) — fitness and precision in plain words: "this
   description accounts for 87% of observed behaviour."
6. **Unconfirmed labels** (Stage 5).
7. **Capture period and population** — how many people, over how long. **A process
   mined from three people over two weeks is a different claim from one mined from
   forty over six months**, and the document must make that impossible to miss.
8. **Known biases** — which shifts, which teams, which systems were in scope.

**Validation checkpoint**

- On a deliberately degraded corpus (one application blinded, several episodes
  low-confidence), the section correctly reports every injected limitation.
  Pass = 100% of injected limitations reported.
- The section is present and non-empty in **every** generated document. A document
  claiming no limitations is itself a defect.

---

### Phase 6.5 — Comprehension testing and acceptance

**Goal.** Test the architecture's own checkpoint — that a person who has never
seen the task performed can read this and understand it.

**Build steps**

1. **Recruit readers unfamiliar with the process** (3–5 people minimum).
2. **Give them only the document**, no briefing.
3. **Measure three things:**
   - **Factual comprehension** — 10 questions with objectively correct answers:
     *what triggers the document check? what are the possible outcomes? which
     systems are involved? what happens when the figures disagree?*
   - **Sequence reconstruction** — put a shuffled list of steps in order; score
     against the model.
   - **Calibrated confidence** — how confident are they, and **were they right to
     be?** Overconfidence is a document failure: it means the writing sounds more
     certain than the evidence warrants, which is exactly the failure the "what we
     don't know" section exists to prevent.
4. **Also have a domain expert review** for correctness — comprehension and
   accuracy are different failures and need different readers.
5. **Iterate on the template**, not on the data.

> **Note:** I did not find a validated instrument for testing comprehension of
> generated process documentation, so this test design is ours. It is better than
> no test, but it is not a standard, and if a validated instrument exists it
> should be preferred.

**Validation checkpoint (Stage 6 exit criteria)**

| Metric | Threshold |
|---|---|
| Factual comprehension by unfamiliar readers | ≥ 80% correct |
| Sequence reconstruction accuracy | ≥ 80% |
| Reader confidence calibrated (not overconfident) | yes |
| Domain expert judges the description accurate | yes, with specific corrections only |
| Claims traceable to evidence | 100% |
| "What we don't know" section present and correct | 100% |
| BPMN opens in a third-party tool | yes |

---

## 3. Dependencies

**Needs from Stage 5:** process type, confidence, evidence, confirmation status.
**Needs from Stage 4:** the model, activity dictionary, frequencies with intervals,
branch conditions, quality metrics, cross-application map, insufficient-data
verdicts.
**Needs from Stage 3:** links with evidence tiers and counts; unexplained
transitions; the OCEL log.
**Needs from Stage 2:** episode counts, confidence distribution, residue.
**Needs from Stage 1:** the application coverage map — which systems could and
could not be observed. **This feeds the single most important sentence in the
document.**

**Hands off to:** a human reader. And to Stage 7, which needs the model snapshot
and its version as the baseline to detect drift against.

**Explicitly does not hand off to:** automation generation, agent construction, or
an ingestion pipeline. The architecture puts these out of scope and the document
should say so in its own text.

---

## 4. Open questions and risks

### OQ-14 — Match the UiPath PDD skeleton, or structure around evidence?

Matching aids adoption by teams who already work that way; diverging lets us lead
with what makes our output better. I lean towards matching the skeleton and adding
our sections. **Get a sample PDD before deciding.**

### OQ-15 — Delivery format

Markdown/HTML is easiest, diffable, and version-controllable. Enterprises often
want Word or PDF. Affects tooling.

### OQ-16 — Who is the reader?

An analyst, an automation developer, and an auditor want different documents from
the same model. The architecture implies the analyst. Worth confirming, since it
sets the level of detail.

### Risk — the honest sections get cut

The "what we don't know" section will be the first thing someone wants removed
from a customer-facing version, because it makes the product look less capable.
**Removing it turns a trustworthy description into a confident-sounding guess**,
which is precisely what the tool was built not to be. It should be structurally
mandatory, not a template option.

### Risk — the LLM shortcut

Generating the prose with a language model would produce a more fluent document
faster, and would break the one property that distinguishes it. Templates for
facts; rephrasing only, off by default.

### Risk — this stage is not novel and shouldn't claim to be

UiPath already exports Process Definition Documents from observed task activity.
The difference here is editorial standard, and it should be described as a better
document, not as an invention.

### Judgment calls a reviewer should re-examine

- **Native JSON authoritative, BPMN as a view** — correct in my view, but it means
  maintaining two representations.
- **Templating over generation** — costs fluency, buys traceability.
- **Comprehension testing with real readers** — slow and unglamorous, and the only
  external validity check this stage has.
