# Stage 2 — Cut the day into cases

*Plain-English walkthrough. Technical version: `../plans/stage-2-blueprint.md`.
Evidence: `../research/stage-2-episode-segmentation.md`.*

---

## What this stage does

Stage 1 gives us one long ribbon of events — Sam's entire day, 6,000 entries,
one after another, with no idea where anything begins or ends.

Stage 2 cuts that ribbon into **episodes**: "these 47 events, from 9:02 to 9:08,
were Sam handling loan LN-48213 from start to finish."

That's it. That's the whole stage. It sounds simple and it isn't, for one
reason: **nobody presses a "start case" button.** Sam just works.

---

## Why this is the hard middle bit

Here's the actual ribbon, roughly:

```
 9:01  opened Outlook, read an email
 9:02  opened LoanDesk                      ┐
 9:02  loan LN-48213 appeared on screen     │
 9:03  highlighted LN-48213, copied         │  ← one case?
 9:03  switched to Chrome, pasted, searched │     where does it
 9:05  read income $84,000                  │     start and end?
 9:06  switched to Excel                    │
 9:07  back to LoanDesk, clicked Reject     ┘
 9:08  phone rang, 4 minutes of nothing
 9:12  opened LoanDesk, loan LN-48214…         ← next case starts here?
```

A human reading that gets it instantly. The problem is doing it automatically,
6,000 events a day, across 12 people, when:

- People **get interrupted** (that phone call — is it a case boundary, or a pause?)
- People **multitask** — Sam might have two loans open at once, flipping between
  them. A naive cutter either merges them into one wrong blob or shatters them
  into fragments.
- People **abandon** cases halfway and come back after lunch.
- Some work happens in **apps we can't see into** (Stage 1's "blind" gaps).

And you can't just say "cut after 30 minutes of inactivity" — more on why that
number is nonsense below.

---

## The picture

```
  STAGE 1's ribbon:  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
  ┌───────────┐            ┌───────────────┐          ┌──────────────┐
  │ SIGNAL 1  │            │   SIGNAL 2    │          │  SIGNAL 3    │
  │ The case  │            │ Pauses &      │          │ Behaviour    │
  │ ID on     │            │ finishing     │          │ shifts       │
  │ screen    │            │ actions       │          │ (fallback)   │
  │           │            │               │          │              │
  │"LN-48213  │            │"4 min pause"  │          │"suddenly a   │
  │ was on    │            │"clicked       │          │ totally      │
  │ screen    │            │ Reject"       │          │ different    │
  │ 9:02-9:07"│            │               │          │ set of       │
  │           │            │               │          │ screens"     │
  │ STRONGEST │            │  SUPPORTING   │          │  WEAKEST     │
  └─────┬─────┘            └───────┬───────┘          └──────┬───────┘
        └──────────────────────────┼─────────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  DECIDE, AND SAY HOW SURE    │
                    │  you are + why               │
                    └──────────────┬───────────────┘
                                   ▼
     EPISODES:  [══ LN-48213 ══] ⋯ [══ LN-48214 ══] ⋯ [leftovers]
                  high confidence      high conf.       "residue"
```

---

## The key idea: use the ID, don't guess from behaviour

Everyone else in this research field cuts the ribbon by **watching behaviour** —
"the rhythm changed here, so probably a new case started." They do that because
their capture tools only record *what type of action* happened, not *what was on
screen*.

**We have something they don't: the actual loan ID, captured from the screen.**

So we don't have to guess. If `LN-48213` was visible from 9:02 to 9:07, that's
not a statistical inference — it's an observation. The episode is that span.

This has a second benefit that matters more than it first appears: **it handles
multitasking for free.** If Sam has two loans open, we get two overlapping spans,
which is *what actually happened*. A behaviour-based cutter can only produce one
sequence of non-overlapping chunks, so multitasking is a failure mode for it and
an ordinary Tuesday for us.

