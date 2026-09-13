# Stage 1 — Listen to everything

*Plain-English walkthrough. The technical version is `../plans/stage-1-blueprint.md`;
the evidence behind every choice is `../research/stage-1-capture-layer.md`.*

---

## What this stage does

Stage 1 builds a program that sits quietly on a computer and writes down
everything meaningful the person does — across every application — into one
long, ordered list. Not a video. A diary.

It records **what** happened (clicked, typed, highlighted, copied, pasted,
switched apps), **where** it happened (which app, which window, which specific
box on screen), **what content was involved** (the value typed or copied, and
what the nearby fields were displaying at that moment), and **exactly when**.

That's it. Stage 1 does no thinking. It doesn't know what a "case" is, doesn't
know which app matters, doesn't try to be clever. Its only job is to miss
nothing and lie about nothing.

> **Why that matters more than it sounds:** every later stage inherits Stage 1's
> mistakes and amplifies them. If capture misses 20% of what happened, Stage 4
> doesn't produce a map that's 80% right — it produces a map that's confidently
> wrong, because the missing 20% is exactly where the exceptions live.

---

## The picture

Three separate listeners feed one shared diary:

```
   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │  DESKTOP APPS    │   │    BROWSER       │   │   CLIPBOARD      │
   │  LoanDesk, Excel │   │  Chrome / Edge   │   │  (whole machine) │
   │  Outlook, …      │   │  DocVault, …     │   │                  │
   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
            │                      │                      │
      listens via            listens via            listens via
      Windows                a browser              Windows
      accessibility          extension              clipboard
      (Phases 1.2-1.5)       (Phase 1.6)            (Phase 1.5)
            │                      │                      │
            └──────────┬───────────┴──────────┬───────────┘
                       ▼                      ▼
            ┌────────────────────────────────────────┐
            │  PUT IT IN ORDER    (Phase 1.7)        │
            │  Three sources, three clocks, arriving │
            │  out of order → one true sequence      │
            └───────────────────┬────────────────────┘
                                ▼
            ┌────────────────────────────────────────┐
            │  CLEAN IT        (Phase 1.8)           │
            │  Block sensitive apps, skip passwords, │
            │  redact personal data                  │
            └───────────────────┬────────────────────┘
                                ▼
            ┌────────────────────────────────────────┐
            │  THE DIARY       (Phase 1.1)           │
            │  One local database file               │
            └───────────────────┬────────────────────┘
                                ▼
                        handed to STAGE 2
```

---

## What one diary entry actually looks like

This is Sam highlighting the loan ID in LoanDesk — step 2 of the story. One
event, written to the diary:

```json
{
  "event_type":  "text_selected",
  "producer":    "desktop",
  "time":        "09:02:11.480",

  "app":     { "process_name": "LoanDesk.exe" },
  "window":  { "title": "Loan Review — LN-48213" },
  "element": { "name": "Loan ID", "automation_id": "txtLoanId",
               "control_type": "Edit" },

  "content": { "value": "LN-48213" },

  "context": [
    { "label": "Applicant",       "value": "J. Whitfield"    },
    { "label": "Declared income", "value": "$92,000"         },
    { "label": "Amount",          "value": "$240,000"        },
    { "label": "Status",          "value": "Pending review"  }
  ]
}
```

Two things to notice, because they're the whole point of this design:

1. **`content`** — we know the exact value Sam highlighted. Not "Sam highlighted
   something in the top-left region." The actual string.
2. **`context`** — we captured the declared income of **$92,000** even though
   **Sam never clicked it, never copied it, never touched it.** It was simply on
   screen, and the application told us. That's what makes Stage 3 possible: later,
   when Sam types "92,000" into a comment or compares it to DocVault's "84,000",
   we can prove they had seen it.

A screenshot-based tool would have to OCR that number off a picture and hope.

---

## The nine phases

Each is a sitting's worth of work. They're ordered so each one has something
real to test as soon as it lands.

