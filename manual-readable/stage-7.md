# Stage 7 — Notice when the process quietly changes

*Plain-English walkthrough. Technical version: `../plans/stage-7-blueprint.md`.
Evidence: `../research/stage-7-keeping-current.md`.*

---

## What this stage does

Because Pulse never stops listening, it can notice something no one-off study
ever could: **the process changed and nobody told anyone.**

A new compliance step gets added. A team quietly stops using one system. A
shortcut spreads from one person to the whole floor. Six months later the
beautiful document from Stage 6 describes a process that no longer exists.

Stage 7 watches for that, works out *what* changed, and **tells a human** — it
never quietly rewrites the map on its own.

The architecture marks this stage optional for v1. **I mostly agree — but not
entirely, and the exception matters.** See below.

---

## The trap that would sink this stage

Here's the problem, and it's specific to how Pulse works.

Pulse reads **the structure of application screens**. That's its whole advantage
over screen recording. But it creates a vulnerability that no standard
drift-detection method worries about:

```
   THE VENDOR SHIPS A LOANDESK UI REDESIGN
                    │
                    ▼
   The buttons have different internal identifiers
                    │
                    ▼
   Stage 1 sees different elements
                    │
                    ▼
   Stage 4 generates different step names
                    │
                    ▼
   Nothing matches the old process map
                    │
                    ▼
   ╔══════════════════════════════════════════╗
   ║  "MAJOR PROCESS CHANGE DETECTED!"        ║
   ║                                          ║
   ║  ...except nothing changed at all.       ║
   ║  People are doing exactly the same job.  ║
   ║  The buttons just moved.                 ║
   ╚══════════════════════════════════════════╝
```

Every off-the-shelf drift detector would report this as a dramatic process change,
confidently and at length.

**And a tool that cries wolf every time a vendor ships an update gets its alerts
ignored within a month** — which destroys the only advantage continuous capture
gives you.

The research literature doesn't cover this, reasonably enough: it assumes event
logs come from systems that label their own activities consistently. Ours don't —
we're inferring labels from UI structure. **So this is our problem to solve, and
it's the first thing this stage does.**

---

## How we tell the two apart

They actually look quite different, once you know what to look for:

| | **UI changed** | **Process changed** |
|---|---|---|
| Step *names/identifiers* | churn heavily | stay stable |
| Order of what people do | stays the same | changes |
| When it starts | **abruptly, everyone at once** (a deployment) | **gradually, person by person** (a habit spreading) |
| Capture health (things Stage 1 tracks) | spikes — more "couldn't read that" events | flat |

So before any drift alert is raised, it's cross-checked against health signals we
already collect. If step names churned at the same instant the fit dropped, the
first hypothesis is **a UI change**, not a process change.

And **"ambiguous" is an allowed answer.** Early on it should be a common one.
Forcing a binary call would manufacture exactly the false confidence this whole
project is built to avoid.

---

## Where I'd push back on the architecture

The plan says Stage 7 is optional for v1. I agree about *process drift* — that can
wait.

**I don't agree about capture health.** If a monitored application changes its UI
and nobody notices, Stages 1 through 4 degrade **silently**. Capture rates drop,
episodes get worse, links thin out — and the output still looks completely
confident. You'd find out when a customer told you the map was wrong.

*"We can see 40% less of LoanDesk than we could last month"* is a useful alert on
day one, independent of any process question. **I'd put that half in v1.**

Flagging it rather than deciding it — it's your call.

---

## The four phases

### Phase 7.1 — Take a snapshot to compare against

You can't detect change without a baseline. So every published process description
gets frozen as a version: the map, the step names, the statistics, the quality
scores, **and the capture conditions at the time** — which applications, which
versions, how well we could see each one.

Those capture conditions are the **control variables**. Without them, when
something diverges later you can't tell which of the two causes it was — and the
central question of this stage becomes unanswerable.

**And we keep every version.** The architecture requires never silently trusting
one over the other, which means both have to still exist.

**How you test it:** compare two snapshots with deliberately known differences.
Every real change must be reported — and **nothing else**. A diff that reports
phantom changes trains people to ignore it.

---

### Phase 7.2 — Watch our own eyesight *(the part I'd ship in v1)*

Continuously track, per application: how often capture failed, how often we
couldn't identify an element, whether step names are churning, whether the
leftover pile from Stage 2 is growing, whether Stage 3's evidence is getting
weaker.

Then classify anything that diverges as **capture change**, **process change**, or
**ambiguous**.

