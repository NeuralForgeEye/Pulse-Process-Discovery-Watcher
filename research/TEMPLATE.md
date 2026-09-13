# Research Log — <short title>

**Sequence:** <NNN, or just rely on git history>
**Stage / Phase:** <e.g. Stage 1 — capture layer>
**Author:** <human or Claude session>
**Status:** open | concluded | superseded by <file>

---

## 1. Question being investigated

One or two sentences. What decision does this research unblock? If it
unblocks nothing, it probably shouldn't be logged as research.

## 2. What was actually checked

List every source actually consulted, with URLs. Distinguish clearly:

- **Verified** — read the source / ran the test.
- **Recalled, not verified** — stated from model memory, still unconfirmed.
- **Not checked** — named here so a later session knows the gap exists.

Never present recalled information as verified.

## 3. Prior art / existing solutions found

| What | Who | Type (patent / product / paper / OSS) | Relevance | Source |
|---|---|---|---|---|

For each: does it cover the same *mechanism*, or just the same *goal*?
Covering the same goal by a different mechanism is a competitor, not
blocking prior art. State which it is.

If nothing relevant was found, say so explicitly and list the searches
run — a negative result is evidence and must be recorded as such.

## 4. Options considered

For each real option: what it is, what it costs, what it buys.

## 5. Debate — for and against

For the non-obvious choice(s), write the genuine strongest case each way.
Do not soften the "against" case because a direction has already been picked.

**Option A — case for:**
**Option A — case against:**
**Option B — case for:**
**Option B — case against:**

## 6. Novelty check (required)

Answer plainly:

- Is the novel part a specific technical mechanism (algorithm, data
  structure, capture method, sequencing)? Name it.
- Or is it "apply an LLM/AI to an existing process"? If so, say that
  plainly and do not dress it up.
- What is the closest prior art, and what is the concrete difference?

## 7. Conclusion / recommendation

The call, and the reasoning in one paragraph. Include what would change
this call (the falsifier).

## 8. Open items requiring a human decision

Anything where CLAUDE.md's "when you disagree" rule applies: a conflict
with the current architecture, or a trade-off that isn't Claude's to make.