> ⚠️ **Safety rule baked into the plan:** phases 1.2 to 1.7 capture content with
> no privacy filtering yet. Until Phase 1.8 is finished and passes its test, this
> only ever runs against **fake practice apps we build ourselves and a throwaway
> browser profile** — never on a real person's machine with real data. Not
> negotiable.

---

### Phase 1.1 — The diary itself

**In one sentence:** decide the exact shape of a diary entry, and build the file
it gets written into.

**What we're building.** A written-down definition of what an event is (the
fields in that JSON example above), and a local database to hold them.

**What we're using, and why.**

- **SQLite** for the database. It's a single file, it's on every machine
  already, it survives the laptop being unplugged mid-write, and you can read
  yesterday's events while today's are still being written.
  - *Not a plain text log file:* you'd have to load the whole day into memory to
    ask it anything, and a crash mid-write corrupts the last line.
  - *Not a big server database:* this runs on a laptop. Anything needing a
    service to be installed and running is the wrong shape.
- **JSON Schema** to define an event. Three different listeners — two written in
  Python, one in JavaScript inside the browser — all have to agree on the format.
  A schema file is the one thing both languages can check themselves against.
- **We do *not* use XES or OCEL here** (the standard process-mining file
  formats), even though we'll want them later. Both formats require you to say
  which "case" each event belongs to — and **figuring out what a case is, is
  Stage 2's entire job.** Forcing that decision at capture time would throw away
  the very evidence Stage 2 needs. We convert later, once Stage 2 has decided.

**What exists when it's done.** A schema file, a database module, and
`pulse.db` appearing on disk.

**How you test it yourself.**
Nothing visible happens yet — this is plumbing. The tests are automated:
- Write 10,000 fake events, read them back, confirm all 10,000 come back
  identical and in the same order.
- Feed it 20 deliberately broken events; all 20 must be rejected, none written.
- Kill the program mid-write with Task Manager, reopen the file. It must open
  cleanly and have lost at most the last batch.

---

### Phase 1.2 — Watch the clicks and the window switches

**In one sentence:** know *that* something happened and *which application* it
happened in.

**What we're building.** The part that notices clicks, keyboard shortcuts,
switching between windows, apps opening and closing, and the person going idle.

**What we're using, and why.**

- **Windows low-level input hooks** — the official way to be told about every
  click and keypress machine-wide.
- **`SetWinEventHook`** — the official way Windows tells you "the person just
  switched to a different window." Crucially we use the *out-of-process* version,
  which does **not** require injecting our code into other applications. The
  injecting version would work too, and would get us instantly rejected by any
  corporate security review.

**The decision worth understanding here: we do not record what you type.**

The obvious approach is to log keystrokes. We're deliberately not doing that:

- A keylogger captures passwords, and there's no way to know a box was a password
  box *before* you've already recorded the characters.
- It's also the single feature most likely to get the whole tool banned by a
  works council or security team.

Instead we record only **which shortcut** was pressed (Ctrl+C, Tab, Enter) and
the *rhythm* of typing — never the characters. The actual typed values come from
Phase 1.3, which asks the application "what does this box contain now?" and gets
back both the value **and** whether it's a password box (in which case we skip it).

This is a better trade in both directions: safer, *and* better data — because we
get the finished value attached to the field it belongs to, instead of a stream
of loose characters we'd have to reassemble.

**Real example.** Sam switches from LoanDesk to Chrome:
`window_activated — Chrome — 09:02:15`, and every event after that is correctly
attributed to Chrome rather than still being credited to LoanDesk.

**What exists when it's done.** A program you can leave running that fills the
diary with clicks and app switches. Plus **two fake practice apps** we build
ourselves ("System A" and "System B") with known, fixed layouts — these become
the ruler we measure everything against for the rest of Stage 1.

