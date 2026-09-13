# Stage 5 Blueprint — Telling what kind of process it is

**Source of truth:** `plans/pulse-architecture.md`, Stage 5.
**Research backing:** `research/stage-5-process-type-labelling.md`.
**Plain-English version:** `manual-readable/stage-5.md`.
**Status:** blueprint only — no implementation code has been written.

> **Stated plainly up front:** this stage is **not novel** and should not be
> claimed as such. Built the tempting way it is literally "apply an LLM to a
> classification task" — the exact pattern CLAUDE.md rule 3 warns against. It is
> built here the unglamorous way for product reasons (explainable, correctable,
> on-device), not because that makes it inventive.

---

## 1. Stage goal

Stage 4 produces a *shape*: a sound process model with backbone steps, branches
and cross-application links. Stage 5 adds *meaning* — proposing what kind of
process it is, so that Stage 6's document can say "this is a quality review
process" rather than just showing a diagram. It does that from two independent
clues, exactly as the architecture specifies: the **shape** itself (a process that
opens a record, compares information, and ends in an approve/reject decision has
a recognisable QA/QC form) and the **on-screen language** captured in Stage 1
(*Approve*, *Reviewer Comments*, *Compliance Check*). The two clues are
independent, which is what makes their agreement meaningful. Every guess is
proposed with its evidence and confirmed or corrected by a person, so trust is
earned before the label is relied on — and each confirmation becomes training
data and a reference model for later.

---

## 2. Phases

Five phases. This stage is smaller than the others and should stay that way; the
effort belongs in Stages 1–4.

---

### Phase 5.1 — Adopt a label vocabulary

**Goal.** Decide what the possible answers are, before building anything that
produces answers.

**Build steps**

1. **Adopt the APQC Process Classification Framework (PCF)** as the base
   vocabulary — an open cross-industry taxonomy developed since the early 1990s,
   with 12–13 enterprise-level categories covering 1,000+ processes, each with
   written definitions and key measures. Current cross-industry version: 7.4.
   - *Why not invent categories:* we would build a worse version of a standard
     that already exists, refined across industries, and our labels would mean
     nothing to a business audience that already benchmarks against PCF.
   - **⚠️ Verify the licence before embedding it in a product.** "Open standard"
     is not the same as "free to redistribute commercially". This is a blocking
     check, not a footnote. *(OQ-11.)*
2. **Select a working shortlist** for v1 rather than all 1,000+: QA/QC review,
   data entry/transfer, exception handling, reconciliation, approval routing,
   research/lookup. Which shortlist is a domain question, not a technical one.
3. **Add a local extension namespace** for distinctions PCF doesn't make that we
   care about, kept clearly separate from the standard's own labels.
4. **Write the discriminating definition for each label** — what must be true of
   a process for this label to apply. These definitions become the structural
   rules in Phase 5.2, so write them as testable statements, not prose.
5. **Always include `unknown` as a first-class label.** A stage that cannot say
   "I don't recognise this" will force every process into the nearest box, which
   is worse than silence.

**Expected output.** `config/process-taxonomy.yaml` — labels, definitions,
discriminating criteria, provenance (PCF ID or local), plus a licence note.

**Validation checkpoint**

- A domain expert reads the shortlist and its definitions and agrees they are
  mutually distinguishable — i.e. for each pair of labels, they can state what
  would tell them apart. **If two labels can't be distinguished by a human, no
  classifier will separate them**, and one of them should be removed.

---

### Phase 5.2 — Shape evidence

**Goal.** Extract structural signals from the Stage 4 model.

**Build steps**

1. **Implement structural signature rules** over the discovered process model and
   the episode statistics. Each rule is one testable statement:
   - Does the model end in an **exclusive choice between two or more terminal
     activities**? (approve/reject — the strongest QA/QC signal)
   - Is there a **comparison pattern** — reading the same identifier or value in
     two applications before a decision? (available directly from Stage 3's links)
   - **Read-heavy vs write-heavy** — ratio of inspect activities to data-entry
     activities across the group.
   - **Cross-application lookup pattern** — enter one system, search another with
     a value carried from the first, return.
   - **Rework/loop presence** — from Stage 4 Phase 4.7.
   - **Branch conditionality** — does a branch trigger on a data disagreement?
2. **Emit each rule's outcome with its support** (how many episodes, what
   confidence), never as a bare boolean. A signature that holds in 95% of
   episodes is different evidence from one holding in 55%.
3. **Do not use graph edit distance or behavioural-profile similarity yet.** Both
   are established techniques for comparing process models, but they compare
   against **reference models we do not have**. Phase 5.5's confirmation loop
   builds that library; revisit once it exists. Recording the dependency here so
   the opportunity isn't forgotten.

**Reuse call.** Build custom, over PM4Py's model objects. The rules encode
domain knowledge, which is not something a library can supply.

**Expected output.** A structural feature vector per process group, each feature
carrying its support.

**Validation checkpoint**

