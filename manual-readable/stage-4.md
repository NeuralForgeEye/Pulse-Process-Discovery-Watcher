# Stage 4 — Find the pattern across everyone

*Plain-English walkthrough. Technical version: `../plans/stage-4-blueprint.md`.
Evidence: `../research/stage-4-process-mining.md`.*

---

## What this stage does

Stage 3 gave us a story for each case. One case is an anecdote — it tells you what
Sam did once, not what "the process" is.

Stage 4 compares **hundreds of those stories** and answers:

- Which steps happen **nearly every time**? → that's the real backbone
- Which happen **sometimes** — and *when*? → that's a branch
- Which happened **once** and never again? → probably a mistake, not the process

The output is a map of the actual process, built from evidence rather than from
someone's memory of how it's supposed to work.

---

## One thing to know before reading: where the data comes from

Stage 4 needs lots of cases to compare. **We're building it on the assumption
that cases from different business units can be pooled together** (as hashed
identifiers — no real values anywhere).

> ⚠️ **That assumption is not confirmed.** Data governance and InfoSec haven't
> ruled on whether pooling hashed identifiers across business units is allowed.
> If they say no, we fall back to mining each unit separately and merging the
> results — those designs are already written and kept on purpose.

We're proceeding rather than waiting, because it's a conversation to have rather
than a problem to research, and three cheap precautions make the bet safe to
lose. The important one: **every business unit must use the same names for the
same steps** (the shared "activity dictionary" in Phase 4.2). If each unit
invented its own names, their results could never be combined later. That costs
nothing to do now and can't be fixed cheaply afterwards.

---

## The good news: this part is solved science

This is the least original stage in the project, and that's exactly right.

**Process mining** is a real academic field with decades of work behind it. There
are mature algorithms with names — Alpha Miner, Heuristics Miner, Inductive Miner,
ILP Miner — and a well-maintained open-source Python library, **PM4Py**, that
implements them. There's a standard way to measure whether a discovered map is any
good (fitness, precision, generalization, simplicity).

**We are not inventing any of this.** The architecture says so explicitly, and it's
correct. Our job here is to *choose well and measure honestly*.

---

## The trap the architecture doesn't mention

Here's something I found that isn't in the original plan, and it's the biggest
risk in this stage.

The architecture goes straight from "episodes" to "find which steps repeat." But
there's a missing step in between, and the research field treats it as a hard
problem in its own right.

**Stage 1 recorded this:**

```
click on "btnSearch" in window "DocVault — Search"
```

**A process map needs this:**

```
Search for the loan document
```

Getting from one to the other is called **event abstraction**, and it's where most
of the error in this stage will come from. Worse: **if you get it wrong, all your
quality scores still look fine.** The map will be measurably excellent at
describing the wrong thing.

Get it too fine-grained → a 400-box hairball nobody can read.
Get it too coarse → four boxes saying "used LoanDesk, used Chrome." Useless.

So I've added it as its own phase (4.2) with its own human review gate. Flagging
that as a change to the plan, not a detail.

---

## The picture

```
   400 episode stories from Stage 3
                │
                ▼
   ┌────────────────────────────────────────┐
   │ 4.1  SORT INTO PILES                   │
   │  "these 300 are loan reviews"          │
   │  "these 100 are complaint cases"       │
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.2  NAME THE STEPS      ⚠ risky       │
   │  click btnSearch → "Search for doc"    │
   │  (a human checks this list)            │
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.3  COUNT                             │
   │  97% do this  → BACKBONE               │
   │  31% do this  → BRANCH                 │
   │   1% did this → NOISE (drop it)        │
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.4  DRAW THE MAP  (PM4Py algorithms)  │
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.5  SCORE IT  — does it match reality?│
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.6  ADD THE APP CONNECTIONS           │
   │  with Stage 3's evidence strength      │
   └────────────────┬───────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ 4.7  EXPLAIN THE BRANCHES              │
   │  not "31% open Excel" but              │
   │  "31% open Excel WHEN figures disagree"│
   └────────────────────────────────────────┘
```

---

## The eight phases

### Phase 4.1 — Sort episodes into piles

You can't average a loan review and a complaint investigation into one map. So
first we group episodes that are the same kind of work.