**How you test it yourself.**
1. Start the capture program.
2. Open Notepad, click around, type the word `ZZQXSENTINEL`, press Ctrl+C.
3. Switch to File Explorer. Switch back. Close Notepad.
4. Open the diary and check:
   - Every app switch you made is there — **all of them**. A missed switch
     poisons the attribution of everything after it, so this one has to be 100%.
   - Your clicks are there with the right app name next to them.
   - **Search the whole database for `ZZQXSENTINEL`. It must not exist.**
     That's the proof the no-keylogging rule is actually being honoured, not
     just described in a document.

---

### Phase 1.3 — Read what's on the screen *(the heart of Stage 1)*

**In one sentence:** for every action, find out exactly which box on screen was
involved, and what the surrounding boxes were displaying.

This is the phase that makes Pulse different from a click counter.

**What we're building.** The listener that asks Windows' accessibility
layer — the same one screen readers use — "what is this thing the person just
clicked, and what's around it?"

**What we're using, and why.**

- **Microsoft UI Automation (UIA)** — the accessibility system built into
  Windows. Every well-behaved app exposes its controls through it.
- We talk to it **directly**, rather than through convenience libraries like
  `pywinauto` or `uiautomation`. Reason: those libraries are built for *driving*
  apps (click this button, fill this form), and their convenient
  "just read the property" style triggers a separate slow cross-application call
  **per property**. Microsoft's own documentation flags this as the main
  performance trap. We ask for everything we need in **one batched request**
  instead.
- **We subscribe to notifications rather than polling.** We never sit in a loop
  asking "changed yet? changed yet?" — Windows tells us when something changes.

**Two deliberate limits, both important:**

1. **The snapshot is bounded.** When Sam clicks something, we grab the clicked
   control, its label, and up to ~12 nearby text-bearing controls — at most 3
   levels deep, 512 characters each, and **if it takes longer than 120ms we stop
   and mark the entry as truncated.** Without a hard limit, one complicated
   application (Excel with a big sheet open) would hang the whole capture.
2. **When we can't see, we say so.** Some apps expose nothing useful — custom
   graphics, games, remote desktop windows. When that happens we write an entry
   that says *"something happened here and we couldn't read it."* We never
   quietly skip it. Stage 3 depends on knowing the difference between
   "nothing happened" and "we went deaf."

**Real example.** Sam clicks the "Documents" tab in LoanDesk. We record: the
clicked control is a tab called "Documents", and on screen at that moment were
`Applicant: J. Whitfield`, `Declared income: $92,000`, `Loan ID: LN-48213`.
Sam never touched those fields. We have them anyway.

**What exists when it's done.** Every event in the diary now carries a proper
element identity and a snapshot of nearby on-screen text.

**How you test it yourself.**
1. Open the practice app. It has 20 controls, all documented.
2. Click each one. Check the diary named the right control every time — 20 out
   of 20.
3. **The real test:** type known values into five fields in the practice app —
   say `$92,000` in the income box. Then click a **completely unrelated button**.
   Open that button-click entry in the diary. **All five values should be sitting
   in its `context` list** — even though you never clicked those fields. If that
   works, the core claim of Stage 1 is real. If it doesn't, it isn't.
4. Type a sentinel into the practice app's password box. Search the database.
   It must not be there.
5. **The speed gate:** run a 5-minute scripted workload including a real heavy
   app (Excel or Outlook). 95% of snapshots must complete in under 150
   milliseconds, with zero missed window switches. If Python can't hit that, the
   plan says to rewrite this one component in C# (using a library called FlaUI)
   and keep everything else in Python. That fallback is already written down so
   nobody has to panic and redesign on the spot.

---

### Phase 1.4 — Notice what people highlight

**In one sentence:** when someone drags their mouse across a value to highlight
it, record that as its own event.

**Why this deserves its own phase.** Highlighting is *deliberate*. Nobody
highlights something by accident. It's one of the strongest available signals
that a person was paying attention to a specific value — much stronger than
"the mouse passed over it." In Stage 3, a highlight is the second-best evidence
that a value moved between applications, beaten only by an actual copy/paste.

