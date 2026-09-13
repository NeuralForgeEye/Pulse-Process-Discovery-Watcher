# Research Log — SKAN's actual approach, and the decisions it forced

**Stage / Phase:** Cross-cutting — sensing strategy, deployment, data controls
**Author:** Claude Code session (Opus 5), with decisions taken by the project owner
**Status:** concluded. **This log supersedes several earlier assumptions.**
See §9 for what changed.

---

## 1. Question being investigated

Three questions, one of which was asked directly by the project owner:

1. **How does SKAN actually work?** The architecture positions Pulse against
   SKAN, but nothing in this repo had verified SKAN's real architecture.
2. Given that answer, what sensing strategy should Pulse commit to at scale?
3. Where does processing happen, and under what data controls?

---

## 2. What was actually checked

**Verified (read the source):**

- **SKAN's own product and engineering descriptions**
  ([skan.ai/platform](https://www.skan.ai/platform),
  [Skan Intelligence blog](https://www.skan.ai/blogs/skan-intelligence-see-how-work-actually-gets-done-skan-ai),
  [privacy-first process intelligence](https://www.skan.ai/blogs/privacy-first-process-intelligence-regulated-industries),
  [implementation guide](https://www.skan.ai/blogs/privacy-first-ai-process-observation-implementation)):
  - **Sensing:** "a lightweight desktop agent (the Virtual Assistant) that
    observes work at the screen level, using computer vision and NLP to
    recognize applications, screens, tasks, and data across every tool in the
    enterprise stack."
  - **Coverage — the critical finding:** this explicitly includes "legacy
    systems, mainframes, **Citrix and VDI environments**, desktop
    applications, web-based SaaS, and even tools with **no API or event log**."
  - **Three-layer architecture:** Observation Layer (lightweight sensor,
    continuous, no integrations) → Intelligence Layer ("billions of events"
    into process maps, activity classifications, execution metrics, variant
    analysis) → Agent Execution Layer (observations become training data for
    agents; "Large Action Models" learning decision logic from real cases),
    over a shared "Context Graph of Work".
  - **Privacy architecture — the second critical finding:** the desktop agent
    "captures screen-level activity locally"; **"a gateway server inside the
    customer network applies anonymization, pseudonymization, and redaction
    rules before transmitting only abstracted process metadata"** to SKAN's
    cloud. "Raw screenshots and sensitive data never leave the customer
    environment." They claim this "has cleared security reviews at major banks
    and received works council approval in regulated European markets", and
    cite ISO 27001, SOC 2, PCI DSS, HIPAA, GDPR, CCPA compliance.

**Recalled, not verified:**

- Whether SKAN performs CV inference on the endpoint or at the gateway. The
  wording ("captures screen-level activity locally", gateway "applies
  anonymization... before transmitting") is ambiguous on where the heavy
  inference runs. **Materially affects endpoint cost comparisons** — do not
  assert either way.
- SKAN's endpoint resource footprint. No figures found.

**Not checked:**

- SKAN's patent portfolio. The Justia assignee page returned **HTTP 403** in
  an earlier session and has not been retried by another route. Still the
  largest single prior-art gap in this repo.
- Independent verification of the bank security-review and works-council
  claims. These are vendor marketing statements, not audited assertions.

---

## 3. Prior art / existing solutions — corrected picture

| What | Who | Relevance | Correction to earlier logs |
|---|---|---|---|
| CV sensing covering **Citrix, VDI, mainframe, no-API tools** | SKAN | The coverage bar we must meet | Earlier logs treated Citrix as "a risk for us"; it is more accurately **a capability the main competitor already has** |
| **On-prem gateway** doing anonymisation/pseudonymisation/redaction before anything leaves | SKAN | The privacy bar | Earlier logs assumed "no video" was a meaningful privacy differentiator. **It largely is not** — their video never leaves the customer's network either |
| Metadata-only, no content | Paxray, KYP.ai | Coverage floor | Unchanged |

---

## 4. Options considered

**Sensing:** metadata-only · hybrid metadata-first with CV fallback ·
CV-first with metadata enrichment.

**Deployment:** fully local per endpoint · on-prem gateway tier · direct to
cloud · federated per business unit.

**Identifier handling:** raw retention · keyed HMAC at capture · HMAC plus a
separate audited reversal vault.

---

## 5. Debate — for and against

### 5.1 Sensing: metadata-only vs hybrid

**Metadata-only — for.** Cheapest, simplest, most accurate where it works,
strongest privacy story, fully portable and testable outside the bank today.

**Metadata-only — against.** SKAN explicitly covers Citrix, VDI and mainframes.
In regulated finance a material share of QA/QC work runs on exactly those
surfaces. A tool that cannot see them is not a competitor at scale; it is a
tool for the subset of work that happens in modern applications. Committing to
purity here means accepting a coverage ceiling set by someone else's
architecture.

**Hybrid — for.** Coverage matches SKAN while preserving the accuracy advantage
where it matters. Exact accessibility reads where available; CV only where
nothing else exists. The sensor choice becomes a *property of each captured
value* rather than a property of the product.

**Hybrid — against.** Two sensing stacks to build, test and maintain. CV brings
back the compute cost and the privacy surface that metadata-only avoided. And
the CV path **cannot be validated outside the Wells Fargo environment**, so a
substantial component stays untested until late.

**Decision (project owner): hybrid, metadata-first, with mandatory reliability
tagging and cross-validation.** Every captured value carries the sensor that
produced it and that sensor's confidence. **Values of different provenance are
never silently merged.** Where both sensors observe the same identifier,
agreement reinforces confidence and **disagreement is flagged, not averaged**.

**Why the tagging matters more than it sounds:** without it, CV's weaker
performance on legacy surfaces would be hidden inside an averaged accuracy
number, and every downstream stage would inherit an unfalsifiable claim. With
it, accuracy can be stated honestly per surface — which is the difference
between a measurement and a marketing figure.

### 5.2 Deployment: gateway vs federated

SKAN needs a gateway because they are an external vendor — data must be
sanitised before crossing the bank's boundary. **Pulse has no boundary to
cross**, so we inherit the controls without inheriting the architecture.

**Decision (project owner): federation is the default posture** — keep data
local per business unit / datacenter; share only **pattern-level summaries**
centrally. Even hashed data is not pooled company-wide by default. **Stage 4's
mining corpus is a deliberate, flagged exception** — see §8.1.

**A genuinely convenient fit worth recording:** Stage 3's field-pair
relationship graph needs *population* evidence — how often
`(from_path_hash → to_path_hash)` is proven across many cases. That is
**already a pattern-level summary containing no content**: a pair of one-way
hashes and a count. So the mechanism that gives Pulse its distinctive
capability is also the one that federates cleanly. This was not designed for
federation; it happens to suit it, and that is worth noticing rather than
assuming it will hold everywhere.

**Where federation genuinely costs us — and the decision taken.** Stage 4
process mining assumes one corpus. Mining locally and merging *models* across
business units is materially harder than mining a pooled log, and no blueprint
solves it.

**Decision (project owner): Stage 4 proceeds against a single pooled corpus of
HMAC-hashed identifiers, as a working assumption pending governance.** The
federation principle continues to govern everything else. See §8.1 for the
governance flag and the three cheap constraints that bound the risk.

### 5.3 Identifier handling: HMAC at capture

This **resolves OQ-1**, previously the repo's most significant open question.

**Decision (project owner): keyed HMAC at the point of capture**, key from the
internal Vault, with a separate narrowly-scoped audited reversal vault for
human review, and structural metadata (field names, button labels, screen
titles) left readable.

**Why this is better than the dual-write design I had proposed:** my Stage 1
Phase 1.8 design deferred the decision by writing both a hash and an encrypted
raw value, with a config flag. That kept a cleartext path alive in the main
pipeline — meaning the *pipeline* had to be trusted, not just the vault.
Hashing at the point of capture means cleartext identifiers **never enter the
pipeline at all**, so the security argument is structural rather than
procedural. The reversal vault still exists, but it is off the main path and
audited, which is the standard tokenization pattern.

**What it costs, stated honestly:** substring and fuzzy matching across
identifier variants is lost — `LN-48213` and a bare `48213` hash differently.
Mitigation is normalisation *before* hashing plus token-level hashing of
components, which recovers the common cases but not all of them. Stage 2 Phase
2.3 and Stage 3 Phase 3.2 must be updated to work purely on hash equality.

---

## 6. Novelty check (required)

Re-assessed against the corrected competitive picture.

**What is *not* differentiating:** metadata-only capture (Paxray, KYP.ai);
CV-based observation (SKAN, FortressIQ); clipboard source→destination tracking
(endpoint DLP patents); on-prem redaction before analysis (SKAN's gateway);
automated process documentation (UiPath PDD); every algorithm in Stage 4.

**What appears to remain**, as one integrated capability rather than four
features:

> **Adaptive per-surface sensing with provenance-graded values**, feeding a
> **population-validated cross-application relationship graph**, producing
> **evidence-graded auditable output**, over a substrate that **monitors and
> reports its own sensing degradation**.

The specific mechanism that no single-mode competitor can replicate: a CV-only
system cannot produce exact field-level identity, so it cannot build reliable
field-pair relationships; a metadata-only system cannot see the legacy
surfaces, so its population evidence has holes it cannot detect. **The
combination is what produces both coverage and exactness, with an explicit
record of which one applied where.**

**Honest qualifications, unchanged in force:**
- This is still a **combination claim**, the weakest kind.
- **No patent claim text has been read** for any competitor.
- SKAN's portfolio remains **unexamined** (403).
- Being internal to Wells Fargo changes the commercial exposure but **does not
  create an exemption** — internal use of a patented invention is still
  infringement under US law. Route to internal IP counsel; do not resolve here.

**"Just apply an LLM"? No.** Sensor arbitration, hash-equality linking,
population corroboration and conformance checking are all deterministic,
inspectable mechanisms. LLM use remains subordinate and optional (Stage 5),
off by default.

---

## 7. Conclusion

Adopt hybrid metadata-first sensing with mandatory provenance tagging; deploy
federated inside the bank with pattern-level sharing only; hash identifiers at
capture with an audited reversal vault; build every component behind
environment-agnostic interfaces so the move from a development machine to the
bank's infrastructure is a configuration change.

**What would change this:** if real coverage measurement shows the
accessibility layer reaches well over 90% of target work, the CV tier becomes
a low-priority option rather than a core component, and the project gets
simpler and cheaper. **Measure before building the CV tier.**

---

## 8. Open items requiring a human decision

1. **Federated Stage 4 mining — DECIDED as a working assumption, still open
   with governance.** Stage 4 will be built against a **single pooled corpus of
   HMAC-hashed identifiers**.

   > **OPEN GOVERNANCE ITEM: Stage 4 currently assumes pooling of HMAC-hashed
   > identifiers across business units is permitted. This has not been confirmed
   > by data governance/InfoSec. If later found not permitted, fall back to the
   > federated local-mine-then-merge-models approach (candidate designs already
   > drafted under PA-1) instead of pooled mining. Do not treat pooled mining as
   > final/approved architecture until confirmed.**

   **The federated candidate designs are retained**, not superseded — see
   `plans/platform-architecture.md` §5.5. They are the fallback.

   **Reasoning for proceeding on the assumption:** the governance answer is a
   conversation, not a research project, and blocking Stage 4 on it would stall
   the most algorithmically mature part of the system for a question that can be
   answered in parallel. The risk is bounded by three cheap constraints
   (§5.4) — a `CorpusProvider` port, a globally shared activity dictionary, and
   a preference for aggregatable statistics — which together make a later
   refusal a boundary change rather than a rewrite.

   **The one constraint that genuinely matters** is the shared activity
   dictionary. Every federated candidate requires that two business units call
   the same real-world step by the same name; dictionaries derived independently
   per unit cannot be reconciled afterwards. It costs almost nothing to do now
   and cannot be retrofitted cheaply, which is precisely the profile of a
   constraint worth adopting before it is needed.
2. **Data classification and storage location** — policy lookup with InfoSec /
   data governance, via the db_discovery approval path. Not a technical
   decision.
3. **Works council / employee consent posture.** Content-bearing capture of
   employee activity inside a bank engages this regardless of internal
   deployment. SKAN treats works-council approval as a selling point, which
   indicates it is a real gate.
4. **SKAN patent portfolio still unexamined.** Retry by a route other than
   Justia.
5. **Where CV inference runs** (endpoint vs gateway) in our own design —
   affects endpoint footprint, which is the main practical objection an
   enterprise desktop team will raise.

---

## 9. What this log supersedes

| Earlier position | Now |
|---|---|
| S1 OQ-1: raw values vs hashes, deferred via dual-write | **Resolved** — HMAC at capture + audited reversal vault |
| S1 OQ-3: Citrix blind spot may kill the premise | **Resolved** — hybrid sensing with CV fallback; CV tier untestable until inside the bank |
| S1 §4.2: "no video" as privacy differentiator | **Weakened** — SKAN's raw capture never leaves the customer network either |
| Deployment assumed single-machine | **Replaced** — federated per business unit, environment-agnostic interfaces, containerised |
| Differentiator undecided | **Decided** — all four, as one integrated capability |
| Stage 4 federated mining unsolved, blocking | **Unblocked** — pooled hashed corpus as a working assumption, federated designs retained as fallback, governance flag raised (§8.1) |
