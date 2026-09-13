# Pulse — The Big Picture

*The whole system in plain English. Read this before anything else.*

---

## 1. The problem we're solving

A company has a process. Say: **reviewing loan applications for errors before
they're approved.** Ask five people how that process works and you get five
different answers, none of them complete. The written procedure document is
three years old. Nobody has ever actually mapped what people *really* do —
including the shortcuts, the exceptions, and the "oh, for those cases I check a
different system first."

The existing way to find out is to **record people's screens all day**, then use
OCR (software reading the pixels on screen like a human eye would) to work out
what was happening in the video. That's what a tool like SKAN does. It works,
but it means you're storing video of everything an employee does, and your
understanding of the process is only as good as your software's ability to read
blurry text off a screenshot.

**Pulse does the same job, but listens instead of watching.**

---

## 1b. Two things you should know before reading further

**This is an internal Wells Fargo tool**, not a product sold to other companies.
That shapes everything: data never leaves the bank, but the controls external
vendors must satisfy still define the bar we hold ourselves to. See
`platform.md`.

**And the original "no OCR, no video" pitch has been revised.** Research into
what SKAN actually does showed two things the plan didn't anticipate: their raw
screenshots never leave the customer's network either (so "we don't store video"
isn't the advantage it looked like), and they explicitly cover Citrix, VDI and
mainframes — exactly where a pure metadata approach is blind.

So Pulse now uses **tiered sensing**: exact structural reads wherever they're
available, computer vision **only** where no structural layer exists, and every
captured value permanently stamped with which sensor produced it. The full
reasoning is in `platform.md`; it's worth reading before the stage files.

---

## 2. The core idea, in one sentence

> Every application already tells the computer what's on its screen — that's how
> screen readers work for blind users. Pulse listens to that wherever it can,
> and only falls back to looking at pixels where no application is talking.

When you look at an application window, you see pixels. But underneath, Windows
knows that window contains *a text box called "Loan ID" containing the value
"LN-48213"*, sitting next to *a button labelled "Approve"*. That structured
description already exists. Screen readers read it aloud. Pulse writes it down.

**The difference this makes:**

| | Screen recording + OCR | Pulse (accessibility layer) |
|---|---|---|
| What's stored | Video frames | A text diary of events |
| "What's in that field?" | Guess from pixels; breaks if the font, theme, or resolution changes | The application tells you exactly: `Loan ID = LN-48213` |
| "Did they copy that value?" | Can't tell from a picture | Yes, and here's the exact value and where it was pasted |
| Storage per user per day | Gigabytes | Tens of megabytes |
| Works when the screen is off / minimised | No | Partly — we only capture what the person actually interacted with |
| Works inside Citrix / remote desktop | **Yes** | **Yes**, via the vision tier — but as a fallback, and marked as inferred rather than exact |
| Do you know which values are exact and which are guesses? | No — everything is a recognition | **Yes** — every value is stamped with its sensor |

---

## 3. The example we'll use everywhere

Meet **Sam**, a QA reviewer at a lender. Sam checks loan files before approval.
Here is one case, start to finish — roughly six minutes of their day:

1. Sam opens **LoanDesk** (an internal Windows desktop app) and sees loan
   **LN-48213** waiting for review.
2. Sam highlights the loan ID with the mouse and copies it. (`Ctrl+C`)
3. Sam switches to **Chrome**, opens **DocVault** (a web app), and pastes the ID
   into the search box.
4. DocVault shows the applicant's income documents. Sam reads the stated income:
   **$84,000**.
5. Sam switches back to LoanDesk and compares it to the declared figure there:
   **$92,000**. They don't match.
6. Sam opens **Excel** to check the lender's tolerance threshold for income
   variance.
7. Sam goes back to LoanDesk, clicks **Reject**, and types a reviewer comment:
   *"Income mismatch — documents show 84k vs declared 92k."*
8. Sam moves on to loan LN-48214 and starts again.

Nobody wrote that process down. Step 6 — the Excel check — isn't in any
procedure document; Sam just does it. **That is exactly the kind of thing Pulse
is built to discover**, by watching this happen 400 times across 12 people and
noticing the pattern.

Keep Sam in your head. Every stage below is explained using this one case.

---

## 4. The seven stages, as a story

Each stage takes what the previous one produced and adds one thing. Nothing
skips ahead.