**What we're using, and why.** UIA has a built-in "the text selection changed"
notification that gives us both the selected text *and* which control it came
from. Where a control doesn't support it, we fall back to watching for a
mouse-drag inside a text area — but we **tag those as guessed** (`inferred`)
rather than observed, so Stage 3 can weigh them lower. Honest labelling here is
what keeps the evidence ranking meaningful later.

One practical wrinkle: dragging across text fires dozens of "selection changed"
notifications, one per character. We wait ~300ms for the selection to settle and
record one event with the final result.

**Real example.** Sam drags across `LN-48213`. One entry:
`text_selected — "LN-48213" — from the "Loan ID" box in LoanDesk`.

**How you test it yourself.**
1. In Notepad, WordPad, Excel and the practice app, highlight 10 known phrases
   with the mouse and 10 with Shift+arrow keys.
2. At least 18 of 20 should be captured **with the exact text** in each app. Any
   app that scores worse goes on a written "here's what we can't see" list rather
   than being quietly ignored.
3. Do one slow 3-second drag. It must produce **exactly one** entry, not thirty.

---

### Phase 1.5 — Copy and paste, as a linked pair

**In one sentence:** when someone copies something and pastes it somewhere else,
record both ends *and the fact that they're the same act*.

**Why this is the most valuable phase in Stage 1.** A copy in App A followed by
a paste in App B is **proof** — not inference — that those two applications were
part of the same piece of work. It's the top of Stage 3's evidence ladder.

It's also where we part company with the competition. **Paxray detects that you
pressed Ctrl+C but deliberately never records what you copied.** Which means
they can never do this linking. We keep the value. That's the trade: more
capability, more privacy responsibility (which Phase 1.8 then has to earn).

**What we're using, and why.**

- **Windows' clipboard listener** — Windows will tell us when the clipboard
  changes. We don't poll it. Polling would burn CPU forever and still miss fast
  copies.
- **The clipboard sequence number** — Windows keeps a counter that ticks up every
  time the clipboard changes. This is what makes pairing reliable: we match a
  paste to the copy whose number was current at the time, rather than guessing
  "probably the most recent one."
- **Detecting paste is harder** — Windows doesn't announce pastes. We combine two
  clues: the Ctrl+V shortcut, and a field suddenly containing the clipboard's
  contents. We record **how confident** we are, based on which clues fired.

**Real example.** Sam copies `LN-48213` in LoanDesk at 09:02:14 and pastes it
into DocVault's search box at 09:02:19. Two diary entries, joined by a shared
pair ID, with confidence `shortcut_and_value_match` — the highest level.

**How you test it yourself.**
Do 30 copy/pastes, including these three tricky ones:
1. **Copy, copy again, then paste.** It must pair to the **second** copy.
2. **Copy once, then paste three times.** Three pastes, all pointing back to the
   one copy.
3. **Copy in the practice app, switch to the browser, paste there.** It must pair
   *across the application boundary* — this is the one that matters.

Also copy a value with an emoji in it, one with a line break, and one that's
4,000 characters long. All three should come back byte-for-byte identical.

---

### Phase 1.6 — The browser

**In one sentence:** do everything from phases 1.2–1.5 again, but inside Chrome,
where most of the work actually happens.

**Why the browser needs its own approach.** You'd think we could point the same
Windows accessibility listener at Chrome and be done. We can't — and the reason
is the most useful thing the research turned up:

> Chrome only builds its accessibility information **when something asks for it**.
> Forcing it on makes Chrome continuously rebuild that information across every
> tab and process. Blue Prism's own integration guide warns it "can result in
> high CPU overhead," and Salesforce has a published support article about pages
> becoming *unresponsive* because of it.

A monitoring tool that makes every browser tab sluggish gets uninstalled in week
one. So: **a browser extension instead.** Inside the browser, all this
information is already there for free — no accessibility mode, no CPU penalty.

