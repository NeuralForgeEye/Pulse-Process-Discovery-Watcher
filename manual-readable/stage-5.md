# Stage 5 — Work out what kind of process it is

*Plain-English walkthrough. Technical version: `../plans/stage-5-blueprint.md`.
Evidence: `../research/stage-5-process-type-labelling.md`.*

---

## What this stage does

Stage 4 gave us a **shape**: a map with boxes and arrows showing what people
actually do.

Stage 5 adds **meaning**: *"this is a quality review process."*

That's the whole job. It's the smallest stage in the project, and it should stay
that way.

---

## Let me be straight with you first

**This stage is not novel, and I'd be lying if I dressed it up.**

Classifying something from its features and its associated words is ordinary
machine learning. Taxonomies of business processes already exist — there's an
open standard with 1,000+ defined processes that's been maintained since the
early 1990s. Extracting meaning from process language is published academic work.

More importantly: **if we build this the tempting way, it is literally "just ask
an LLM"** — which is exactly the failure mode your own project rules call out.

So I want to be clear about what's happening here: I'm building it the
*unglamorous* way, and **not because that makes it inventive**. It doesn't. I'm
doing it because the unglamorous way is explainable, correctable, and keeps
captured workplace content on the machine — which are product virtues, not patent
virtues.

**Your defensibility lives in Stages 1–3. Don't let anyone tell you it lives here.**

---

## The idea: two clues that don't depend on each other

The architecture's insight is good, and it's this: there are **two independent
ways** to tell what kind of process you're looking at.

```
   CLUE 1 — THE SHAPE                    CLUE 2 — THE WORDS
   (from Stage 4's map)                  (from Stage 1's capture)

   ┌──────────────────────┐              Buttons on screen:
   │ Open a record        │                • "Approve"
   │        ↓             │                • "Reject"
   │ Look something up    │                • "Reviewer Comments"
   │ in another system    │                • "Compliance Check"
   │        ↓             │
   │ Compare the two      │              Screen titles:
   │        ↓             │                • "Loan Review"
   │   ╱          ╲       │                • "QC Queue"
   │ Approve    Reject    │
   └──────────────────────┘

   "Opens a record, compares,            "The vocabulary of this
    ends in a two-way decision"           screen is review language"

                    ╲            ╱
                     ╲          ╱
                      ▼        ▼
              ┌─────────────────────┐
              │  Both clues agree   │
              │  → QA/QC review     │
              │     (confident)     │
              └─────────────────────┘
```

**Why "independent" matters.** The shape comes from analysing behaviour. The words
come from reading the screen. Neither one causes the other. So when they agree,
that agreement is genuine corroboration rather than the same evidence counted
twice — the same principle that makes Stage 3's evidence tiers work.

---

## Don't invent categories — use the standard one

A useful find: the **APQC Process Classification Framework** is an open,
cross-industry taxonomy of business processes — 13 top-level categories, 1,000+
processes, each with a written definition, maintained since the early 1990s by
companies across many industries.

**So the question changes shape.** Instead of "is this QA/QC, yes or no?" —
which is a question we invented and only we can grade — it becomes *"which
established category does this process most resemble?"* That's a better question,
and someone else already wrote the answer key.

It also means our labels mean something to a business audience that already uses
this framework for benchmarking, instead of being Pulse-specific jargon.

⚠️ **One thing to check:** "open standard" doesn't automatically mean "free to
put inside a commercial product." That licence question needs answering before
we embed it. Flagged as a blocker.

---

## The five phases

### Phase 5.1 — Decide what the possible answers are

Pick a shortlist from the standard taxonomy — QA/QC review, data entry,
exception handling, reconciliation, approval routing, research/lookup — and write
down, for each one, **what would have to be true for this label to apply.**

Those written definitions become the actual rules in the next phase, so they're
written as testable statements rather than prose.

**And `unknown` is always an available answer.** A classifier that can't say "I
don't recognise this" will shove every process into the nearest box, which is
worse than silence.

**How you test it:** a domain expert reads the shortlist and, for every pair of
labels, states what would tell them apart. **If a human can't distinguish two
labels, no algorithm will** — drop one.

---

### Phase 5.2 — Read the shape

We write rules that examine Stage 4's map. Each one is a single testable question:

- Does it **end in a choice between two or more final actions**? (Approve/Reject —
  the strongest QA signal there is)
- Is there a **comparison** — the same value looked at in two systems before a
  decision? (Stage 3 already tells us this)
- Is it **read-heavy or write-heavy**? (Reviewing vs. data entry)
- Is there a **cross-system lookup** — take a value from system A, search system B?
- Is there **rework** — people redoing steps?

Each rule reports **how often it holds**, not just yes/no. A pattern true in 95%
of cases is different evidence from one true in 55%.

**One technique we're deliberately NOT using yet.** There's an established method
for comparing process maps to each other (graph edit distance). It's good. But it
needs a **library of reference maps to compare against — and we don't have one.**
We'll accumulate that library from Phase 5.5's human confirmations, and revisit
then. Noting the dependency so it doesn't get forgotten.

**How you test it:** on a process built to be a QA review, the decision-ending
rule and the comparison rule must both fire. On a pure data-entry process with no
decision, both must stay silent. **A rule that fires on everything isn't evidence.**

---

### Phase 5.3 — Read the words

Stage 1 kept button labels and screen titles in plain text — deliberately, because
they're not personal data. **This is the payoff for a decision made four stages
earlier.**

We match that vocabulary against the taxonomy's terminology (*approve, reject,
verify, compliance, sign-off, reconcile*).