```
   Sam works normally, all day, across many apps
                    │
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 1   LISTEN                                  │
   │  Write down everything meaningful, non-stop        │
   │  OUT: one long timeline of events                  │
   └───────────────────────────────────────────────────┘
                    │  "9:02:14 copied 'LN-48213' from LoanDesk
                    │   9:02:19 pasted it into DocVault search…"
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 2   CUT IT UP                               │
   │  Find where one case starts and ends               │
   │  OUT: episodes — one case each                     │
   └───────────────────────────────────────────────────┘
                    │  "Everything from 9:02 to 9:08 was one review:
                    │   loan LN-48213"
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 3   JOIN THE DOTS  ◄── the hard, novel bit  │
   │  Work out how the apps were connected in that case │
   │  OUT: one connected story per episode              │
   └───────────────────────────────────────────────────┘
                    │  "The ID Sam copied from LoanDesk is the same ID
                    │   they searched in DocVault — proven by copy/paste"
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 4   FIND THE PATTERN                        │
   │  Compare hundreds of episodes; find what's common  │
   │  OUT: the real process map, with branches          │
   └───────────────────────────────────────────────────┘
                    │  "97% of reviews do steps 1-5. 31% also open Excel —
                    │   always when the income figures disagree."
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 5   NAME IT                                 │
   │  Work out what kind of process this is             │
   │  OUT: "this is a QA/QC review" (+ confidence)      │
   └───────────────────────────────────────────────────┘
                    │
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 6   WRITE IT DOWN                           │
   │  The actual deliverable: a clear written process   │
   │  OUT: a document a newcomer can understand         │
   └───────────────────────────────────────────────────┘
                    │
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  STAGE 7   KEEP IT HONEST  (optional, later)       │
   │  Notice when the real process quietly changes      │
   └───────────────────────────────────────────────────┘
```

### Stage 1 — Listen *(blueprinted in detail — see `stage-1.md`)*

Sit quietly on Sam's machine and write down everything meaningful: every click,
every value typed, every highlight, every copy and paste, every switch between
applications — **and what the screen was showing at that moment.** No video.

*After Stage 1 we have:* one long, ordered list of events for Sam's whole day.
Roughly 3,000–8,000 events. It knows nothing about "cases" yet — it's just an
honest diary.

### Stage 2 — Cut it up *(not yet researched)*

That diary runs all day without breaks. Where does one loan review end and the
next begin? The plan is to look for natural signals: a long pause, a brand-new
loan ID appearing for the first time, or a final action like clicking "Approve"
or "Reject".

*After Stage 2 we have:* the day sliced into **episodes** — "these 47 events
were one review of loan LN-48213."

### Stage 3 — Join the dots *(not yet researched — the interesting one)*

Inside one episode, how do we know LoanDesk and DocVault were part of the *same*
piece of work, and not two unrelated things Sam happened to do close together?

Because **the same value appears in both**. The plan ranks the evidence:

1. **Copied in App A, pasted in App B** — proof. Can't argue with it.
2. **Highlighted the value, then typed it elsewhere** — strong. They clearly
   looked at it on purpose.
3. **The value was just visible on screen, then appeared elsewhere** — reasonable
   guess, not proof.
4. **Same value in both apps, nothing else linking them** — weak. Only trusted if
   the same pattern shows up again and again across many episodes.

This is the part the original architecture flags as most likely to be genuinely
new, and the research so far agrees — competitors capture *that* a copy happened
but deliberately don't keep *what* was copied, which makes this kind of linking
impossible for them.

### Stage 4 — Find the pattern *(not yet researched)*

