# Research Log — Stage 6: producing the final output

**Stage / Phase:** Stage 6 — the deliverable
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes

---

## 1. Question being investigated

Stage 6 is where the product actually delivers. Questions:

1. Does automated process-documentation generation already exist commercially?
2. What machine-readable format should the model be exported in?
3. How do you *test* that a document is understandable — the architecture's
   checkpoint says a person who has never seen the task must understand it, which
   sounds untestable but shouldn't be.

---

## 2. What was actually checked

**Verified:**

- **PM4Py BPMN support.** PM4Py converts a Petri net into a BPMN diagram
  (`pm4py.objects.conversion.petri_to_bpmn`), providing **correspondence
  dictionaries between elements in the original Petri net and the resulting BPMN
  diagram** — i.e. the mapping needed to keep provenance across the conversion.
  Export to **BPMN 2.0 XML** via `pm4py.objects.bpmn.exporter.bpmn20`
  (`export_bpmn`), and "it's also possible to write frequency and performance
  information directly into the BPMN 2.0 XML file."
  ([PM4Py BPMN 2.0 management](http://pm4py.pads.rwth-aachen.de/bpmn-2-0-management/),
  [convert module docs](https://pm4py-source.readthedocs.io/en/latest/_modules/pm4py/convert.html))
- **UiPath Task Mining exports a PDD.** From the Stage 1 research: UiPath's Task
  Mining surfaces "automation skeleton export as PDD and XAML files" — a **Process
  Definition Document** plus executable workflow files. UiPath also ships
  **Task Capture** as a dedicated process-documentation tool.

**Recalled, not verified:**

- The internal structure of a UiPath PDD (sections, level of detail). Named from
  general knowledge; **not inspected this session.** Worth obtaining a sample
  before designing our document structure, since it is the de facto industry
  format and matching its skeleton would aid adoption.
- That BPMN 2.0 is an OMG standard with broad tool support (Camunda, Signavio,
  Visio, bpmn.io). High confidence, not re-verified.

**Not checked:**

- Whether any published work evaluates *comprehension* of automatically generated
  process documentation. Our Phase 6.5 comprehension test design is therefore
  **my own construction**, not a method taken from literature. If a validated
  instrument exists, it would be better than mine.
- Accessibility standards for the output document (WCAG). Relevant if this is
  delivered as HTML and worth checking before shipping.

---

## 3. Prior art / existing solutions found

| What | Who | Type | Relevance |
|---|---|---|---|
| Process Definition Document (PDD) generated from observed task activity | UiPath Task Mining / Task Capture | Commercial product | **Direct prior art for this stage.** Automated process documentation from observation is a shipping feature, not a new idea |
| Petri net → BPMN conversion, BPMN 2.0 XML export with frequency/performance annotations | PM4Py | OSS | Reuse directly |
| BPMN 2.0 | OMG standard | Standard | The machine-readable target format |

**Conclusion:** Stage 6 is not novel either. What can distinguish our output is
**not the fact of generating a document but what is in it** — specifically, the
evidence provenance and the explicit statement of what is *not* known. UiPath's
PDD exists to seed automation; ours exists to be trusted as a description.

---

## 4. Options considered

**Machine-readable format:** BPMN 2.0 XML · Petri net (PNML) · OCEL 2.0 ·
plain JSON.

**Human-readable format:** Markdown · HTML · PDF · an interactive web view.

**Diagrams:** BPMN rendering · Graphviz DFG · Mermaid.

---

## 5. Debate — for and against

### 5.1 BPMN 2.0 as the machine-readable output

**For.** It is the standard business audiences and BPM tools already read, PM4Py
exports it with frequency and performance annotations embedded, and the converter
supplies correspondence dictionaries so we can keep a link from each BPMN element
back to the Petri net element and, through it, to the evidence.

**Against.** BPMN cannot express everything we know. It has no native way to say
"this transition is supported by copy/paste evidence in 240 episodes" or "we don't
know how these two steps connect." Forcing our evidence into BPMN extension
attributes means most tools will silently drop it on import — **the richest part
of our output is the part the standard format loses.**

**Call: export BPMN 2.0 for interoperability *and* keep a native JSON model as the
authoritative artefact**, with the document generated from the native model, not
from BPMN. BPMN is a view, not the source of truth. Say so explicitly in the
output so nobody round-trips through BPMN and loses the evidence without noticing.

### 5.2 What makes our document different from a UiPath PDD

**The case that it isn't different:** UiPath already generates a process document
from observed activity. A skeptical reviewer would say we are rebuilding a
shipping feature.

**The case that it is:** the PDD exists to seed an automation project — it
describes steps so a developer can automate them. Ours exists to be *trusted as a
description of reality*, which imposes different requirements:

- **Every claim traceable to evidence.** "97% of cases do this (388 of 400
  episodes, Wilson CI 94–98%)" rather than "reviewers check the document."
- **Cross-application links carry their evidence tier** — proven transfer vs.
  inferred from visibility. These are different kinds of claim and the document
  must not flatten them.
- **An explicit "what we don't know" section** — blind applications, unexplained
  transitions, low-confidence episodes, insufficient-data groups. Stage 1 through
  Stage 5 each generate honest uncertainty; **this is where it either survives or
  gets quietly dropped**, and dropping it would waste the entire evidential design.

That is a difference in *editorial standard*, not in technology. It is worth
building and worth describing accurately — as a better document, not as an
invention.

### 5.3 Can "is it understandable?" be tested?

**The objection:** comprehension is subjective; the architecture's checkpoint
("someone who has never seen the task performed can read this output and
understand exactly what the process is") sounds like a vibe rather than a test.

**The answer:** it can be operationalised. Give the document to someone
unfamiliar with the process and have them (a) answer factual questions about it
(*what triggers the Excel check? what are the possible outcomes? which systems are
involved?*), (b) reconstruct the step order from a shuffled list, and (c) rate
their confidence. Score against the model. That is a measurable test with a
pass/fail line, and it is the only external check that matters at this stage.

**Caveat noted honestly:** I did not find a validated instrument for this in the
literature, so the test design in the blueprint is mine. It is better than no
test, but it is not a standard.

---

## 6. Novelty check (required)

**Not novel.** UiPath Task Mining exports Process Definition Documents from
observed task activity today. BPMN export is standard. Document templating is
ordinary engineering.

The distinguishing feature is editorial: **evidence provenance for every claim and
an explicit statement of what is not known.** That is a quality standard, not a
technical mechanism, and should be presented that way.

**Not "apply an LLM to X"** — and a warning attaches here. The obvious shortcut is
to feed the mined model to a language model and have it write the document. That
would produce fluent prose and would **break the one thing that makes this output
worth having**: every sentence traceable to a number. Any generated prose must be
template-driven from the model, with an LLM permitted at most for *rephrasing*
sentences whose factual content is fixed — never for producing claims.

---

## 7. Conclusion / recommendation

Generate the document from a **native JSON process description** (the
authoritative artefact), with BPMN 2.0 XML exported alongside for
interoperability and OCEL 2.0 retained from Stage 3. Build the human-readable
document with deterministic templating (Jinja2 → Markdown/HTML), every claim
carrying its support figures and evidence tier. Include a mandatory **"what we
don't know"** section assembled automatically from the uncertainty each earlier
stage recorded. Validate with a real comprehension test against people unfamiliar
with the process.

**What would change this call:** if comprehension testing shows readers ignore or
misread the evidence annotations, the annotations need redesigning — not removing.
The finding would be about presentation, not about whether to be honest.

---

## 8. Open items requiring a human decision

1. **Obtain a sample UiPath PDD** and decide whether to match its skeleton.
   Matching aids adoption by teams who already work that way; diverging lets us
   structure around evidence. I lean towards matching the skeleton and adding our
   sections, but that is a product decision.
2. **Delivery format.** Markdown/HTML is easiest and most diffable; enterprises
   often want Word or PDF. Affects tooling choices.
3. **Who is the reader?** A process analyst, an automation developer, and an
   auditor want different documents from the same model. The architecture says
   "a person who has never seen the task performed", which suggests the analyst —
   worth confirming, since it drives the level of detail.