- On the scripted QA/QC scenario, the terminal-exclusive-choice rule and the
  comparison-pattern rule both fire with high support. **These are the two rules
  the architecture's own reasoning rests on — if they don't fire on a process
  built to be a QA review, the rule definitions are wrong.**
- On a deliberately non-QA synthetic process (pure data entry, no decision), both
  rules stay silent. A rule that fires on everything is not evidence.

---

### Phase 5.3 — Language evidence

**Goal.** Extract meaning from the words on screen — the second, independent clue.

**Build steps**

1. **Harvest the vocabulary** from Stage 1's `ui_chrome` text (button labels,
   screen titles, column headings, field labels), which Stage 1 Phase 1.8
   deliberately retains in clear precisely because it is not personal data. This
   is a payoff for a decision made four stages earlier.
2. **Match against taxonomy terminology** — each label in the taxonomy carries
   indicative terms (*approve, reject, review, verify, compliance, sign-off,
   exception, reconcile*). Score by weighted match count, with rarer terms
   weighted higher (same term-frequency principle as Stage 3).
3. **Weight by structural position.** A word on the **terminal action button**
   is far stronger evidence than the same word in a menu somewhere. "Approve" as
   the final click is nearly decisive; "approve" in a help menu is noise.
4. **Consider semantic role labelling** as an upgrade — Rebmann & van der Aa
   (CAiSE 2021) extract up to eight semantic roles per event from event-log
   language, combining a language model with attribute classification. Evaluate
   whether the richer extraction beats plain weighted matching on our data;
   adopt only if it measurably wins.
5. **Handle multilingual and in-house vocabulary explicitly.** Real systems have
   buttons in other languages and company-specific jargon. The term list must be
   editable config, and unmatched high-frequency terms should be surfaced for a
   human to map — that list is also a useful artefact in its own right.

**Reuse call.** Plain weighted lexicon matching first (transparent, no
dependencies, no training). Evaluate the published semantic-role-labelling
approach as a measured upgrade rather than adopting it on reputation.

**Expected output.** A language feature vector per group, with the matched terms
and their positions listed as evidence.

**Validation checkpoint**

- On the scripted scenario, the QA/QC terms are found with the terminal-button
  position weighting applied. The evidence list names the actual buttons.
- **Negative control:** a synthetic process with QA-ish words in incidental
  positions (a help menu) but no decision structure must **not** score as QA/QC.
  This tests that position weighting is doing real work.

---

### Phase 5.4 — Combining the evidence

**Goal.** Turn two independent clue sets into one labelled guess with a
confidence and a readable justification.

**Build steps**

1. **Treat each evidence source as a labelling function** — each structural rule
   and each language match votes for or against a label, with a strength.
2. **Combine using weak supervision** (Snorkel-style): a generative model that
   learns from **agreements and disagreements among labelling functions without
   requiring labelled data**, producing probabilistic labels. This is the right
   framework precisely because we will have almost no labelled examples early on.
   - Snorkel's own guidance notes weak supervision performs best on **structured
     text** — button labels and structural signatures are about as structured as
     text gets, which suits it.
3. **Start simpler than that if the data is thin.** With a handful of process
   groups, a transparent additive score over the same evidence may be all that's
   warranted; weak supervision earns its place once there are enough groups for
   agreement/disagreement patterns to be estimable. **Build the transparent
   scorer first and compare.**
4. **The LLM rule — read carefully.** An LLM may be used as **one additional
   labelling function**, never as the classifier:
   - **Off by default.** It must be possible to run the whole product without it.
   - It sees the activity dictionary and vocabulary, **never raw captured
     content**, and never leaves the device unless explicitly configured — Stage 1
     went to real lengths to keep content local and this stage must not quietly
     undo that.
   - Its vote is denoised alongside the others. Published evidence supports this
     shape specifically: prompting as labelling functions denoised by weak
     supervision reduced errors ~19.5% versus zero-shot on WRENCH, while zero-shot
     LLM classification is documented as unreliable and **sensitive to prompt
     wording**.
   - **Never the sole voice, and never the explanation.** The justification shown
     to a human must be the structural and language evidence, not "the model said
     so" — because a reviewer can argue with the former and not the latter.
5. **Produce a plain-language justification**, as the architecture requires:
   *"this process opens a record, checks it against criteria, and ends in an
   approve/reject decision, matching the shape of a QA/QC review"* — assembled
   from the firing evidence, not generated prose.
6. **Output `unknown` when evidence is weak or conflicting.** Enforce a floor.

**Expected output.** Per group: proposed label, confidence, the ranked evidence
that produced it, and a plain-language justification.

**Validation checkpoint**

- **Calibration:** higher-confidence labels are more often confirmed by humans.
  Same discipline as Stages 2 and 3 — an uncalibrated confidence misleads Stage 6.
- **Ablation:** shape-only and language-only arms reported separately. **If one
  clue alone performs as well as both combined, say so** — the architecture's
  two-clue design would then be unnecessary complexity, and that is a finding
  worth having.