**The catch, stated honestly:** this assumes a case ID exists, is on screen, and
Stage 1 caught it. Sometimes it won't be. That's why there's a fallback, and why
one of the first things we measure is *what fraction of real work actually has a
visible ID.* If that number comes back low, the plan needs rethinking — and
because Stage 3 links on the same IDs, that one measurement tells us something
important about the whole project. **We take it early on purpose.**

---

## A thing worth knowing: the 30-minute rule is made up

Every web analytics tool on earth ends a "session" after 30 minutes of
inactivity. It's such a standard that it feels like physics.

It isn't. The trail leads back to a **1995 paper by Catledge & Pitkow**, who
measured the average time between clicks on their web server — 9.3 minutes —
added 1.5 standard deviations to get 25.5, and later work rounded it to 30.

That number describes people browsing the web over dial-up in 1995. It has
nothing to do with how long a loan reviewer pauses to think. So we don't hardcode
it — **we learn the threshold from the person's own actual pause patterns**, and
we record which value we used so the answer stays explainable.

---

## The eight phases

### Phase 2.1 — Build the ruler before measuring

**What we're building:** a hand-labelled set of sessions where we *know* the
right answer, so we can score everything afterwards.

**Why first:** without this, every later phase ends in "looks about right," which
is how you ship a segmenter that's 60% accurate and don't find out until Stage 4
produces a nonsense map.

Three kinds of test data:
1. **Scripted** — the 30-minute rehearsal from Stage 1, where we know the case
   boundaries because we wrote the script.
2. **Deliberately nasty** — two interleaved cases, a case abandoned halfway, a
   case spanning lunch, two cases sharing one ID.
3. **Real, labelled by a person** — expensive, so only a little. Held back and
   never used for tuning.

**How you test it:** get **two people to label the same real session
independently.** If they don't agree with each other at least 80% of the time,
that's a genuine discovery — it means "where does a case start" is ambiguous even
for humans, and no algorithm can be held to a higher standard. We'd write that
up rather than bury it.

---

### Phase 2.2 — Work out the signals

**What we're building:** the derived measurements every cutter needs — how long
the pauses are, how fast Sam switches apps, how much the *kind* of screen changes,
and which on-screen words mean "this case is finished."

