# Research Log — Stage 5: telling what kind of process it is

**Stage / Phase:** Stage 5 — process-type classification
**Author:** Claude Code session (Opus 5)
**Status:** concluded for blueprint purposes. **This is the stage CLAUDE.md's
rule 3 was written for, and §6 gives the blunt answer.**

---

## 1. Question being investigated

Stage 4 produces a *shape*. Stage 5 must add *meaning*: "this looks like a QA/QC
review." Three questions:

1. Does a standard taxonomy of business processes already exist, or do we invent
   categories?
2. How do you classify a process from its shape and its on-screen language, with
   almost no labelled training data?
3. **Is there any way to do this that isn't just "ask an LLM"?** — and if not, is
   that acceptable?

---

## 2. What was actually checked

**Verified:**

- **APQC Process Classification Framework (PCF)** — [apqc.org/process-frameworks](https://www.apqc.org/process-frameworks). "A taxonomy of business processes that allows organizations to objectively track and compare their performance internally and externally with organizations from any industry." Organised into **12–13 enterprise-level categories** (version-dependent) covering process groups and **more than 1,000 processes and associated activities**. Developed in the early 1990s by APQC with member companies as an **open standard**, cross-industry, with per-category documents giving definitions and key measures. Current cross-industry version referenced in sources: **7.4** (also 7.3.1, 7.2.1). A public PDF copy of v7.4 is mirrored at [solutions.ifrc.org](https://solutions.ifrc.org/sites/default/files/2024-10/K014750_APQC%20Process%20Classification%20Framework%20(PCF)%20-%20Cross%20Industry%20-%20PDF%20Version%207.4.pdf).
- **Rebmann & van der Aa, *Extracting Semantic Process Information from the
  Natural Language in Event Logs*, CAiSE 2021** ([arXiv 2103.11761](https://arxiv.org/abs/2103.11761), [PDF](https://hanvanderaa.com/wp-content/uploads/2021/03/CAISE2021-Extracting-Semantic-Process-Information-from-the-Natural-Language-in-Event-Logs.pdf)). Performs **semantic role labelling of event data**, combining analysis of textual attribute values using a state-of-the-art language model with a novel attribute classification technique, extracting **up to eight semantic roles per event**. Evaluated quantitatively over a range of event logs. Follow-up: *Enabling semantics-aware process mining through the automatic annotation of event logs*, Information Systems, 2022.
- **Process model similarity measures.** Techniques are either **structural**
  (graph edit distance) or **behavioural** (activity profiles / execution
  semantics). Three metric families: node-matching similarity (labels and
  attributes), structural similarity (labels + topology), behavioural similarity
  (labels + causal relations). TAGER computes similarity via edit distance over
  **coverability graphs**, which represent a Petri net's behaviour well. Noted
  gap in the literature: "structural techniques may be fast but inaccurate,
  behavioural approaches accurate but complex." Sources: [Dijkman et al., *Similarity of business process models: Metrics and evaluation*](https://www.sciencedirect.com/science/article/abs/pii/S0306437910001006), [TAGER](https://link.springer.com/content/pdf/10.1007/978-3-662-45563-0_11.pdf).
- **Weak supervision (Snorkel).** Subject-matter experts write **labelling
  functions** expressing heuristics, patterns and distant supervision; Snorkel
  combines their outputs with an **unsupervised generative model that learns from
  agreements and disagreements among labelling functions, without requiring
  labelled data**, producing probabilistic labels to train a downstream
  classifier ([Snorkel paper, arXiv 1711.10160](https://arxiv.org/pdf/1711.10160)).
- **LLMs as labelling functions, not as classifiers.** *Language Models in the
  Loop: Incorporating Prompting into Weak Supervision* ([arXiv 2205.02318](https://arxiv.org/pdf/2205.02318), ACM/IMS J. Data Science) — prompting a model with multiple distinct queries per example and **denoising those noisy label sources with weak supervision** achieved an average **19.5% reduction in errors over zero-shot** on the WRENCH benchmark. Reported alongside: zero-shot LLM approaches "can be unreliable when the language model has noisy outputs and is sensitive to the wording of the prompt", and BERT used out-of-the-box as a zero-shot classifier "yields poor results, significantly underperforming human-generated labeling functions."
- **Practical weak-supervision trade-offs** (Snorkel AI's own guidance): worth it
  when you'd rather have 100,000 "pretty good" labels than 100 perfect ones;
  performs best on **structured text**, less well where contextual human judgment
  dominates; end-to-end LLM labelling carries "unacceptable computational/monetary
  cost" at scale.

**Recalled, not verified:**

- APQC PCF's licensing terms for commercial redistribution. It is described as an
  open standard and PDFs are publicly mirrored, but **whether we may embed the
  taxonomy in a product is not established**. Check before shipping.
- Whether any published work classifies *process type* (as opposed to matching or
  measuring similarity between models). I found similarity measures and semantic
  annotation, but **no paper that does what Stage 5 asks for directly**. Absence
  of evidence here, not evidence of absence — my searching was shallow.

**Not checked:**

- The MIT Process Handbook (a well-known process taxonomy) — named from memory,
  not searched. Worth checking as a second taxonomy source.
- Industry-specific QA/QC process standards (ISO 9001 process definitions, etc.)
  that might supply better category definitions than a generic taxonomy.

---

## 3. Prior art / existing solutions found

| What | Who | Type | Relevance |
|---|---|---|---|
| Open cross-industry taxonomy: 13 categories, 1,000+ processes, with definitions | APQC PCF | Open standard | **Use it. Don't invent categories.** Gives us a label vocabulary that already means something to a business audience |
| Semantic role labelling of event log text (8 roles per event) | Rebmann & van der Aa, CAiSE 2021 | Academic | Closest published method for the "language" half of Stage 5 |
| Structural / behavioural process model similarity (graph edit distance, coverability graphs, behavioural profiles) | Dijkman et al.; TAGER | Academic | The "shape" half — compare a discovered model against reference shapes |
| Weak supervision: combine noisy labelling functions without labelled data | Snorkel | OSS + academic | The right framework for our few-labels situation |
| LLM prompts as labelling functions, denoised by weak supervision (−19.5% error vs zero-shot) | Language Models in the Loop | Academic | **The defensible way to use an LLM here** |
| Process type labelling from shape + on-screen language | — | **Nothing found** | Possibly a gap; possibly just an unsearched corner. Do not claim novelty on this basis |

---

## 4. Options considered

**For the shape half:** structural signature rules (does the model end in an
exclusive choice between two terminal activities?) · graph edit distance against
reference models · behavioural profiles · learned graph embeddings.

**For the language half:** keyword/lexicon matching against a taxonomy ·
TF-IDF + linear classifier · sentence embeddings + nearest-centroid · semantic
role labelling (Rebmann & van der Aa) · LLM prompt.

**For combining and deciding:** hand-written rules · weak supervision (Snorkel) ·
supervised classifier · LLM end-to-end.

---

## 5. Debate — for and against

### 5.1 The honest framing: what would "just use an LLM" look like, and why not?

**The LLM-only approach — case for.** Hand the activity names, button labels and
model structure to a capable model and ask "what kind of process is this?" It
would probably work well *today*, with almost no engineering. It handles wording
variation and domain vocabulary we never anticipated. For a product feature,
this is a genuinely reasonable engineering choice, and pretending otherwise would
be precious.

**The LLM-only approach — case against.** Four concrete problems, in order of how
much they matter here:

1. **It is not patentable, and the project cares about that.** CLAUDE.md's rule 3
   exists precisely for this: "apply an LLM to an existing classification task" is
   the textbook obviousness rejection. If Stage 5 is LLM-only, it contributes
   nothing to defensibility.
2. **It can't explain itself in a way that survives challenge.** The architecture
   requires a person to confirm or correct the first several guesses. "The model
   says QA/QC" gives a reviewer nothing to correct — whereas "ends in an
   exclusive choice between *Approve* and *Reject*, contains a comparison step,
   and the screen vocabulary includes *Reviewer Comments* and *Compliance Check*"
   can be argued with.
3. **Prompt sensitivity.** Published work notes zero-shot approaches "can be
   unreliable when the language model has noisy outputs and is sensitive to the
   wording of the prompt". A classification that changes because someone reworded
   a prompt is not a measurement.
4. **It sends captured workplace content to a model.** After Stage 1 went to
   considerable lengths to keep content on-device, shipping screen vocabulary to
   an external API would undo that — a *deployment* problem, not just a
   philosophical one.

**Call: shape rules + taxonomy-matched language evidence as the primary
mechanism; an LLM permitted only as one labelling function among several,
denoised by weak supervision, and never as the sole voice.** This is not
anti-LLM squeamishness — it is the finding from *Language Models in the Loop*,
where prompts used as labelling functions and denoised with weak supervision beat
zero-shot by ~19.5% error reduction. The same design gives us explainability and
keeps the LLM optional, which also means the system still works for a customer
who forbids external model calls.

### 5.2 Invent categories or adopt APQC PCF?

**Invent — for:** our categories can be exactly what matters for this product
(QA/QC vs data entry vs exception handling), with no irrelevant baggage.
**Invent — against:** we would be building a worse version of something that has
existed as an open standard since the early 1990s, refined by many companies
across industries, with **definitions and key measures already written** for
1,000+ processes. Our labels would also mean nothing to a business audience that
already benchmarks against PCF.

**Call: adopt APQC PCF as the label vocabulary**, with a small local extension
for distinctions it doesn't make that we care about. **Verify the licence before
embedding it in a product** — "open standard" is not the same as "free to
redistribute commercially."

This also reframes Stage 5 usefully: it stops being "is this QA/QC, yes or no?"
and becomes "which PCF category does this process most resemble, and how
confidently?" — a better-posed question with an existing answer key.

### 5.3 Shape: rules vs. model similarity

**Structural signature rules — for:** directly encode the architecture's own
insight — "opens a record, compares information, ends in approve/reject." Each
rule is a sentence a domain expert can check. No training data needed.
**Rules — against:** brittle to structural variation; someone must write them; and
they won't generalise to process types nobody anticipated.

**Graph edit distance against reference models — for:** principled, established,
handles variation more gracefully.
**GED — against:** **we have no library of reference process models to compare
against.** Without reference models this technique has nothing to measure against,
and building that library is a research project of its own. The literature also
notes structural methods are "fast but inaccurate" while behavioural ones are
"accurate but complex".

**Call: structural signature rules now; revisit similarity measures once a
library of confirmed models exists** (which Stage 5's own human-confirmation loop
will slowly build). Note the dependency: the better technique becomes available
only after the cruder one has been running for a while. That's a reason to design
the confirmation loop to *store* confirmed models from day one.

### 5.4 How much labelled data will we actually have?

Almost none. Realistically a handful of confirmed process labels early on — which
rules out supervised classification and is exactly the situation weak supervision
was designed for: combine several noisy voters (shape rules, vocabulary matches,
taxonomy similarity, optionally an LLM prompt) using a generative model that
learns from their agreements and disagreements **without labelled data**.

The caveat from Snorkel's own guidance is relevant: weak supervision "performs
best in structured text" and less well where contextual human judgment dominates.
Our inputs — button labels, screen titles, structural signatures — are about as
structured as text gets, which is a point in its favour.

---

## 6. Novelty check (required) — the blunt answer

**Stage 5 is not novel, and the honest thing is to say so plainly rather than
dress it up.**

Classifying a thing from its structural features and its associated text is
ordinary applied machine learning. Taxonomies of business processes already exist
(APQC PCF, 1,000+ processes, since the early 1990s). Semantic extraction from
event log language is published (Rebmann & van der Aa, CAiSE 2021). Process model
similarity has a mature literature.

**Applying CLAUDE.md rule 3 directly:** is the novel part a specific technical
mechanism, or is it "apply an LLM to Y"? For Stage 5, **if built the tempting way,
it is exactly "apply an LLM to Y"** — and no amount of framing changes that. The
blueprint therefore builds it the unglamorous way (rules + taxonomy + weak
supervision, LLM optional and subordinate), not because that is more inventive —
it isn't — but because it is **explainable, correctable, auditable, and it keeps
captured workplace content on the device**. Those are product virtues, not
patent virtues, and they should be claimed as such.

**Recommendation: do not attempt to claim anything at Stage 5.** The project's
defensibility rests on Stages 1–3. Stage 5 should be judged on whether a human
reviewer finds its guesses useful and easy to correct.

---

## 7. Conclusion / recommendation

1. **Adopt APQC PCF as the label vocabulary** (licence check first), with a local
   extension for distinctions we need.
2. **Shape evidence:** hand-written structural signature rules over the Stage 4
   model — terminal exclusive choice, presence of a comparison step, read-heavy
   vs. write-heavy profile, cross-application lookup pattern.
3. **Language evidence:** match `ui_chrome` vocabulary (retained in clear by
   Stage 1) against taxonomy category terminology; optionally adopt semantic role
   labelling for richer extraction.
4. **Combine with weak supervision** (Snorkel-style), each evidence source as a
   labelling function, producing a probabilistic label with the contributing
   evidence listed.
5. **LLM strictly optional** — one additional labelling function, off by default,
   never the sole voice, and never sending content off-device without explicit
   configuration.
6. **Human confirmation loop**, as the architecture requires, with confirmations
   stored as growing ground truth *and* as a reference model library that unlocks
   better shape methods later.

**What would change this call:** if a handful of structural rules plus vocabulary
matching turns out to classify far worse than a plain LLM prompt on real data,
then the honest answer is to use the LLM for the product and **stop describing
Stage 5 as a contribution** — not to keep a weaker mechanism for the sake of a
story.

---

## 8. Open items requiring a human decision

1. **APQC PCF licensing for commercial use.** Described as an open standard,
   publicly mirrored — but redistribution rights inside a product are
   **unverified**. Needs checking before it is embedded.
2. **Is an LLM allowed in the product at all?** This is a deployment and
   trust decision as much as a technical one: sending screen vocabulary to an
   external model would undo Stage 1's on-device posture. A local model would
   avoid that at a hardware cost. **Needs an explicit policy**, not a default.
3. **How many categories do we actually need?** PCF has 1,000+ processes. For a
   first version, a shortlist (QA/QC review, data entry, exception handling,
   reconciliation, approval routing) is probably enough — but which shortlist is a
   domain question.