- **LLM ablation:** report performance with and without the optional LLM
  labelling function. This number tells you honestly what the LLM is worth here,
  and whether the on-device-only configuration is viable for customers who
  forbid external calls.

---

### Phase 5.5 — Human confirmation loop

**Goal.** Implement the architecture's explicit requirement that a person
confirms or corrects the first several guesses, so trust is earned before the
label is relied on unsupervised.

**Build steps**

1. **Review screen:** proposed label, confidence, evidence list, justification,
   and the process map beside it. Actions: confirm, correct (choose another
   label), or mark unknown.
2. **Store every confirmation and correction** as ground truth. Corrections are
   worth more than confirmations — a corrected guess tells you which evidence
   misfired.
3. **Also store the confirmed model as a reference model.** This is what
   eventually unlocks the process-model-similarity techniques deliberately
   deferred in Phase 5.2. **Start storing from day one**, even though nothing uses
   them yet.
4. **Track accuracy over time** and only propose unsupervised labelling once
   confirmed accuracy on new, unseen processes clears a threshold — the
   architecture's "trust is earned" requirement made measurable.
5. **When a correction is made, show which evidence was wrong**, so rules and
   term lists can be fixed at the source rather than patched per-case.

**Expected output.** A confirmation tool; a growing labelled set; a reference
model library; an accuracy-over-time record.

**Validation checkpoint (Stage 5 exit criteria)**

| Metric | Threshold |
|---|---|
| Correct label proposed on unseen processes | ≥ 70% top-1 |
| Correct label in top 2 proposals | ≥ 90% |
| `unknown` correctly emitted on out-of-taxonomy processes | ≥ 80% |
| Confidence calibration | monotonic |
| Justification judged useful by reviewer | ≥ 80% of cases |
| Review time per process | < 2 minutes |
| Works with the LLM function disabled | yes — required, not optional |

70% top-1 is deliberately modest. **The architecture's own bar is that a human
"only needs to glance and confirm, not diagnose from scratch"** — that is a bar
about usefulness, not accuracy, and the top-2 and justification-usefulness
metrics measure it better than top-1 does.

---

## 3. Dependencies

**Needs from Stage 4:** the process model (for shape rules); the activity
dictionary; branch conditions; the cross-application map (for the lookup-pattern
rule); group quality metrics — a label proposed from a low-fitness model should
inherit that uncertainty rather than presenting as confident.

**Needs from Stage 1:** `ui_chrome` text retained in clear, with structural
position preserved (which button was terminal). **The position information is
what makes the language evidence work**, and it comes from Stage 1's element
capture.

**Needs from Stage 3:** link evidence, for the comparison-pattern and
cross-application-lookup structural rules.

**Hands off to Stage 6:** the proposed label, its confidence, its evidence list,
the plain-language justification, and the human confirmation status — so the
final document can distinguish "confirmed by a person" from "proposed by the
system and not yet reviewed". That distinction must survive into the output.

---

## 4. Open questions and risks

### OQ-11 — APQC PCF licensing *(blocking)*

Described as an open standard with publicly mirrored PDFs, but commercial
redistribution rights inside a product are **unverified**. Check before embedding.
If the licence doesn't permit it, the fallback is a local taxonomy *informed by*
PCF's structure, which is weaker but workable.

### OQ-12 — Is an LLM permitted in the product at all?

A policy decision, not a technical one. Sending screen vocabulary to an external
model conflicts with Stage 1's on-device posture and with whatever was promised
to the workforce during capture consent. A local model avoids it at a hardware
cost. **Needs an explicit answer**; the blueprint defaults to "off" so that the
absence of a decision doesn't become a decision by accident.

### OQ-13 — Which categories actually matter?

PCF has 1,000+ processes; the proposed v1 shortlist is a guess. A domain expert
should set it.

### Risk — this stage may simply not be worth much

If the discovered process map is good (Stage 4) and readable (Stage 6), the label
may add little: a reader who can see the map ending in Approve/Reject can tell
it's a review process without being told. **Stage 5's value should be tested,
not assumed** — the honest test is whether a reader finds the label useful when
the map is already in front of them. If not, this stage could be reduced to a
one-line heading and the effort moved to Stage 6.

### Risk — overfitting the taxonomy to QA/QC

The architecture is focused on QA/QC review. Rules and vocabulary tuned to that
one type will classify everything else as "not QA/QC", which is a useless
distinction dressed up as a classification. The negative controls in Phases
5.2–5.3 exist to catch this, and the taxonomy shortlist should contain several
genuinely different types from the start.

### Judgment calls a reviewer should re-examine

- **Adopting APQC PCF rather than inventing categories** — subject to licence.
- **Rules + weak supervision over an LLM classifier** — chosen for
  explainability, correctability and on-device operation, **not** because it is
  more accurate. Phase 5.4's LLM ablation measures exactly what that choice costs.
- **Deferring process-model similarity** until a reference library exists — sound,
  but it means the better method stays unavailable for a while.
- **70% top-1 as the bar** — deliberately modest, because the architecture's
  requirement is "glance and confirm", not autonomous accuracy.
