# Pulse — Architecture Plan
### (A metadata-based process discovery watcher — no OCR, no video)

## What this is, in one paragraph

Today, a tool like SKAN sits on someone's computer, records their screen
continuously, and later uses OCR (reading pixels like a human eye would) to
figure out what happened in a chunk of that recording, turning it into an
8-15 minute clip that represents one task. Pulse does the same *job* —
watch quietly, figure out the real process — but senses the world
differently: instead of watching pixels, it listens to the structured
signals every application already produces internally (clicks, typed
values, selected text, the actual field content on screen) the same way a
screen reader does for accessibility. Over many people doing the same task
many times, across multiple applications, the repeating pattern underneath
all that noise *is* the process. That's the field of process mining —
established science — applied through a different sensing method than
anyone else in our space is using.

This plan has seven stages, in the correct real-world order: capture first,
then figure out where one task begins and ends, then figure out how
different applications relate to each other within that one task, then find
the repeating pattern across many tasks, then label what kind of process it
is, then produce the final output, then optionally keep it current over
time.

---

## Stage 0 — Get the concept rock solid

**Purpose:** Make sure anyone reading this understands why it's possible
before they ask "how would this even work?"

**Steps:**
1. State the core shift plainly: instead of a video, we keep a diary that
   writes itself — every click, every typed value, every piece of text a
   person selects or sees on screen, with a timestamp.
2. Name the field this sits inside: process mining — turning a log of real
   actions into the real step-by-step process people actually follow,
   including the shortcuts and exceptions nobody wrote down.
3. State the difference from SKAN clearly: we read the application's own
   internal structure directly (the same text a screen-reader accessibility
   tool already reads) instead of reading the screen visually. No OCR, no
   sensitivity to how something looks.
4. Write down the real questions this plan has to answer:
   - Can we capture everything meaningful a person does, continuously,
     without watching the screen?
   - Can we tell where one task instance starts and ends inside that
     nonstop stream?
   - When a task spans multiple applications, can we tell how information
     actually moved between them?
   - Can we turn many people's task instances into one clear, repeatable
     process?
   - Can we tell what *kind* of process it is (QA/QC vs. something else)
     just from the pattern?

---

## Stage 1 — Continuous, wide-net capture (the "listening" layer)

**Purpose:** Capture everything meaningful, all the time, across every
application in view — not a short fixed list, a genuinely wide net.

**Steps:**
1. Capture every meaningful action as it happens: clicks, typed values,
   button presses, opening a new screen or tab, switching between
   applications or windows.
2. Also capture **text selection and highlighting** as its own distinct
   event — when someone highlights a value with their mouse, that is a
   strong, deliberate signal, separate from and more reliable than just
   tracking where the mouse moved.
3. Also capture **copy and paste** as linked events, storing the actual
   value that was copied and where it was later pasted.
4. Also capture the **actual text content visible on screen** at the moment
   of each action — pulled from the application's own internal structure
   (a browser's DOM, or Windows' accessibility layer), not from a picture of
   the screen. This means we can often know what a field displayed even if
   the person never clicked or copied it.
5. Tag every captured event with which application and window it happened
   in, and the exact time, so events from different applications can later
   be placed on one shared timeline per person, per session.
6. Checkpoint: for one person working continuously across multiple
   applications, we can produce one unbroken, ordered timeline of everything
   meaningful they did, with no gaps and no reliance on watching the screen.

---

## Stage 2 — Finding where one task starts and ends (episode segmentation)

**Purpose:** A continuous stream by itself doesn't know where "one QA/QC
review" begins and ends — this is the step that turns SKAN's continuous
recording into its 8-15 minute clip, done here through signals instead of a
human choosing a video segment.

**Steps:**
1. Look for natural boundary signals in the continuous timeline — for
   example, a long gap of inactivity, or a brand-new identifier (like a
   loan ID or ECN number) appearing on screen for the first time, which
   often marks the start of a new case.
2. Look for natural end signals — for example, a final action like
   "Approve," "Reject," or "Submit," or the identifier disappearing from
   view as the person moves to a different case.
3. Group everything between a detected start and end signal into one
   "episode" — one complete instance of the person handling one case,
   however many applications it touched.
4. Checkpoint: given one person's full day of activity, we can correctly
   slice it into distinct episodes, each representing one handled case,
   without anyone manually marking where each one begins or ends.

---

## Stage 3 — Connecting the dots across applications (within one episode)

**Purpose:** This directly answers "how do we know what he saw and did with
it, when it moved across applications?"

**Steps:**
1. Within one episode, look for identifier matches — the same value (a loan
   ID, ECN number, task ID) appearing in more than one application. This is
   the anchor that proves two applications were part of the same case.
