# CLAUDE.md — Working instructions for this repo

## What this repo is

This repo holds the research and architecture for **Pulse**: a metadata-based
process discovery tool that mines real workflows (e.g. QA/QC review
processes) across multiple applications, without relying on OCR or screen
recording, by capturing structured application signals instead. It also
tracks related early-stage patent research (see `/plans/`).

The goal of this repo is not just "write code" — it's **research and
architecture validation**, done rigorously enough that the ideas here could
survive a real prior-art check and a skeptical technical reviewer.

## How to approach every task here

1. **Read `/plans/pulse-architecture.md` first**, every session, before doing
   anything else. It is the source of truth for the current design. Don't
   propose something that contradicts it without flagging the contradiction
   explicitly (see "When you disagree" below).

2. **Treat every claim as needing evidence.** If you assert something works,
   point to where — a test you ran, a source you found, a benchmark you
   checked. Don't state confidence you haven't earned.

3. **Be suspicious of "just apply AI to X."** A recurring failure mode in
   this research is proposing an idea that's really just "use an LLM to do
   an existing process" — that fails patentability (the legal obviousness
   bar) even when it's good engineering. Before proposing any new mechanism,
   explicitly check: is the novel part the actual technical mechanism (a
   specific algorithm, data structure, capture method, or sequencing), or is
   it just "apply AI/LLM to Y"? If it's the latter, say so plainly instead
   of dressing it up.

4. **Check for prior art before getting excited about an idea.** Search for
   existing patents (Google Patents / USPTO), published research, and named
   competing tools/products (SKAN, UiPath, Celonis, Automation Anywhere,
   etc.) covering the same mechanism. Log what you find in `/research/` —
   even a "found nothing relevant" result is useful evidence, not wasted
   effort.

5. **Argue both sides before concluding.** For any significant design
   decision, write out the strongest case *for* the approach and the
   strongest case *against* it — genuinely, not as a token gesture — before
   landing on a recommendation. Don't skip the "against" case just because
   you've already committed to a direction.

6. **Log everything in `/research/`**, using the template in
   `/research/TEMPLATE.md`, so nothing gets lost between sessions. A future
   session (or a human) should be able to read the research log and
   understand what's been tried, what worked, what didn't, and why —
   without re-deriving it from scratch.

## When you disagree with an approach

If, during research or implementation, you conclude that the current plan or
a specific approach is wrong, weak, or worse than an alternative:

1. **Stop and flag it explicitly** — state clearly what you disagree with
   and why, with evidence.
2. **Propose your best alternative** — don't just critique, present the
   specific alternative you think is strongest, with your reasoning.
3. **Wait for input before proceeding** — do not silently switch approaches
   or keep building on your own alternative without confirmation. Present
   the disagreement and the alternative, then pause for a decision.

This applies even if you're confident — confidence is not a substitute for
confirmation on a direction change.

## Scope boundaries

- This repo is about **process discovery and research validation**, not
  about building the downstream agents/ingestion pipeline that would
  eventually consume Pulse's output. Don't scope-creep into that unless
  explicitly asked.
- Don't fabricate benchmark numbers, prior-art search results, or citations.
  If something wasn't actually checked, say it wasn't checked.