One episode is an anecdote. Four hundred episodes are evidence. This stage
compares them all and asks: which steps happen nearly every time (the real
backbone)? Which happen sometimes (a branch, like Sam's Excel check)? Which
happened once and are probably just someone's mistake?

This is **process mining** — a real, established academic field with decades of
work behind it and mature open-source tools (PM4Py, and algorithms named Alpha
Miner, Heuristic Miner, Inductive Miner). **We are not inventing this maths.**
The job is picking which existing algorithm handles our cross-application data
best.

### Stage 5 — Name it *(not yet researched)*

The map from Stage 4 shows the *shape* of the process but not its *meaning*. Two
clues give us the meaning: the shape itself (open a record → compare things →
end in approve/reject is a recognisably QA-shaped process), and the actual words
on screen we captured back in Stage 1 ("Approve", "Reviewer Comments",
"Compliance Check").

⚠️ **This is the stage most at risk of becoming "just ask an LLM"**, which the
project's own rules call out as a failure mode. When we get here, that needs
watching closely.

### Stage 6 — Write it down *(not yet researched)*

The actual product: a clear written description of the process. Which apps it
touches, the steps in order, where it branches, where the cross-app links are,
what kind of process it is. Understandable by someone who has never watched the
job being done.

**Where this project deliberately stops.** Turning that description into working
automation is somebody else's problem, on purpose.

### Stage 7 — Keep it honest *(optional, later)*

Because we never stopped listening, we can notice six months later that the real
process has drifted from the map — and flag it for a human rather than silently
trusting either version.

---

## 5. What's actually been decided so far

| Stage | Blueprint | Researched | Phases | Plain-English |
|---|---|---|---|---|
| 1 — Listen | ✅ | ✅ | 9 | `stage-1.md` |
| 2 — Cut it up | ✅ | ✅ | 8 | `stage-2.md` |
| 3 — Join the dots | ✅ | ✅ | 8 | `stage-3.md` |
| 4 — Find the pattern | ✅ | ✅ | 8 | `stage-4.md` |
| 5 — Name it | ✅ | ✅ | 5 | `stage-5.md` |
| 6 — Write it down | ✅ | ✅ | 5 | `stage-6.md` |
| 7 — Keep it honest | ✅ | ✅ | 4 | `stage-7.md` |

**No code has been written yet for any stage.** Everything so far is planning —
but planning backed by real research: named algorithms, named libraries,
prior-art searches, and the case for and against each choice written out.

**Two changes to the original architecture** came out of that research, and both
need your sign-off:

- **Stage 4 gained a phase** — *event abstraction* (turning raw clicks into named
  process steps). The original plan jumps over it; the research field treats it as
  a hard problem in its own right, and every number in Stage 4 depends on it.
- **Half of Stage 7 should arrive earlier than "optional."** Watching whether
  *Pulse itself* can still see properly isn't optional — if an application's UI
  changes and nobody notices, Stages 1–4 rot silently while still looking
  confident.

**Where to start building isn't necessarily Stage 1, Phase 1.** Both of the
project's biggest risks — can we see into the target applications at all, and do
real cases carry a visible ID — can be measured with a fraction of Stage 1 plus
one phase of Stage 2. There's a suggested risk-first build order at the bottom of
`../plans/BUILD-STATUS.md`.

---

## 6. Honest caveats you should know up front

Three things that a skeptical reviewer would hit you with. Better you hear them
from me first.

### "This isn't new."

Stage 1 — capturing process signals from application metadata instead of pixels
— **is already sold commercially.** A tool called **Paxray** advertises exactly
this: no screenshots, no video, only technical interactions. **KYP.ai** does the
same and includes clipboard monitoring. The original architecture says this
sensing method is one "no one else in our space is using." That isn't
supportable as written.

**What may still be genuinely new** is narrower and lives at Stage 3: Paxray
deliberately records *that* you pressed Ctrl+C but never *what you copied*.
Pulse keeps the value and uses it to prove two applications were part of one
piece of work. That's a different mechanism with different consequences — but
it's a Stage 3 claim, not a Stage 1 claim.

### "It used to go blind inside Citrix." — now addressed, at a cost

If people work inside Citrix or a remote desktop, the local machine receives
**pictures of an application running somewhere else** — there's no underlying
structure to listen to. SKAN advertises coverage of exactly these environments.

**Decision taken:** Pulse adds a computer-vision tier for those surfaces only.
Coverage now matches; what stays different is that vision is our *fallback*
rather than our primary, so most values are exact rather than recognised — and
every value says which it was.

**The honest catch:** that vision tier **cannot be tested outside the Wells
Fargo environment**, because the Citrix and mainframe screens it exists to read
aren't available on a development machine. It will be flagged as untested until
it has run for real. Don't let anyone demo it as proven.

### "Capturing what's on screen is a big privacy ask." — now answered structurally

Keeping the *values* is the whole point, and it's also the whole risk. Paxray
can tell a works council "we never store your content." We can't say that
sentence and still do Stage 3.

**Decision taken:** sensitive identifiers are converted to a **one-way keyed
hash at the moment of capture**, using a key from the internal Vault. Cleartext
never enters the pipeline at all — so the security argument is structural rather
than "we promise to handle it carefully." Matching still works, because the same
value always produces the same hash.

Button labels and screen titles stay readable, deliberately: they aren't
personal data, and Stages 4 and 5 can't work without them. A separate locked and
audited vault handles the rare case where a reviewer must see a real value.

Full detail in `platform.md`.

---

## 7. Where to go next

- **`stage-1.md`** — the nine phases of Stage 1 in detail, with a demo you can
  run yourself at the end.
- **`../plans/BUILD-STATUS.md`** — the running checklist of what's done, what's
  pending, and the five open questions waiting on you.
- **`../plans/stage-1-blueprint.md`** — the technical version, for building from.
- **`../research/stage-1-capture-layer.md`** — the receipts: what was checked,
  what competitors do, and the arguments for and against each decision.