**The detail that makes this work: position matters enormously.** The word
"Approve" on the **final button of the process** is nearly decisive. The word
"approve" buried in a help menu is noise. Same word, completely different
evidential weight. So matches are weighted by where they sit in the structure.

**The real-world messiness we handle:** buttons in other languages, company
jargon, in-house abbreviations. The term list is editable config, and words that
show up a lot but match nothing get surfaced for a human to map — that list is
itself a useful artefact.

**How you test it — with a trap:** build a fake process that has QA-ish words
scattered in incidental places but no decision structure at all. It must **not**
come out as QA/QC. That proves the position weighting is doing real work rather
than just counting words.

---

### Phase 5.4 — Put the clues together

Each rule and each word-match is a **voter**. We combine the votes.

**The method: "weak supervision"** (the well-known framework here is Snorkel).
Instead of needing thousands of labelled examples — which we won't have; we'll
have a handful — it learns from **where the voters agree and disagree with each
other**, and produces a probabilistic answer with no labelled data at all.

It's a good fit for us for a specific reason: published guidance notes weak
supervision works best on **structured text**, and button labels plus structural
rules are about as structured as text gets.

**And the LLM question, answered explicitly.**

An LLM *may* be used here — but as **one voter among many**, never as the judge:

- **Off by default.** The whole product must work without it.
- It sees step names and vocabulary — **never raw captured content** — and doesn't
  leave the machine unless someone explicitly turns that on. Stage 1 worked hard
  to keep content local; this stage must not quietly undo it in the last mile.
- Its vote gets weighed against the others, not trusted on its own.
- **Its answer is never the explanation shown to a human.** The justification has
  to be the actual evidence — because a reviewer can argue with *"ends in
  Approve/Reject and the vocabulary is review language"* and cannot argue with
  *"the model said so."*

This isn't squeamishness about LLMs — it's what the research actually supports.
Published work found that using prompts **as voters, denoised by weak
supervision**, cut errors by about 19.5% compared to just asking the model
directly, and noted that zero-shot classification is unreliable and **sensitive to
how the prompt is worded**. A classification that changes because someone reworded
a prompt isn't a measurement.

**How you test it:** run shape-only, words-only, and both-together. **If one clue
alone does just as well as both, say so** — the two-clue design would then be
unnecessary complexity, and that's worth knowing. Also run with and without the
LLM voter, so you know honestly what it's worth.

---

### Phase 5.5 — Let a human confirm it

The architecture requires this, and it's right: a person confirms or corrects the
first several guesses, so trust is *earned* before anything runs unsupervised.

The review screen shows the proposed label, the confidence, the evidence, the
plain-English justification, and the map itself.

**Three things happen with each confirmation:**
1. It becomes training data. **Corrections are worth more than confirmations** —
   a correction tells you exactly which rule misfired.
2. The confirmed map goes into the **reference library** — which is what
   eventually unlocks the better shape-comparison technique we deferred in 5.2.
   We start storing from day one even though nothing uses them yet.
3. Accuracy over time gets tracked. The system only proposes labels unsupervised
   once accuracy on genuinely new processes clears a bar. That's the
   architecture's "trust is earned" requirement, made measurable.

**To pass Stage 5:**

| What | Must be |
|---|---|
| Right label first time (new processes) | ≥ 70% |
| Right label in the top 2 | ≥ 90% |
| Correctly says "unknown" for odd processes | ≥ 80% |
| Justification judged useful by the reviewer | ≥ 80% |
| Review time per process | under 2 minutes |
| **Works with the LLM turned off** | **required** |

**Why only 70% first-time?** Because the architecture's actual bar isn't accuracy
— it's that *"a human only needs to glance and confirm, not diagnose from
scratch."* A wrong-but-close guess with good reasoning attached beats a right
guess with no explanation. That's why "top 2" and "is the justification useful"
matter more here than top-1 accuracy.

---

## What you'll have when Stage 5 is done

✅ Each discovered process comes with a proposed type, a confidence, the evidence
behind it, and a sentence explaining the reasoning in English.

✅ A review screen where a person confirms or corrects in under two minutes.

✅ A growing library of confirmed processes that makes the system better over time
— and unlocks better techniques later.

❌ **It's still not a document.** That's Stage 6.

---

## Worth debating

1. **"Is this stage even worth building?"** Genuinely asking. If Stage 4's map is
   good and Stage 6 makes it readable, a reader looking at a map that ends in
   Approve/Reject can probably tell it's a review process without being told. The
   honest test is: **put the map in front of someone and see whether the label adds
   anything.** If it doesn't, this becomes a one-line heading and the effort moves
   to Stage 6. I'd rather find that out than build it on assumption.

2. **"Why not just use an LLM and move on?"** Honestly? For a product feature it'd
   probably work fine today. Three reasons I didn't default to it: it contributes
   nothing to defensibility (your rules call this out specifically); it can't
   produce an explanation a reviewer can argue with; and it would send workplace
   screen vocabulary off the device after four stages of keeping it local. If you
   decide those don't matter, the LLM path is one config flag away — I built it so
   that's possible.

3. **"Are you overfitting to QA/QC?"** A real risk. If the rules and vocabulary
   are tuned to quality reviews, everything else gets labelled "not QA/QC", which
   is a useless distinction dressed up as a classification. The negative controls
   are there to catch it, but the shortlist needs several genuinely different
   process types from the start.

4. **The taxonomy licence is a genuine blocker.** Needs answering before we embed
   it. The fallback — our own taxonomy shaped by theirs — is weaker but workable.

5. **Should an LLM be allowed in this product at all?** That's a policy call about
   trust and deployment, not a technical one, and it interacts with whatever was
   promised to the people being recorded. I've defaulted it to **off** so that not
   deciding doesn't quietly become a decision.