**The finishing-word list.** Stage 1 keeps button labels and screen titles in
plain text (they're not personal data). So we can build a list: *Approve, Reject,
Submit, Complete, Sign Off, Send, Finish.* We seed it by hand, then grow it by
noticing which labels repeatedly come just before a long pause or a new ID.
It lives in an editable file so a domain expert can fix it in one line.

**The one rule that must not be broken:** Stage 1 distinguishes "Sam was away"
(`idle`) from "Sam was working in something we can't read" (`blind`). **A blind
gap must never be treated as a case boundary.** Confusing these would make the
system declare a new case every time Sam uses an unreadable app — a wrong answer
that looks completely convincing. This is the single most damaging mistake
available in this stage.

**How you test it:** on the scripted session, the learned pause threshold must
land between the longest within-case pause and the shortest between-case pause.
If no such number exists, that's a real result — it means pauses alone can't
separate these cases, which is exactly why we anchor on IDs instead.

---

### Phase 2.3 — Find the case IDs *(the riskiest phase)*

**What we're building:** the thing that works out which of the thousands of
captured values are actually *case identifiers*, and which are just... values.

**How we tell.** A case ID looks like this, statistically:
- Lots of different values across the corpus, but one value per case
- Consistent format (`LN-` then five digits)
- **Appears in more than one application** — the strongest clue, and the one that
  matters most for Stage 3
- Isn't a date, an amount, a status word, or a person's name

We keep this as **plain scored rules, not a machine-learning classifier**,
specifically so that when a domain expert says *"no, that's the branch code,
that's not the case key"*, fixing it is a one-line config change rather than a
retraining exercise.

**Two traps we handle explicitly:**

- **The same ID written five ways.** `LN-48213`, `ln 48213`, `LN48213`. We
  standardise before matching, so all five count as the same case.
- **The sticky ID.** If some ID sits in a dashboard header all day, it would
  swallow the whole day into one giant "episode". We detect any value that's
  present for more than ~40% of the session and strike it off the anchor list.

**How you test it:**
1. On the scripted data, does it find the real loan ID? (Must catch at least 90%.)
2. Plant a sticky value. Is it correctly demoted?
3. Write one ID five different ways. Do all five collapse to one?
4. **The big number:** what fraction of real activity has *any* usable ID?
   **Below about 60% and we stop and rethink** rather than pushing on.

---

### Phase 2.4 — The deliberately dumb version

**What we're building:** the simplest possible cutter — cut on a long pause, cut
after a finishing word. About 100 lines of code.

**Why bother building something we think is worse?** Because it's the **control**.
If the clever ID-based approach can't beat "cut on long pauses," then the honest
conclusion is that long pauses were enough, and we should say so and save the
complexity. Without a control you can never answer *"how much did the clever part
actually buy you?"* — and that's the first question any serious reviewer asks.

We record its score and **we don't fiddle with it afterwards** to make the clever
version look better.

---

### Phase 2.5 — The main event: cut on the IDs

**What we're building:** episodes built from where each case ID was visible.

**The refinement that matters.** Sam opens LoanDesk, navigates for 15 seconds,
*then* the loan ID appears. Those 15 seconds are part of the case — so we extend
the start backwards to the last natural boundary (app opening, or the end of a
pause). But we **mark that extension as inferred**, separately from the part we
actually observed. Later stages can then tell the difference between *what we
saw* and *what we reasonably added.* That distinction is cheap to keep and
impossible to recover later.

**How you test it:**
1. **It must beat the dumb version** from 2.4. If it doesn't, we report that the
   thesis was wrong. That's the deal.
2. **The multitasking test:** on a session with two deliberately interleaved
   cases, both must come out as two clean separate episodes. This is the specific
   thing behaviour-based cutters can't do, and the main reason for this design.
3. **The run-up test:** the extended start should land within 15 seconds of the
   true start, at least 80% of the time.

---

### Phase 2.6 — The fallback, for stretches with no ID

**What we're building:** something to handle the parts of the day where no ID is
visible, so they aren't simply thrown away.

**What we use:** an algorithm called **PELT** ("Pruned Exact Linear Time") from a
Python library called **`ruptures`**. It takes a numeric signal over time — here,
things like "app switches per minute" and "how much the screens changed" — and
finds the points where the pattern genuinely shifts.

*Why PELT and not the alternatives:* it's **exact** rather than greedy (it finds
the genuinely best set of cut points, not a good-enough one), it's fast, and it
has one tunable knob instead of several.

**We also test ourselves against the state of the art.** There's a published
method from Mannheim (Rebmann & van der Aa, CAiSE 2023) that does this with
streaming clustering, and their code is public. We run it as a **comparison arm**.
If it beats ours, we say so and reconsider. Either way we end up with an honest
comparison against published work rather than a claim.

**A test that matters more than the score:** we sweep PELT's one tuning knob and
plot accuracy against it. If accuracy swings wildly with a knob nobody can set
correctly in advance, **the method isn't deployable** — and we report that rather
than quoting the best point on the curve.

---

### Phase 2.7 — Decide between them, and admit uncertainty

**What we're building:** the arbitrator. Three cutters have three opinions;
this produces one answer plus an honest confidence score.

**The order of trust:** ID-based beats rules beats PELT. When two methods agree,
confidence goes **up** (independent corroboration is real evidence). When they
disagree badly, we keep the ID-based answer and **flag it for a human**.

**Leftovers are kept, not hidden.** Events that belong to no episode — email,
coffee, unreadable apps — go into a labelled "residue" pile. The size of that
pile is itself a health metric: if it suddenly grows, either the person changed
how they work or capture broke, and both are worth knowing.

**The review tool.** Episodes sorted worst-confidence-first, each explaining
itself in plain words: *"started when LN-48213 first appeared in LoanDesk; ended
after clicking Reject."* A person can accept, adjust, split or merge. Their
corrections become new ground truth.