**The simple way (the architecture's suggestion):** group by which apps were used
and which kind of ID was involved. Cheap and probably right most of the time.

**The problem with it:** two genuinely different processes can use the same
applications. A new loan review and a complaint investigation might both use
LoanDesk and DocVault.

**The upgrade:** a clustering algorithm called **HDBSCAN**.
*Why that one:* DBSCAN (the more famous one) needs you to guess a sensitivity
setting, and a wrong guess silently merges or shatters your groups. HDBSCAN sweeps
that setting automatically, handles groups of different sizes and tightness, and
doesn't need you to say in advance how many process types exist — which is the
thing we're trying to find out. It also **labels genuine one-offs as noise**
instead of forcing them into a pile, which is honest.

**How you test it:** build a test corpus with two different processes that
deliberately share applications. The grouping must separate them. **If the simple
attribute method also passes, we use the simple one and delete the clustering.**

---

### Phase 4.2 — Name the steps *(the risky one)*

**What we're building:** the rule that turns raw clicks into named process steps.

**Our approach:** a step is *(which app, which screen, what kind of action)*,
where the action kinds are: open/navigate, read, search, enter data, transfer
(copy/paste), decide.

*Why this way:* it's deterministic and explainable, built entirely from what Stage
1 already captured, and it matches how people describe their own jobs — *"I open
the search screen, then I open the document view."*

*Why not let an algorithm find the patterns statistically?* Because it produces
steps with no names — `cluster_17` — and the entire deliverable of this project is
a document a human can read. A statistical abstraction that improves the fitness
score by 3% and makes the output unreadable is a net loss.

**One detail that would quietly wreck everything if missed:** window titles
usually contain the case ID — *"Loan Review — LN-48213"*. If we don't strip that
out, every single case produces its own unique "screen" and the map explodes into
thousands of boxes. We strip identifiers using the patterns Stage 2 learned.
There's an automated test for this with zero tolerance.

**How you test it — and this is a gate, not a formality:**
- A **domain expert reads the list of step names** and must accept at least 80%
  as "yes, that's a real step in this process."
- A 30-minute case (~400 raw events) should come out as roughly **10–40 steps**.
  Hundreds = too fine. Under five = too coarse.
- The **same real step done by three different people** must get the same name at
  least 90% of the time — otherwise the map shows three steps where there's one.

**Why the human gate matters:** the automated quality scores in Phase 4.5 cannot
detect a bad abstraction. The map will score beautifully while describing
something that isn't the process. A person looking at the step names is the only
defence.

---

### Phase 4.3 — Count, carefully

Now the architecture's actual ask: which steps are core, which are optional, which
are noise.

- **Backbone** — in 90%+ of episodes
- **Branch** — 10–90%
- **Noise** — under 10%, dropped from the map

**The statistical honesty bit.** "8 out of 12 episodes" and "340 out of 400" are
both 67% — and they look *identical* on a bar chart. But one is nearly a
coin-flip's worth of evidence and the other is solid. So we report confidence
intervals, not bare percentages.

**And we're willing to refuse.** If a group has fewer than ~30 episodes, the
system **declines to publish a map** and says why. A confident-looking map built
from 12 episodes of one person's habits isn't a process map — it's a portrait of
one person, mislabelled. Refusing is a feature, and it will be tempting to
override it to produce a nice demo. Don't.

---

### Phase 4.4 — Draw the map

**Which algorithm?** I checked the field's big benchmark study (Augusto et al.,
IEEE TKDE 2019 — 12 real-life logs, 9 quality measures). **Being straight with
you: I only read the abstract, not the results table.** What the abstract actually
concludes is that there's **no universal winner** — performance "diverges strongly"
depending on which quality measure you care about.

So rather than quoting a winner I can't verify:

- **Primary: Inductive Miner – infrequent (IMf).** Chosen because its models are
  **guaranteed to be "sound"** — meaning they can't deadlock and a human can
  actually follow them. For a tool whose whole output is a document someone has to
  trust, an unsound map is worse than a slightly less accurate readable one. It
  also has one meaningful dial (a noise filter) that maps directly onto our
  backbone/branch/noise split.
- **Comparison: Heuristics Miner.** Built for noisy data, but **no soundness
  guarantee**. We run it anyway and publish both, so you can see what soundness
  costs us.
- **Rejected: Alpha Miner.** It's the famous teaching algorithm, and the
  architecture mentions it — but it has no noise handling and produces broken
  models on real logs. Real UI logs are nothing *but* noise.
- **Split Miner:** shows up a lot in the literature, but I couldn't verify its
  benchmark ranking, its licence, or whether there's a working Python version, and
  it's not in PM4Py's listed algorithms. Named as "evaluate if available," not
  recommended.

**How you test it:** generate a log from a **process we invented ourselves**, mine
it, and check we get our own process back. If the algorithm can't rediscover a
process we know the answer to, it won't discover one we don't.

---

### Phase 4.5 — Score the map honestly

Four standard measurements, all from PM4Py:

| Measure | Asks |
|---|---|
| **Fitness** | Can the real recorded cases actually be replayed on this map? |
| **Precision** | Does the map allow stuff that never actually happens? |
| **Generalization** | Will it cope with cases it hasn't seen? |
| **Simplicity** | Can a person read it? |

**We always report all four.** Optimising one is how you get a meaningless map —
you can trivially draw a map that allows *everything*, which scores perfect fitness
and is completely useless.