2. Rank the evidence for *how* that value moved, from strongest to weakest:
   - An explicit copy in one app followed by a paste in another — direct
     proof.
   - A text selection/highlight of that value, even without a copy — strong
     signal of deliberate attention.
   - The value simply being visible on screen (captured via Stage 1's
     field-content capture) shortly before it's typed elsewhere — a
     reasonable inference, not proof.
   - The same value appearing in both apps with no other evidence linking
     them, purely by timing closeness — the weakest signal, used only to
     support a pattern seen repeatedly across many episodes, never trusted
     alone.
3. Accept openly that some episodes will have real gaps — moments where a
   person acted on something we have no digital trace of (they remembered
   it, or acted outside any system we can see). Don't try to force a link
   where none exists in the data.
4. Checkpoint: for one episode spanning two or more applications, we can
   produce a single connected sequence of steps — "opened record in App A,
   read loan ID, opened App B, searched using that same loan ID, reviewed
   result" — built from real evidence, with honest gaps marked as gaps
   rather than guessed at.

---

## Stage 4 — Finding the real process across many episodes (the mining step)

**Purpose:** One connected episode tells us what one person did once. This
stage finds the process that holds true across many people, many times.

**Steps:**
1. Group episodes that appear to belong to the same kind of task (similar
   applications touched, similar identifiers involved).
2. Across many episodes in the same group, find which steps appear in
   nearly every one (the backbone of the real process) versus which steps
   only sometimes appear (optional or conditional) versus which appear so
   rarely they're likely one-off mistakes, not part of the real process.
3. Turn that backbone into a clear step-by-step map, including where it
   branches, built entirely from evidence across many real episodes — not
   from any one person's memory of "how it's supposed to work."
4. Note for the later investigation phase: this kind of pattern-finding
   already has proven, established methods in process-mining research (for
   example, the Alpha algorithm, Heuristic Mining, Inductive Mining), with
   existing open-source tools covering parts of it. The job later is to
   investigate which existing method fits our cross-application data best,
   not to invent this math from nothing.
5. Checkpoint: given a stack of episodes for one task, we can produce one
   clear map of the real process that most of those episodes actually
   follow, including how it flows across applications.

---

## Stage 5 — Telling what kind of process it is (QA/QC or something else)

**Purpose:** The map from Stage 4 shows the shape of the process, not its
meaning. This stage adds the meaning.

**Steps:**
1. Use the shape itself as one clue — a process that opens a record,
   compares information, and ends in an approve/reject or pass/fail
   decision has a recognizable shape typical of a QA/QC review.
2. Use the actual on-screen language captured in Stage 1 as a second clue —
   field names, button labels, and screen titles like "Approve," "Reviewer
   Comments," or "Compliance Check" are strong hints toward the process
   type, independent of the shape.
3. Combine both clues into a plain-language best guess — for example, "this
   process opens a record, checks it against criteria, and ends in an
   approve/reject decision, matching the shape of a QA/QC review" — with a
   person confirming or correcting the first several guesses, so trust is
   earned before the label is relied on unsupervised.
4. Checkpoint: given a brand-new mined process it hasn't seen before, it can
   correctly propose "this looks like a QA/QC process" (or correctly say
   "this looks like something else") often enough that a human only needs
   to glance and confirm, not diagnose from scratch.

---

## Stage 6 — Producing the final output

**Purpose:** Package everything learned into one clear, structured
description of the process — the actual deliverable this tool exists to
produce.

**Steps:**
1. For each discovered process, produce a structured writeup containing:
   which applications it touches, the backbone steps in order, the
   cross-application links from Stage 3, the branches and exceptions noticed
   in Stage 4, and the process-type label from Stage 5.
2. Keep this in a clear, well-organized written format — not a video, not a
   vague summary — genuinely understandable to a person who has never seen
   the task performed.
3. State plainly: what happens after this (turning the description into
   running automation, agents, or an ingestion pipeline) is a separate
   concern and is intentionally out of scope here. This tool's job ends at
   producing a clear, trustworthy description of the real process.
4. Checkpoint: someone who has never seen the task performed can read this
   output and understand exactly what the process is, what it's for, and
   where it varies — with real confidence, built from real data.

---

## Stage 7 — Keeping it current over time (future extension, optional for v1)

**Purpose:** Because capture is continuous rather than a one-time recording,
we're positioned to notice when a real-world process quietly changes.

**Steps:**
1. Keep collecting new episodes after a process has already been mined once.
2. Periodically check whether new episodes still match the previously mined
   map, or whether the real process has shifted.
3. If a meaningful shift is detected, flag it for human review rather than
   silently trusting either the old or new version.

---

## What comes next (honest next step, not part of this plan)

Once this plan is agreed on, the next phase is investigation, not
construction: for each stage, check what already exists in the open-source
world (capture techniques, process-mining libraries and algorithms,
labeling approaches) that can be reused or adapted, and design something
fully new only where nothing suitable already exists. Stage 3 (cross-
application linking through identifier and copy/paste evidence) is the
piece least likely to already exist off-the-shelf, since most process-mining
tools assume a single system's event log rather than signals scattered
across several unrelated applications — that is the most promising place to
look for a genuinely new, defensible invention.
