# Stage 6 — Write it down

*Plain-English walkthrough. Technical version: `../plans/stage-6-blueprint.md`.
Evidence: `../research/stage-6-output.md`.*

---

## What this stage does

Everything so far has been building towards one thing: **a document**.

Not a video. Not a dashboard. Not a vague summary. A clear written description of
how the work actually gets done — readable by someone who has never watched the
job being performed.

That's the product. Stage 6 makes it.

---

## And then it stops

The architecture is explicit about this and it's worth repeating: **turning this
description into working automation is somebody else's job.**

Pulse's job ends at producing a clear, trustworthy description of the real
process. That boundary goes *into the document itself*, so nobody mistakes it for
an automation specification.

---

## Honest note: this isn't new either

UiPath's Task Mining already exports something called a **PDD** — a Process
Definition Document — generated from watching people work. Automated process
documentation is a shipping product feature.

**So what's different about ours?** Not the technology. The *editorial standard*:

| A typical generated process doc | Ours |
|---|---|
| "Reviewers check the document library." | "In 388 of 400 observed cases (97%, CI 94–98%), the reviewer opened the document library before deciding." |
| An arrow between two systems | An arrow that says *"proven by copy/paste in 240 cases"* — or *"inferred from on-screen visibility in 8 cases"* |
| Describes what it found | **Also describes what it couldn't see** |

Theirs exists to seed an automation project. Ours exists to be **trusted as a
description of reality**. That's a different bar, and it drives different content.

---

## What the document contains

```
 ┌─────────────────────────────────────────────────────────────┐
 │  QA REVIEW OF LOAN APPLICATIONS                              │
 ├─────────────────────────────────────────────────────────────┤
 │                                                              │
 │  IN ONE PARAGRAPH                                            │
 │    What this is, who does it, how often, how sure we are     │
 │                                                              │
 │  THE SYSTEMS INVOLVED                                        │
 │    LoanDesk · DocVault · Excel — and what each is used for   │
 │                                                              │
 │  THE MAIN PATH                                               │
 │    Step by step, each with how consistently it appears       │
 │                                                              │
 │  HOW INFORMATION MOVES BETWEEN SYSTEMS       ← our speciality│
 │    "The loan ID is carried from LoanDesk to DocVault.        │
 │     Proven by copy/paste in 240 of 400 cases."               │
 │                                                              │
 │  WHERE IT VARIES                                             │
 │    "31% also open Excel — when the income figures disagree"  │
 │                                                              │
 │  EXCEPTIONS AND REWORK                                       │
 │                                                              │
 │  WHAT KIND OF PROCESS THIS IS                                │
 │    With its reasoning, and whether a human confirmed it      │
 │                                                              │
 │  ⚠ WHAT WE DON'T KNOW                        ← mandatory     │
 │    "Activity in the mainframe terminal could not be          │
 │     observed. Steps performed there are missing."            │
 │                                                              │
 │  HOW THIS WAS PRODUCED                                       │
 │    12 people, 6 weeks, 400 cases. Describes observed         │
 │    reality — not policy, not the procedure manual.           │
 └─────────────────────────────────────────────────────────────┘
```

---

## The five phases

### Phase 6.1 — Make every claim traceable

**What we're building:** the underlying data file the document is generated from,
with a rule enforced in the structure itself:

> **A percentage is not allowed to exist without its numbers behind it.**

