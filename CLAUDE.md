# CLAUDE.md — Working instructions for this repo

## What this repo is

This repo holds the research and architecture for **Pulse**: a process
discovery tool that mines real workflows (e.g. QA/QC review processes)
across multiple applications by capturing structured application signals —
the accessibility layer, the DOM — in preference to pixels, falling back to
computer vision only where those signals do not exist.

**Deployment context (decided — do not re-litigate):** Pulse is being built
for deployment **inside Wells Fargo's own environment**. It is an internal
tool, not a product sold to third parties. Consequences that shape every
design decision:

- The cross-organisational-boundary problem does not apply — data never
  leaves the bank. But the **controls** external vendors must satisfy still
  define the bar we hold ourselves to internally (see "Data controls").
- The audience is large and multi-datacenter. Design for that shape from the
  start; do not design a single-machine script and plan to scale it later.
- InfoSec, data governance and works-council/employee-consent considerations
  are real approval paths, not hypotheticals. Where a decision belongs to
  those functions, say so and stop — do not decide it in a plan.

The goal of this repo is **research and architecture validation**, done
rigorously enough that the ideas survive a skeptical technical reviewer and
an internal security review.

---

## How to approach every task here

1. **Read `plans/pulse-architecture.md` first**, every session, before doing
   anything else. It is the source of truth for the current design. Then read
   `plans/platform-architecture.md` (cross-cutting concerns) and
   `plans/BUILD-STATUS.md` (what is decided, what is open).

2. **Treat every claim as needing evidence.** If you assert something works,
   point to where — a test you ran, a source you found, a benchmark you
   checked. Distinguish explicitly between **verified** (you read the source
   or ran the test), **recalled** (stated from memory, unconfirmed), and
   **not checked**. Never present recalled information as verified.

3. **No assumptions, anywhere.** If something is unknown, the correct output
   is "this is unknown and here is how we would find out" — not a plausible
   guess presented smoothly. This applies to library versions, benchmark
   results, patent claims, and internal Wells Fargo policy alike.

4. **Take the best available approach, then differentiate substantively.**
   The standard is: *what is the most accurate, most reliable approach that
   exists in the world?* Use it. Do not reinvent solved science, and do not
   avoid a strong existing method merely because someone else got there
   first. Where we differentiate, the difference must be **substantive** —
   it must change what the system can actually do — not cosmetic.

   Understand the three distinct situations, because they have different
   consequences and are routinely confused:

   | Situation | Can we use it? | Can we patent our version? |
   |---|---|---|
   | Published paper / open-source (MIT, BSD, Apache) | **Yes**, per licence | Only if our contribution is itself novel |
   | Granted patent | **Freedom-to-operate question** — a small or cosmetic change does **not** avoid infringement; patent law covers equivalents | No |
   | Commercial product, patent status unknown | Probably — but check | Depends on their filings |

   Prior art existing blocks *us patenting*; it does not automatically block
   *us building*. Keep those two questions separate, and never suggest that a
   trivial modification clears a granted patent — it does not. Route genuine
   freedom-to-operate questions to Wells Fargo's internal IP/legal function
   rather than resolving them in a plan.

5. **Be suspicious of "just apply AI to X."** Before proposing any mechanism,
   check: is the novel part an actual technical mechanism (a specific
   algorithm, data structure, capture method, or sequencing), or is it "use
   an LLM to do an existing process"? If it's the latter, say so plainly.
   LLMs and agent frameworks are permitted tools where they are genuinely the
   best option — but they must be **subordinate, auditable, and optional**,
   never the sole source of a claim the system presents as fact.

6. **Check for prior art before getting excited about an idea.** Search
   patents (Google Patents / USPTO), published research, and named competing
   tools (SKAN, UiPath, Celonis, Automation Anywhere, Paxray, KYP.ai). Log
   findings in `/research/` — "found nothing relevant" is useful evidence,
   provided you list the searches you actually ran.

7. **Argue both sides before concluding.** For any significant design
   decision, write the strongest case *for* and *against* — genuinely — before
   recommending. Don't skip the "against" case because a direction is already
   chosen.

8. **Log everything in `/research/`**, using `/research/TEMPLATE.md`. A future
   session must be able to understand what was tried, what worked, what
   didn't, and why, without re-deriving it.

9. **Maintain the three-artifact rule.** Every stage has a blueprint in
   `plans/`, a research log in `research/`, and a plain-English walkthrough in
   `manual-readable/`. Keep them in sync; a change to one usually needs the
   other two updated.

---

## The four differentiators (decided)