*We also rejected using Chrome's debugging protocol*, which is the other obvious
route. It either shows a permanent "Chrome is being debugged" banner, or requires
leaving a debugging port open — which on an employee's laptop is a genuine
security hole, since anything that reaches that port can drive their logged-in
sessions.

**What we're building.** A Chrome extension that captures clicks, typing,
highlighting, copy/paste, form field values, and page navigation — including
navigation *inside* modern web apps that never actually reload the page — and
sends it all to the same diary via a small local connector program.

**One known unknown, flagged honestly.** Modern Chrome extensions get shut down
after about 30 seconds of doing nothing, which is awkward for something meant to
listen all day. There's a well-known technique for keeping the connection alive
that I believe works but **did not verify** — so this phase includes testing it
for real, and two documented fallbacks if it doesn't hold.

**Real example.** Sam pastes `LN-48213` into DocVault's search box. We capture
it as a paste into a field whose accessible label is "Search loan ID", on the
page `docvault.internal/search`.

**How you test it yourself.**
1. **The big one:** copy a value in the desktop practice app → paste it into a
   browser page. Then do the reverse. **Both directions must show up as a
   correctly paired copy/paste across the two listeners.** This is the single
   most important test in all of Stage 1 — it's the thing Stage 3 is built on,
   and the first moment we find out whether the whole architecture is real.
2. Leave the browser completely alone for 10 minutes, then click something. It
   must be captured. (This is the proof the extension didn't quietly die.)
3. Open `chrome://accessibility` and confirm accessibility mode is **off** —
   proof we didn't accidentally reintroduce the very CPU cost we designed around.
4. Type into a password field on a test page. It must not appear in the diary.

---

### Phase 1.7 — Put it all in the right order

**In one sentence:** three listeners, arriving at different speeds with different
clocks, become one true sequence.

**Why this isn't as trivial as it sounds.** The desktop listener, the browser
extension, and the clipboard watcher all report independently. The browser sends
in batches. Windows delivers some notifications late on purpose. So events
**arrive out of order**. And you can't just sort by the clock, because the
computer's clock can jump — daylight saving, or a time sync correction that moves
it *backwards* mid-recording.

**What we're using, and why.**

- **A stopwatch, not a wall clock.** For ordering we use a counter that only ever
  goes up and can't be adjusted. The wall clock is kept too, but only for human
  reading.
- **The browser's clock gets calibrated** against ours with a regular ping-pong,
  the same basic trick internet time sync uses.
- **A small waiting room.** Events wait ~2 seconds before their order is
  finalised, so stragglers can slot into their correct place. Anything arriving
  later than that is still kept — flagged as late, never dropped.

**The most valuable output of this phase: the gap ledger.**

For every quiet period in the day, we write down *which kind of quiet it was*:

| Kind | What it means | What Stage 2 should do with it |
|---|---|---|
| `idle` | Sam genuinely wasn't at the computer | A likely boundary between two cases |
| `blind` | Sam **was** working, but in something we can't read | **Missing evidence — not a boundary** |
| `host_down` | Our program wasn't running | Ignore this stretch entirely |

Getting this distinction right is worth more than anything else in this phase.
If `blind` gets confused with `idle`, Stage 2 will confidently declare a new case
started every time Sam uses an app we can't see into. That's not a small bug —
it's a wrong answer that *looks* like a right answer, which is the worst kind.

**How you test it yourself.**
1. Alternate between the desktop app and the browser every second for five
   minutes. Every cross-app pair more than half a second apart must be in the
   correct order — 100%, no exceptions.
2. **Change your system clock forward by 10 minutes while it's recording.** The
   event order must be completely unaffected. That's the proof we're using the
   stopwatch and not the wall clock.
3. Produce all three kinds of gap deliberately: walk away for 3 minutes (`idle`),
   work for 2 minutes inside something unreadable like a remote desktop window
   (`blind`), and kill the capture program for 2 minutes (`host_down`). All three
   must be classified correctly.

---

### Phase 1.8 — Make it safe to run on a real person

**In one sentence:** the phase that decides whether this tool can ever leave the
lab.

**What we're building.**

1. **Blocklists that work *before* capture, not after.** Password managers,
   banking sites, personal email, HR systems: default to capturing **nothing** but
   "this app was open for 4 minutes." Paxray ships exactly this; it's table stakes,
   not innovation.
2. **Different rules for different kinds of text.** This distinction is the clever
   part of the design:
   - **Screen furniture** — button labels, column headings, screen titles
     ("Approve", "Reviewer Comments"). This is *not personal data*, and Stage 5
     needs it to work out what kind of process this is. **Keep it as-is.**
   - **Identifiers** — loan IDs, ticket numbers. Handled per your decision below.
   - **Free text** — comments, notes. Run through redaction, keep the cleaned
     version.
   - **Sensitive** — never kept at all.
3. **PII redaction** using **Microsoft Presidio**, an open-source tool that finds
   names, card numbers, national ID numbers, emails and phone numbers in text. We
   reuse it rather than writing our own — it's mature, well-maintained, and
   pattern-matching for personal data is a solved problem we'd do worse.
4. **A way to delete.** `purge(person, from, to)` that genuinely removes
   everything, including from exported files. Built now, while the system is
   simple — retrofitting deletion later is painful.
5. **A viewer** so the person being recorded can see exactly what's been captured
   about them, and a pause button that actually works.

**The decision that's waiting for you.**

For identifiers like `LN-48213`, there are two options:

| | Keep the real value | Keep a fingerprint of it |
|---|---|---|
| What's stored | `LN-48213` | `a7f3e9...` (one-way, can't be reversed) |
| Can Stage 3 still link apps? | Yes | **Yes** — same value always gives the same fingerprint |
| Can we match `LN-00123` to a bare `00123`? | Yes | **No** — partial matches break |
| Is the final Stage 6 report readable? | Yes | Much less so |
| What you tell a security review | "We store business identifiers" | "We store no recoverable content" |