**One more thing this phase does that matters:** when a UI change *is* confirmed,
it helps **re-anchor** the step dictionary to the new screen layout, so history
stays comparable. Without that, a single vendor update wipes out your baseline and
you start from scratch.

**How you test it — the gate for this whole stage:**
1. Change the fixture app's internal control names **without changing the workflow
   at all.** It must say `capture_change`. **Not** `process_change`.
2. Change the **workflow** while leaving the UI identical. It must say
   `process_change`.

Get these two right and the alerts are worth reading. Get them wrong and nobody
will read them.

---

### Phase 7.3 — Detect real drift, and say what changed

**The main method:** take new cases, replay them against the existing map, and
watch how well they fit over time. Fitness dropping = real work no longer matches
the map.

*Why this method:* we already compute it in Stage 4, it means something obvious in
plain English, and — most importantly — it tells us **which steps** stopped
matching, not just that *something* changed.

That last property is the reason we don't lead with the famous general-purpose
detectors (**ADWIN**, **Page-Hinkley**). They're mature and cheap and we use them
as a **cheap early warning** — but the literature notes directly that they "lack
process awareness and structural traceability." They can say *that* something
changed, not *what*. And "what changed" is the entire deliverable here. An alert
saying "drift detected" with no explanation creates work rather than insight.

**We also classify the kind of drift**, because it changes what a human should do:
- **Sudden** → usually a policy or system change
- **Gradual** → usually a practice spreading person to person
- **Incremental** / **recurring** → e.g. seasonal patterns

**And we describe it in words:** *"Since March, 40% of cases include a new step —
checking the sanctions list in [system] — before approval. This step did not
appear in the baseline."*

**How you test it:** build test data with a known sudden change, a known gradual
change, and **no change at all**. Detect the first two with the right timing.
**The third matters most** — a detector that finds drift in stable data is worse
than having no detector.

---

### Phase 7.4 — Tell a human, don't act alone

**The map is never silently replaced.** The architecture is explicit and it's
right: flag for human review rather than trusting either version.

A silently updated process map has no version anyone ever agreed to — useless as a
reference document and genuinely dangerous as an audit artefact in a regulated
setting.

So: side-by-side old and new, the difference in words, the evidence, the
capture-health cross-check, and the new candidate's quality scores. The human
chooses: accept, keep the old one, mark it as a capture problem, or wait for more
data.

**Every alert gets an owner.** Capture-health alerts go to whoever runs the
deployment; process-drift alerts go to the process owner. **An alert with no owner
is just noise.**

**To pass Stage 7:**

| What | Must be |
|---|---|
| Known sudden change detected, right timing | yes |
| Known gradual change detected | yes |
| **False alarms on stable data** | **zero** |
| Simulated UI change called `capture_change` | yes |
| Simulated workflow change called `process_change` | yes |
| Points at the right steps | ≥ 80% |
| Map never replaced without a human decision | 100% |
| Every alert has an owner and a plain description | 100% |

---

## What you'll have when Stage 7 is done

✅ Early warning when the real process drifts away from the documented one — with
a plain description of what changed.

✅ Operational alerts when **Pulse itself** starts seeing less than it used to —
which is arguably the more useful of the two, day to day.

✅ A version history of the process with a human decision recorded at each change.
In a regulated environment, that audit trail may be worth as much as the map.

---

## Worth debating

1. **"Should any of this be in v1?"** My recommendation: **capture-health
   monitoring yes, process-drift detection no.** The first protects everything else
   from silently rotting; the second is a genuinely optional enhancement. Splitting
   it that way is a scoping decision worth making deliberately rather than
   inheriting from the word "optional".

2. **"How much drift is drift?"** No idea yet, honestly. Any threshold now is a
   guess. Too sensitive → alert fatigue → nobody reads them. Too loose → it never
   fires and the stage is decorative. Needs real data.

3. **"Isn't this just employee monitoring by another name?"** It could become
   that — *"Person X's work diverges from the process"* is one query away from this
   data. It would be a misuse: this stage exists to notice **the process** changing,
   not to score individuals. Same guard as Stage 4: aggregate by default,
   individual views only on an explicit and logged request. Worth deciding the
   policy now rather than when someone asks for the feature.

4. **"What if nobody reads the alerts?"** Then the map goes stale and the stage was
   pointless. That's not a technical problem — it's why every alert needs a named
   owner and a clear "here's what changed and what to do about it."

5. **The UI-change problem might be bigger than the drift problem.** If the target
   environment ships UI updates frequently, then knowing when Pulse's eyesight
   degraded becomes the primary feature and drift detection becomes the side
   benefit. Worth checking how often the target applications actually change.
