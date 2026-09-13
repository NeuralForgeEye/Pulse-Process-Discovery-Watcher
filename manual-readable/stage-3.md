# Stage 3 — Join the dots across applications

*Plain-English walkthrough. Technical version: `../plans/stage-3-blueprint.md`.
Evidence: `../research/stage-3-cross-application-linking.md`.*

---

## What this stage does

Stage 2 handed us a box of events labelled *"this was Sam handling loan
LN-48213."* Inside that box, Sam used three applications.

Stage 3 answers: **how were those applications actually connected?**

Not "Sam used LoanDesk and DocVault around the same time" — that's just
co-location. We want: *"Sam read the loan ID in LoanDesk, carried it to DocVault,
and searched with it"* — and we want to say **how we know**.

---

## Why this is the stage that matters

This is where the architecture expects the real invention to live, so it deserves
the most scrutiny. Here's the honest situation, found by actually searching:

**Part of it is already done by other people.**

- **Data-loss-prevention (DLP) security software already does the copy/paste
  part.** Those agents record which app you copied from, and inspect the content
  when you paste into a different app — that's how they stop you pasting customer
  data into Gmail. It's in granted patents and shipping products. So "track a
  value from app A to app B via the clipboard" is **not new**.
- **Academic work already detects data transfers between applications** from
  interaction logs. Leno et al. (2020) went further than us in one respect —
  they work out *how the value was reshaped* on the way (e.g. `LN-48213` → `48213`).

**What doesn't appear to exist anywhere I found** is the part described below in
Phase 3.6 — using *repetition across many people* to promote evidence that would
be too weak to trust on its own. More on that when we get there.

I'd rather you hear this now than after a patent attorney charges you for it.

---

## The core idea: rank the evidence honestly

Sam's loan ID ends up in two applications. *Why?* There are four possible kinds
of evidence, and they are genuinely not equal:

```
 ┌────────────────────────────────────────────────────────────────┐
 │ TIER 1 — PROVEN                                    ★★★★        │
 │ Copied in LoanDesk. Pasted in DocVault.                        │
 │ This isn't inference. It's proof.                              │
 ├────────────────────────────────────────────────────────────────┤
 │ TIER 2 — DELIBERATE                                ★★★         │
 │ Highlighted it in LoanDesk, then it turns up in DocVault.      │
 │ Nobody highlights by accident. Strong, not proof.              │
 ├────────────────────────────────────────────────────────────────┤
 │ TIER 3 — VISIBLE                                   ★★          │
 │ It was on screen in LoanDesk, then appeared in DocVault.       │
 │ Reasonable. But maybe they never actually looked at it.        │
 ├────────────────────────────────────────────────────────────────┤
 │ TIER 4 — COINCIDENCE?                              ★           │
 │ Same value in both. Nothing else.                              │
 │ NEVER trusted on its own. (See Phase 3.6.)                     │
 └────────────────────────────────────────────────────────────────┘
```

And a fifth possibility the system must be willing to admit:

> **"Sam just remembered the number and typed it."** No copy, no highlight, never
> captured on screen. A real link, with **zero** digital evidence. The correct
> answer here is *"we don't know how these connected"* — and getting the system to
> say that instead of inventing something is a specific thing we test for.

---

## The picture

```
   ONE EPISODE (from Stage 2): loan LN-48213, 9:02–9:08

   LoanDesk ──────────────────────────────► DocVault ──────► Excel
      │                                        │                │
      │  copied "LN-48213" at 9:03             │                │
      └────────── PROOF (Tier 1) ──────────────┘                │
                                               │                │
      "$84,000" was on screen 9:05             │                │
      └─────── VISIBLE (Tier 3) ───────────────────────────────┘
                                                       (weak-ish)

      Sam switched to Excel at 9:06 with nothing linking them
      └─────── ??? recorded as UNEXPLAINED, not guessed ────────

                              │
                              ▼
   ┌──────────────────────────────────────────────────────────┐
   │ THE STORY                                                 │
   │ 1. Opened loan record LN-48213 in LoanDesk                │
   │ 2. Copied the loan ID              [proven]               │
   │ 3. Searched DocVault with it       [proven]               │
   │ 4. Read income $84,000                                     │
   │ 5. Opened Excel                    [unexplained gap]      │
   │ 6. Returned to LoanDesk, clicked Reject                    │
   └──────────────────────────────────────────────────────────┘
```

Note step 5. **An account with an honest hole in it is worth more than a smooth
one with a guess in it** — because the moment you can't trust one step, you can't
trust any of them.

---

## The eight phases

### Phase 3.1 — Decide what a "link" is, and build the answer key

We define the link record (from where, to where, what value, which tier, how
confident, which direction) and build a test set where we **know** the truth.

Crucially, the test set includes **traps**:
- The same value appearing in two genuinely unrelated apps (must NOT link)
- A value typed from memory (must be reported as unexplained, **not invented**)
- A value that changed shape in transit (`LN-48213` → `48213`)