You can't write `97%`. You have to write `{value: 97%, 388 of 400, confidence
interval 94–98%, source: Stage 4 frequency analysis}`. The schema **rejects**
anything else, so the rule can't quietly erode when someone's in a hurry.

And the chain runs all the way down: document claim → process model → episodes →
raw events. Anyone asking *"how do you know that?"* gets an answer.

**How you test it:** pick 20 claims at random from a generated document and trace
each one back to the actual recorded events. All 20 must trace.

---

### Phase 6.2 — Write the document

Templates, filled in from the data. Every sentence is a template.

**The evidence goes in the sentence, not in a footnote.** *"In 388 of 400 observed
cases (97%), the reviewer opened the document library before deciding"* reads
naturally **and** carries its proof. Footnoted evidence gets skipped by every
reader who ever lived.

**And a rule that matters:** **no AI-generated prose for factual claims.** It
would be faster and read more smoothly, and it would destroy the single property
that makes this document worth more than a competitor's — that every sentence
traces back to a number. An LLM may be allowed to *rephrase* a sentence whose
facts are already fixed, and that's off by default.

**How you test it:** an automated check that no sentence contains an unsupported
number. Zero tolerance.

---

### Phase 6.3 — Pictures and machine-readable files

**For the humans:** a **swimlane diagram** — steps grouped by which system they
happen in, with the connections between systems drawn between lanes. That picture
is the one that shows what this project does that a normal process tool doesn't.

The connections are drawn differently depending on evidence:
- **Solid line** = proven (copy/paste)
- **Dashed line** = inferred (visibility)
- **Dotted with a "?"** = we saw them move between systems and don't know how the
  two were connected

**Deliberately distinguishable in greyscale**, not by colour — because diagrams get
screenshotted and pasted into slide decks, away from their legends.

**For the machines:** we export **BPMN 2.0** — the standard business process
format that tools like Camunda and bpmn.io read — using PM4Py, which converts our
model and keeps a mapping back to the original so the evidence chain survives.

**One caveat we state openly in the export:** BPMN has no way to express *"this
link is proven by copy/paste in 240 cases"* or *"we don't know how these
connect."* That information goes into extension attributes that most tools will
silently drop. **So the BPMN file is a view, not the truth** — our own JSON stays
authoritative. We say that in the file header so nobody round-trips through BPMN
and loses the evidence without noticing.

---

### Phase 6.4 — "What we don't know" *(the section that makes it trustworthy)*

Every previous stage generated honest uncertainty. **This is where it either
reaches the reader or gets quietly dropped.**

It's assembled automatically:

- **Blind systems** (from Stage 1) — *"Activity in the mainframe terminal could not
  be observed. Steps performed there are missing from this description."* **This
  is probably the single most important sentence in the whole document** for a
  reader deciding how much to trust it.
- **Unexplained connections** (Stage 3) — *"In 23 cases the reviewer moved from A
  to B and we could not determine how they were connected."*
- **Cases we weren't confident about** (Stage 2), and how many were excluded.
- **Variants we saw too rarely to describe** (Stage 4).
- **How well the map fits reality** — *"this description accounts for 87% of
  observed behaviour."*
- **How much evidence this is built on** — *"12 people, 6 weeks, 400 cases."*
  A process mined from 3 people over 2 weeks is a completely different claim from
  one mined from 40 over 6 months, and the document must make that impossible to
  miss.

**How you test it:** deliberately break the input — blind one application,
degrade some episodes — and check that every injected limitation shows up in this
section. 100%, no exceptions.

**A document that claims no limitations is itself a defect.**

---

### Phase 6.5 — Give it to someone who's never seen the job

The architecture's checkpoint sounds untestable — *"someone who has never seen the
task performed can read this and understand it."* It isn't. Here's the test:

1. Find 3–5 people unfamiliar with the process.
2. Give them **only the document**. No briefing.
3. Measure:
   - **Can they answer factual questions?** *What triggers the Excel check? What
     are the possible outcomes? Which systems are involved?* (10 questions, real
     answers)
   - **Can they put shuffled steps back in order?**
   - **Are they appropriately confident?** — and here's the subtle one:
     **overconfidence is a document failure.** If readers feel certain about things
     the evidence doesn't support, the writing sounds more definite than the data,
     which is exactly what the "what we don't know" section exists to prevent.
4. Separately, a **domain expert** checks it for correctness — being understandable
   and being right are different failures needing different readers.

**To pass Stage 6:**

| What | Must be |
|---|---|
| Unfamiliar readers answer correctly | ≥ 80% |
| They can reconstruct the step order | ≥ 80% |
| Their confidence is calibrated (not overconfident) | yes |
| Domain expert says it's accurate | yes, minor corrections only |
| Every claim traceable to evidence | 100% |
| "What we don't know" present and correct | 100% |
| BPMN file opens in a third-party tool | yes |

> Being straight: I couldn't find an established, validated way to test
> comprehension of generated process documents, so **this test is my own design**.
> It's much better than no test, but it isn't a standard — if a proper instrument
> exists, use that instead.

---

## What you'll have when Stage 6 is done

✅ A document a newcomer can read and understand, where every claim shows its
evidence and every gap is stated.

✅ Machine-readable exports (BPMN 2.0, OCEL, JSON) for other tools.

✅ Diagrams that show the process *across systems*, with connection strength
visible.

✅ Measured proof that people who've never seen the job can actually understand it.

**And that's the product.** Everything after this is either optional maintenance
(Stage 7) or somebody else's project.

---

## Worth debating

1. **"Should we match UiPath's PDD format?"** They're the de facto convention, so
   matching their skeleton would ease adoption for teams that already work that
   way. But their structure is built for seeding automation, and ours has better
   material (evidence, gaps). I lean towards **matching the skeleton and adding our
   sections** — but I haven't actually seen a sample PDD, and we should get one
   before deciding.

2. **"Someone is going to ask you to delete the 'what we don't know' section."**
   Almost certainly, because it makes the product look less capable in a sales
   setting. **Deleting it turns a trustworthy description into a confident guess** —
   which is the exact thing this tool was built not to be. I've made it
   structurally mandatory rather than a template option, on purpose. If you
   disagree, that's a decision worth making explicitly.

3. **"Why not let an AI write the prose? It'd read better."** It would, and it'd
   be faster. And it would break traceability — the one property that makes this
   document worth more than a competitor's. Templates for facts, rephrasing only.

4. **Who's the reader?** An analyst, an automation developer, and an auditor want
   different documents from the same data. The architecture implies the analyst.
   Worth confirming, since it sets how much detail goes in.

5. **What format do you actually need?** Markdown/HTML is easiest and
   version-controllable. Enterprises often want Word or PDF. Affects the tooling.