The plan **writes both** — the fingerprint always goes in the diary, and the real
value goes into a separate locked vault only if you switch it on. So you can
decide later, or decide differently per customer, without any rework.

**But it has to be decided before this ever runs on real data**, because it
changes what you're asking a security reviewer to approve.

**How you test it yourself.**
1. Put a banking site and a password manager on the blocklist. Use both for two
   minutes. The diary should contain **zero** content from either — but should
   still show that the apps were open.
2. Fill a practice form with 50 **fake** personal details. At least 95% must be
   redacted, and **100%** of the structured high-risk ones (card numbers,
   national ID numbers). Every miss gets written up, not shrugged off.
3. Turn the fingerprint-only mode on. Copy an ID in App A, type it in App B.
   The fingerprints must match — **and the real value must appear nowhere.**
   That's the proof the privacy-preserving mode still supports Stage 3.
4. Run a purge. Check the database, the vault, and the exported files. All clean.

---

### Phase 1.9 — The full dress rehearsal

**In one sentence:** run Sam's actual workflow for 30 minutes and measure how
much we got right.

**What we do.** Write a realistic 30-minute QA/QC script — several loan reviews,
including a phone-call interruption, a mistake and correction, and one case
abandoned halfway. Someone records independently what they actually did. Then we
run capture and compare.

The messy variations matter more than the clean run. Interruptions and
corrections are exactly what Stages 2 and 4 exist to handle, so Stage 1 has to
survive them.

**What "passing" means:**

| What we measure | Must be at least |
|---|---|
| Actions captured | 95% |
| Correct app attributed | 100% |
| Specific on-screen control identified | 90% |
| On-screen values captured | 85% |
| Copy/paste pairs matched across apps | 95% |
| Order correct (for actions >0.5s apart) | 100% |
| Gaps we can't explain | **zero** |
| CPU used | under 5% of one core |
| Storage | under 100 MB per person per day |

If any number misses, we diagnose it before starting Stage 2. **No "close
enough."** As noted at the top: a 95%-complete diary doesn't give you a
95%-correct process map.