**How you test it:** every link in the answer key must be something a human can
justify by looking at the timeline. If a person can't defend it, it doesn't
belong in the answer key.

---

### Phase 3.2 — Narrow down the pairs worth checking

**The problem:** an episode has thousands of events. Checking every pair against
every other pair is millions of comparisons, almost all pointless.

**The technique — "blocking"**, borrowed from a well-established field called
*record linkage* (the science of working out whether two database records are the
same person). Only compare events that **share a value** and are in **different
applications**. That's a handful of pairs instead of millions.

**The trap we handle here:** some values are worthless as evidence. If both apps
show `0`, or `N/A`, or today's date, that proves nothing — those values are
everywhere. So we count how common each value is across the whole corpus, and
weight accordingly. A shared `LN-48213` (seen twice ever) is near-decisive. A
shared `0` (seen 40,000 times) is noise.

**How you test it:** 99% of known true links must survive this filtering step.
Throwing away a real link here can never be recovered later, so this number
matters more than efficiency.

---

### Phase 3.3 — The certain ones: copy and paste

Stage 1 already paired copies with pastes. Here we just turn cross-application
pairs into links. Direction is **known** — copy is the source, paste is the
destination.

**How you test it:** 100% of known copy/paste links found, with correct
direction. This is deterministic; anything less means Stage 1 has a bug and the
fix belongs there, not here.

**Honesty note:** this tier is the part DLP products already do. We shouldn't
describe it as novel anywhere — including in the final report.

---

### Phase 3.4 — The uncertain ones: highlighting and visibility

Now the inference. Value highlighted in app A, appears in app B. Or: value merely
visible in app A, appears in app B.

**A nice property of the design:** we **learn the time window from the certain
tier**. We measure how long copy→paste actually takes in this corpus, and use
that to set the window for the uncertain tiers. The proven evidence calibrates
the unproven evidence. No invented numbers.

**One subtle thing we get right.** A copy is *usually preceded by* a highlight,
which is *preceded by* the value being visible. That's **one act**, not three
pieces of evidence. Counting it three times would triple our confidence in
something we saw once. So each candidate gets exactly **one** tier — the
strongest that applies.

**How you test it — the important one:** in the test scenario, include a value
Sam typed **from memory**. The system must produce **no link** and report an
unexplained gap. Inventing a link here is the exact failure this stage must not
have — and it's invisible unless you deliberately test for it, because a
fabricated link looks just like a correct one.

---

### Phase 3.5 — Turn evidence into a number that means something

**The problem with the architecture's ranking as written:** it gives you an
*order* (proof beats highlight beats visible), but not a *number*. So you can't
answer "is one highlight worth more than three sightings?" or set a threshold.

**What we use:** additive scoring in **log-odds**, borrowed from the
**Fellegi–Sunter** framework — the standard method for probabilistic record
linkage, used by national statistics offices, with mature open-source tooling
(**Splink**, from the UK Ministry of Justice). Its central idea is exactly what we
need: **evidence weights that add up**, plus an adjustment so that rare values
count more than common ones.

We set the weights by hand first (debuggable, explainable, needs no training
data), then test whether letting the algorithm learn them does better. **We adopt
the learned version only if it measurably wins**, not because it sounds more
sophisticated.

**What we deliberately rejected:** *Dempster–Shafer theory*, the textbook answer
for "combining uncertain evidence." Two documented reasons: it produces
counter-intuitive results when evidence conflicts (an open problem in that
literature after decades of attempted fixes), and it assumes all your evidence
sources are **equally reliable** — which our design violates on purpose, since
unequal reliability *is* the whole idea. Using a framework whose core assumption
your problem breaks, for the sake of mathematical respectability, is a bad trade.

**How you test it:** group links by score and check that high-scoring ones really
are more often correct. An uncalibrated confidence number is worse than none at
all, because everything downstream will believe it.

---

### Phase 3.6 — The distinctive bit: let the crowd vouch for the weak evidence

This is the part that appears to be genuinely ours.

**The idea.** One instance of *"the loan ID was visible in LoanDesk, then typed
into DocVault"* is circumstantial — could be coincidence.

But suppose that **exact same field-to-field relationship** —
`LoanDesk's Loan ID box → DocVault's search box` — shows up across 300 episodes
and 12 different people, and in 240 of those it was **proven** by an actual
copy/paste.

Then the *relationship* is established. And that lets us accept the weak
instances: not because that one instance got stronger, but because we now know
this is a thing people routinely do.

So every link carries **two separate numbers**:
- **What we saw this time** (instance evidence)
- **How often this relationship is proven elsewhere** (population evidence)

We keep them separate on purpose, so a reviewer can read the actual reasoning:
*"weak on its own, but this exact connection is proven 240 times elsewhere."*
Collapsing that into one number would destroy the only sentence that justifies it.