Everything we build should strengthen at least one of these. They are treated
as one integrated capability, not four features:

1. **Sensing-tier arbitration** — choose the cheapest sufficient sensor per
   application surface (accessibility → DOM → computer vision), record which
   sensor produced every value, and grade the value by that sensor's
   reliability.
2. **Field-pair relationship graph** — exact values plus semantic field
   identity let us learn real cross-application pathways across many cases,
   and use population-level evidence to validate individually weak
   observations.
3. **Evidence-graded output** — every claim carries its support and evidence
   tier, plus an explicit "what we don't know" section. Auditable by design.
4. **Capture-health self-awareness** — the system detects and reports when its
   own sensing degrades, instead of silently producing worse output.

**Never silently merge values of different provenance.** A computer-vision
guess and an exact accessibility read must stay distinguishable end to end.
Where both sensors observe the same value, agreement raises confidence and
disagreement is **flagged, not averaged away**.

---

## Data controls (decided — apply in every stage)

1. **Sensitive identifiers** (loan IDs, ECNs, account numbers) are **never**
   stored or transmitted in cleartext anywhere in the pipeline. Apply
   **keyed HMAC hashing at the point of capture**, key held in the existing
   internal Vault. Cross-application matching works on hash equality, so no
   capability is lost.
2. **Structural and procedural metadata** (field names, button labels, screen
   titles, timestamps) is **not sensitive and stays readable**. Do not
   over-hash — the mining and labelling stages need to read this.
3. **Reversal path**: a separate, narrowly-scoped, fully audited
   tokenization-vault (same shape as PCI card tokenization) for the rare case
   a human reviewer must see a real value. **Never exposed in the main
   pipeline.**
4. **Data classification and storage location** follow Wells Fargo's internal
   data governance policy — the same approval path used for the db_discovery
   project's encrypted connection strings. This is a **policy lookup with
   InfoSec/data governance, not a technical decision to make unilaterally.**
5. **Audit everything**: every access to sensitive data or to the reversal
   path is logged and reviewable, matching the audit expectations imposed on
   external vendors.
6. **Federated local mining**: even hashed data is not pooled company-wide by
   default. Mine locally per business unit / datacenter; share only
   **pattern-level summaries** centrally.
7. **No individual performance surveillance.** Aggregate by default.
   Per-person views only on an explicit, logged request. This system exists to
   discover processes, not to score employees — and breaching that would also
   destroy the workforce consent the capture layer depends on.

---

## Environment-agnostic architecture (decided)

Build once; move environments by configuration, never by rewrite.

- **Storage, secrets, and sensing sit behind abstract interfaces.** Local
  database and local secrets file during personal development; Wells Fargo's
  internal database and Vault later — **config change only, no logic change**.
- **Containerised from the start** (Docker Compose locally) so the shape
  matches the clustered, multi-datacenter target rather than needing a rewrite
  to get there.
- **A single environment config file** declares where storage, secrets and
  sensing point. Moving environments is an edit to that one file.
- **Accessibility/DOM sensing is portable and testable now.** The computer
  vision fallback for Citrix/mainframe/VDI **cannot be validated until inside
  the Wells Fargo environment** — it must be flagged honestly as untested,
  never demoed as proven.

---

## When you disagree with an approach

If you conclude the current plan or a specific approach is wrong, weak, or
worse than an alternative:

1. **State the disagreement explicitly in writing**, with evidence — in the
   relevant blueprint, in `/research/`, and in `BUILD-STATUS.md`.
2. **Propose your best alternative**, with reasoning.
3. **Then keep working.** Do not halt the whole task waiting for a reply.
   Proceed with the best-evidenced option, clearly labelled as your judgment
   call, so the work keeps moving and the decision stays visible and
   reversible.

**Stop and wait only for decisions that are genuinely not yours:** anything
requiring Wells Fargo policy (InfoSec, data governance, legal/IP,
works council or employee consent), anything requiring domain knowledge only
a business expert has, and anything that would be expensive or hard to undo.

Being confident is not a substitute for being right. Do the research, strip
the problem down several ways, compare them, and pick the best — then say
plainly why you picked it and what would change your mind.

---

## Scope boundaries

- This repo is about **process discovery and research validation**. It ends at
  producing a clear, trustworthy description of a real process. Building the
  downstream agents/ingestion pipeline that consumes Pulse's output is out of
  scope unless explicitly asked.
- **Don't fabricate** benchmark numbers, prior-art results, citations, or
  internal Wells Fargo policy details. If something wasn't checked, say it
  wasn't checked.
- **No dates in file contents or filenames.** Git records history.