**Also produced: a coverage map.** A written, honest list of which real
applications we can see into properly, which we half-see, and which we're blind
to. Stage 3 and Stage 4 both need to know where the holes are.

---

## What you'll have when Stage 1 is done

✅ A program you can leave running all day that produces an honest, ordered,
searchable diary of someone's work across every application — with the actual
values involved, and what was on screen — using no video and no OCR.

✅ A recorded, real answer to "does this actually work?" — with numbers, on real
applications, including a written list of where it fails.

✅ A sample dataset from the dress rehearsal, which becomes Stage 2's starting
material.

❌ **It still won't know what a "case" is.** The diary is one long undifferentiated
stream. "These 47 events were one loan review" is Stage 2.

❌ **It won't know the apps are related.** It records that Sam copied `LN-48213`
in LoanDesk and pasted it in DocVault, but it draws no conclusion from that.
Concluding is Stage 3.

❌ **It won't know what the process is.** That's Stages 4, 5 and 6.

Stage 1 is the microphone. It isn't the transcript, and it certainly isn't the
analysis.

---

## The demo you can run yourself, once Stage 1 is finished

About ten minutes, and it exercises the entire stage:

1. Start the capture program. Open the diary viewer alongside it.
2. Open the practice app ("System A"). Note the loan ID it's showing.
3. **Highlight** that ID with your mouse. **Copy** it.
4. Switch to Chrome. Open the practice web page. **Paste** the ID into search.
5. Read a number off the results page. Switch to Excel. Type something.
6. Switch back to System A. Click **Approve**. Type a comment.
7. **Walk away for three minutes.** Come back.
8. Do one more, shorter case with a different ID.
9. Stop the capture. Open the diary.

**What you should see:**

- Every app switch, in the right order, across all three applications.
- Your highlight, with the exact text you highlighted.
- The copy and the paste, **joined to each other**, with the real value,
  **across the desktop-to-browser boundary**.
- On the Approve click, a `context` list containing values that were on screen —
  including ones you never clicked.
- Your three-minute break showing up as an `idle` gap, not as a mysterious hole.
- No passwords. Nothing from any blocklisted app. No raw keystrokes anywhere.

If all of that is there, Stage 1 is real and Stage 2 has something to work with.

---

## Worth debating

Things I'd push back on if I were reviewing this. Pick any of them apart.

1. **"Is Stage 1 even worth building, if Paxray and KYP.ai already sell it?"**
   My answer: yes, but not as the invention — as the foundation. The distinctive
   part (keeping the copied value, and linking apps with it) *needs* this
   foundation, and no one will license theirs to us to build on. But if you were
   hoping Stage 1 itself was the defensible piece, the research says otherwise.

2. **"Why nine phases? Isn't that over-engineering a logger?"**
   Fair challenge. My reasoning: phases 1.1, 1.2, 1.5 and 1.6 are unavoidable.
   1.3 is the actual product differentiator. 1.7 looks like plumbing but the gap
   ledger is what stops Stage 2 producing confident nonsense. 1.8 is what makes
   it deployable at all. If you wanted to compress, **1.4 could fold into 1.3** —
   that's the one I'd merge.

3. **"Windows and Chrome only?"** My call, not the architecture's. Mac and Linux
   have equivalent systems, but every phase above would need a parallel build.
   Roughly doubles Stage 1 if you need it.

4. **"What if the target customer runs everything in Citrix?"** Then Stage 1 sees
   almost nothing and the project premise needs rethinking. Worth checking who
   the first real customer is *before* building, not after.

5. **The fingerprint-vs-real-value question** from Phase 1.8. Genuinely yours to
   decide — it's a business and legal call as much as a technical one.

6. **"Can't we skip the practice apps and just test on real software?"**
   I'd resist. Without an app whose exact layout we control, every test becomes
   "looks about right," and "looks about right" is how you end up with an 80%
   capture rate you don't discover until Stage 4 produces a map that's wrong in a
   way nobody can explain.