Human-in-the-loop here isn't an admission of failure — it's an established
approach in this research area, with published work behind it.

**How you test it:** group episodes by confidence score and check that the
high-confidence ones really are more accurate. **A confidence score that isn't
calibrated is worse than no score**, because everything downstream will believe it.

---

### Phase 2.8 — Score it properly

**What we're building:** the honest report card.

We measure boundary accuracy at three different tolerances (±15s, ±30s, ±60s —
one number hides the shape of the errors), how "pure" each episode is, how many
true cases we found at all, and how big the leftover pile is.

**We always publish all four methods' scores side by side** — dumb baseline,
ID-based, PELT, and merged. Quoting only the best one is how a project fools
itself.

**We also run the attacks a skeptic would run**, before they do:
- What if we remove the finishing-word list?
- What if we use the fixed 30-minute rule instead of learning it?
- What if we skip ID standardisation?
- **What if we treat "blind" gaps as "idle" gaps?** This one should visibly make
  things worse — proving the distinction we built in Stage 1 was worth building.

And a **failure gallery**: the ten worst segmentations with a written explanation
of why each went wrong. More useful to the next person than any average score.

**To pass Stage 2:**

| What | Must be at least |
|---|---|
| Boundary accuracy (±30s) | 85% scripted / 75% real |
| Episode purity | 90% |
| True cases found | 90% |
| Interleaved cases separated | 80% |
| Leftovers | under 25% |
| Confidence scores calibrated | yes |
| **Beats the dumb baseline** | **on every metric** |

---

## What you'll have when Stage 2 is done

✅ Sam's day, cut into labelled cases, each one knowing which loan it was about,
how confident we are, and why.

✅ A review screen where a human can fix the uncertain ones in a couple of minutes.

✅ An honest measurement of how well this works — including against published
methods and against a deliberately dumb baseline.

❌ **It still doesn't know the apps were related.** Within one episode it can see
that LoanDesk and DocVault were both used — but it draws no conclusion about
*how information moved between them*. That's Stage 3.

❌ **It doesn't know what the process is.** One episode is still just one
anecdote. Finding the pattern across 400 of them is Stage 4.

---

## The demo you can run, once Stage 2 is finished

1. Feed it the recorded session from the Stage 1 demo.
2. It should hand back your cases — one per loan ID you worked on — with the
   right start and end, and your three-minute break correctly treated as a
   boundary rather than a mystery.
3. **Now the interesting test:** deliberately work two loans at once, flipping
   between them. It should give you **two overlapping episodes**, not one merged
   mess.
4. Open the review screen. The shakiest episode should be at the top, explaining
   in plain words why it's unsure.

---

## Worth debating

1. **"What actually is a case?"** — genuinely yours to answer. One *loan*? One
   *review* of a loan (so a loan reviewed twice = two cases)? One sitting at the
   desk? It changes what Stage 4 mines and what the final report says. I'm
   proceeding on "one review" but that's an assumption, not a decision.

2. **"Should overlapping episodes be allowed?"** I say yes — it's the truth about
   how people work. But most process-mining algorithms in Stage 4 expect tidy
   non-overlapping cases, so we'd have to flatten them later. The alternative is
   forcing tidiness now and quietly being wrong about multitasking. I'd rather be
   messy and honest.

3. **"You're betting against the research literature."** True, and worth saying
   out loud. Published work segments by behaviour; we're segmenting by identifier.
   The justification is that we have data they don't. The safeguard is that we
   measure ourselves against both a dumb baseline and a published method — so if
   the bet is wrong, we'll know from the numbers rather than from a customer.

4. **"What if most work has no visible case ID?"** Then the primary design is
   wrong *and* Stage 3 is weakened at the same time, because both run on the same
   identifiers. That's why measuring ID coverage is one of the first things we do,
   not one of the last.

5. **"Is 25% leftovers acceptable?"** Honestly, I made that number up as a
   starting point. It should come from real data.