**The danger — and the guard against it.** This creates a loop: population
statistics validate individual links, and individual links feed population
statistics. Left alone, **the system would corroborate itself into ever-growing
confidence** — which looks exactly like learning until you check.

So the passes are strictly separated:
- **Pass 1** counts relationships using **only proven and deliberate evidence**.
- **Pass 2** promotes weak links using those counts.
- **Pass 2's results never feed back into Pass 1.**

**How you test it:** run Pass 2, then recompute Pass 1. **The numbers must be
identical.** If they changed, feedback has leaked in and the confidence scores are
fiction. This is the single most important test in Stage 3.

And a hard cap: coincidence-only evidence can reach "probable" but **never
"proven"**, no matter how often it recurs.

---

### Phase 3.7 — Write the episode's story

**What we're building:** the actual Stage 3 deliverable — one connected account
per episode, with gaps marked as gaps.

We produce it in two formats:
1. **OCEL 2.0** — a process-mining standard where one event can reference several
   "objects" (the loan, the document, the application). That's a precise fit for
   our data, and **PM4Py** (the main open-source process-mining library) reads it
   directly — so Stage 4 gets real algorithms for free instead of us writing our
   own.
2. **A plain link table** — for Stage 6's human-readable write-up, which needs
   the evidence wording that the standard has no place for.

**How you test it:** show the generated story to someone who watched the session
happen and ask "is this what happened?" That's the architecture's own checkpoint,
and it's the right one.

We also load the OCEL file into PM4Py and draw a graph from it — a cheap early
smoke test that Stage 4 is actually going to work, taken now rather than
discovered later.

---

### Phase 3.8 — Score it against two baselines

**Two deliberately naive comparisons:**

1. **Timing only** — "any two apps used within 30 seconds are linked." High
   recall, terrible precision. Shows what the evidence model actually buys.
2. **Copy/paste only** — the honest *"what a DLP tool could already tell you"*
   baseline. High precision, low recall.

**The gap between baseline 2 and our full model is the actual contribution of
this stage.** That specific number is the answer to "so what's new here?" — and
we should quote it rather than describing the approach in adjectives.

**To pass Stage 3:**

| What | Must be |
|---|---|
| Copy/paste links correct | 100% |
| Overall link precision | ≥ 95% |
| Overall link recall | ≥ 80% |
| Direction correct (when asserted) | ≥ 95% |
| **False links on the coincidence traps** | **zero** |
| Unexplained gaps correctly admitted | ≥ 90% |
| The circularity test | passes exactly |

Notice recall (80%) is allowed to be lower than precision (95%). That's
deliberate: **a missed link makes the map incomplete; a false link makes it
wrong.** An incomplete map that knows it's incomplete is useful. A wrong map that
sounds confident is actively harmful.

---

## What you'll have when Stage 3 is done

✅ For each case, a readable account of what happened across all the applications
involved — with each connection labelled by how strongly it's supported.

✅ Honest holes where the evidence genuinely isn't there.

✅ A catalogue of the field-to-field relationships that recur across the
organisation — *"people routinely carry the loan ID from LoanDesk's ID box to
DocVault's search box"* — which is itself a useful finding before any mining
happens.

❌ **It's still one case at a time.** Sam's LN-48213 review is one anecdote. It
can't tell you whether the Excel check is a normal part of the process or
something Sam alone does. That's Stage 4.

---

## Worth debating

1. **"You said this stage was the novel one, and now you're saying DLP already
   does it."** Partly, yes — the copy/paste tracking part. What's left is the
   evidence-ranking plus the population-corroboration mechanism in Phase 3.6. I
   think that's real, but it's a *combination* claim, which is the weakest kind,
   and **I only read patent summaries, not claims.** Before spending money on a
   filing, get an attorney to search this specific mechanism.

2. **"Why not just track the data properly instead of inferring it?"** Good
   question, and there's a real technology for it — *taint tracking*, which
   follows actual bytes through a system. It's used in security research. It
   doesn't work here: every working implementation instruments the execution
   environment (Android's VM, a compiler, a whole-system emulator) with 14–32%
   overhead *where it works at all*. Windows business apps are closed-source
   binaries on a real machine. It's not an option at any price.

3. **"Which direction did the value go?"** Often genuinely unknowable — both apps
   might have read it from a third system. I propose asserting direction only when
   copy/paste or highlighting proves it, and saying "connected, direction unknown"
   otherwise. A domain expert might prefer a different default, and it affects how
   readable the final report is.

4. **"Is the population trick actually sound, or is it circular?"** It's the thing
   I'd attack first if I were reviewing this. The two-pass separation is the
   defence, and the circularity test is how we prove the defence holds — but it
   deserves a skeptical human read **before** it's built, not after.

5. **Everything here rests on Stage 2 finding visible case IDs.** If most real
   work has no on-screen identifier, all four tiers thin out at once and this
   stage degrades along with its defensibility. That's why measuring ID coverage
   is an early task, not a late one.