**And we hold data back.** Build the map from 80% of episodes, then test it against
the 20% it's never seen. A map that only fits the cases it was built from has
memorised, not discovered.

---

### Phase 4.6 — Show the app connections with their evidence

This is where Stage 4 shows off what Stages 1–3 bought us.

An ordinary process map has boxes and arrows. Ours also shows:

- **which application** each step happened in
- **how the applications were connected** — and *on what strength of evidence*

So an arrow from LoanDesk to DocVault isn't just an arrow. It says: *"240 episodes,
proven by copy/paste."* A different arrow might say: *"18 episodes, inferred from
on-screen visibility only."* **Those are completely different kinds of claim, and
the map shows the difference** — otherwise all the evidential care taken in Stage 3
gets thrown away at the last moment.

And where Stage 3 found no evidence at all, the map shows a **dashed "we don't
know how these connect" edge** rather than a confident line.

**How you test it:** the scripted scenario deliberately includes one app switch
with no linking evidence. The map must show that one as unexplained rather than
inventing a connection.

---

### Phase 4.7 — Explain the branches *(the payoff)*

Anyone can report *"31% of reviewers open Excel."* That's a statistic.

What's actually useful is: *"31% open Excel — **and it's the ones where the income
figures disagree**."* That's an insight, and it's the thing no procedure document
ever contains.

So for each branch we test what predicts taking it: which ID type, which app, which
preceding step, which outcome. We deliberately keep the method **shallow** — a
simple decision tree or association rules — so the answer can be stated in one
sentence in the final report. A more accurate model you can't explain is useless
here.

We also report **rework and loops** — in a QA process, people redoing steps is a
*finding*, not noise.

**A warning built into the plan:** this phase can compare individuals ("Sam always
skips step 4"). That's one config flag away from an employee surveillance tool —
which would both break the trust the capture layer depends on and probably breach
whatever consent the workforce gave. So: **aggregate by default**, per-person only
on an explicit, logged request.

**How you test it:** the scripted scenario has a deliberately planted conditional
branch. The system must find it *and state the condition*. If all it can say is
"31% open Excel" without the "because," this stage produced statistics instead of
understanding.

---

### Phase 4.8 — Show it to someone who knows the job

Run everything, publish all the numbers, then **give the map to a domain expert and
ask: is this the process? What's missing? What's wrong?**

Their answers go into the record verbatim. **This is the only real external check
we have**, and it outranks every internal metric. A map with a 0.92 fitness score
that an expert says is wrong is a wrong map with a good score.

**To pass Stage 4:**

| What | Must be |
|---|---|
| Fitness on held-out cases | ≥ 80% |
| Precision | ≥ 70% |
| Maps are sound (no deadlocks) | 100% |
| Step names accepted by expert | ≥ 80% |
| Core steps correct on scripted data | 100% |
| Conditional branch found *with its condition* | yes |
| App connections show evidence strength | 100% |
| Groups with too little data | refused, not published |
| Expert's verdict | "yes, that's recognisably the process" |

---

## What you'll have when Stage 4 is done

✅ A real map of how the work actually gets done — backbone, branches, and the
conditions that trigger them — built from hundreds of real cases rather than
anyone's recollection.

✅ Applications shown as part of the process, with connections labelled by how
strongly they're evidenced.

✅ Honest quality scores, and a system that **refuses** to produce a map when
there isn't enough data.

❌ **It doesn't know what the process is *for*.** It can show you a shape that
opens a record, compares things, and ends in a decision — but it can't yet tell you
that's a QA/QC review. That's Stage 5.

❌ **It's not a document yet.** It's a model plus tables. Turning it into something
a newcomer can read is Stage 6.

---

## Worth debating

1. **"You added a phase to the architecture."** Yes — event abstraction (4.2).
   I think the plan has a real gap there, and the evidence is that SmartRPA's
   published pipeline has the same component. But it's your architecture; if you
   disagree, say so.

2. **"Why refuse to produce a map on small data?"** Because the alternative is
   presenting one person's habits as organisational truth, with a confident-looking
   diagram attached. I'd rather ship "not enough data yet" — but I recognise that's
   commercially awkward in exactly the situations where a customer wants to see
   something.

3. **"You picked soundness over accuracy."** IMf guarantees followable models;
   Heuristics Miner might fit the data slightly better but can produce maps that
   deadlock. I chose readability because the deliverable is a document humans
   trust. Arguable the other way if you'd rather maximise fit.

4. **"You didn't read the benchmark."** Correct — abstract only. It's the single
   most useful document for choosing a miner and it should be read properly before
   this phase is built. I'd rather flag that than quote a ranking I can't back up.

5. **The surveillance risk in 4.7 is real.** The capability to compare individuals
   falls out of this analysis whether we want it or not. Worth deciding the policy
   deliberately rather than discovering it when someone asks for the feature.
