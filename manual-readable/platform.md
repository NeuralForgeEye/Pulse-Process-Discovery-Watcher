# The platform — decisions that apply to every stage

*Plain-English walkthrough. Technical version: `../plans/platform-architecture.md`.
Evidence: `../research/deployment-sensing-and-data-controls.md`.*

---

## Why this document exists

Four things cut across all seven stages: **how we sense**, **how we protect
data**, **where it runs**, and **how it moves between environments**. Writing
them into each stage seven times would guarantee they drift apart. They live
here.

---

## 1. What we learned about SKAN — and why it changed the plan

The original plan positioned Pulse as *"SKAN, but without the video."* Having
actually researched what SKAN does, that framing doesn't survive contact.

**What SKAN actually does:**

```
   Desktop agent               Gateway server               SKAN's cloud
   (watches screen,     →      INSIDE the customer's   →    (analysis)
    computer vision)           own network
                              ├ anonymisation
                              ├ pseudonymisation           only abstracted
                              └ redaction                  metadata leaves
```

Two things this tells us that the plan didn't anticipate:

**a) Their raw screenshots never leave the customer's building either.** They
didn't ignore the privacy problem — they engineered around it with an on-prem
gateway. So *"we don't store video"* is a much weaker pitch than assumed.

**b) They explicitly cover Citrix, VDI, mainframes, and "tools with no API or
event log."** That's their headline capability — and it's exactly where a
pure metadata approach goes blind. In regulated finance, a large share of QA/QC
work runs on precisely those surfaces.

So the honest position: **we can't win on privacy framing, and we'd lose badly
on coverage.** Hence the sensing decision below.

---

## 2. Tiered sensing — the decision

We don't pick one sensing method. We pick the **best available one per screen**,
and we always record which one we used.

```
  ┌──────────────────────────────────────────────────────────────┐
  │  TIER 1 — ACCESSIBILITY LAYER          EXACT                  │
  │  Native Windows apps. The app tells us the value.             │
  │  "Loan ID = LN-48213"  ← not a guess                          │
  ├──────────────────────────────────────────────────────────────┤
  │  TIER 2 — BROWSER DOM                  EXACT                  │
  │  Web apps. Value + the field's real label.                    │
  ├──────────────────────────────────────────────────────────────┤
  │  TIER 3 — COMPUTER VISION              INFERRED               │
  │  Citrix, VDI, mainframe, canvas apps.                         │
  │  Only used where nothing structural exists.                   │
  │  "Probably LN-48213 (confidence 0.91)"                        │
  └──────────────────────────────────────────────────────────────┘
```

**The rule that makes this honest:** every single captured value is stamped with
which tier produced it and how confident that tier was.

**And the rule we never relax:** *values of different provenance are never
silently merged.* If the accessibility layer says `LN-48213` and the vision tier
says `LN-4B213`, we record **both and flag the disagreement.** We do not pick
one, and we absolutely do not average them — an averaged value is a value nobody
ever saw.

**Why this matters more than it sounds.** Without provenance tagging, computer
vision's weaker performance on old mainframe screens would disappear inside a
single blended accuracy number, and every claim we make becomes unfalsifiable.
With it, we can say *"exact on modern apps, approximate on mainframe screens,
and here's which is which."* That's the difference between a measurement and a
marketing figure — and it's one of the four things that make Pulse distinctive.

**Arbitration:** if a structural sensor works on a screen, **we don't run vision
at all.** Vision costs orders of magnitude more compute for a worse answer.

**Stated honestly:** the vision tier **cannot be tested outside Wells Fargo's
environment** — the Citrix and mainframe screens it exists to read aren't
available on a development machine. It gets flagged as untested in every status
report and never demoed as proven until it's run against real surfaces.

---

## 3. Protecting the data

### The core move: hash at the moment of capture

Sensitive identifiers — loan IDs, ECNs, account numbers — are converted to a
**keyed one-way hash the instant they're captured**, using a key from the
internal Vault. Cleartext **never enters the pipeline at all.**

```
   Screen shows:  LN-48213
        │
        ▼  (in the capture agent, before anything is stored)
   normalise → "ln48213"
        │
        ▼  HMAC with Vault key
   a7f3e9c2...   ← this is what the pipeline sees, forever
```

**And nothing is lost for matching.** If the same ID appears in DocVault, it
produces the *same* hash — so Stage 3 can still prove the two apps were
connected. Equality still works; only readability is gone.

**Why this beats what I originally designed.** My first version wrote *both* a
hash and an encrypted real value, with a config flag. That kept a cleartext path
alive inside the pipeline — meaning the whole pipeline had to be trusted.
Hashing at capture means the pipeline never holds a real identifier, so the
security argument is **structural, not procedural.** Much stronger claim to take
into a security review.

### What we deliberately do NOT hash

**Button labels, screen titles, field names, column headings.**

These aren't personal data — and Stages 4 and 5 *must* read them. A system that
hashes button labels can't tell a QA review from a data-entry task and can't
produce a readable document. **Over-hashing is a real failure mode**, not a safe
default.

### The reversal path

Sometimes a human reviewer genuinely needs to see the real value behind a
flagged case. So there's a **separate, locked, fully audited vault** mapping
hash → real value — same pattern banks already use for card tokenization.

- Different service, different credentials, different network path
- Requires a named human, a stated reason, produces an audit record
- **Not reachable from the main pipeline**
- If it's being used routinely, something upstream is broken

### What this costs, honestly

You can't do fuzzy matching on hashes. `LN-48213` and `LN-4B213` (a typo) hash
to completely unrelated values. We recover the common cases by normalising
before hashing and by hashing the components separately — so a bare `48213` can
still match. But near-miss matching is genuinely gone.

**If real data shows that matters, we escalate it — we don't quietly put
cleartext back.**

---

## 4. Federated by default — with one deliberate exception

Even hashed data isn't pooled company-wide by default. Each business unit or
datacenter keeps its **own** data locally, and only **pattern-level summaries**
go to the centre.

**The exception is Stage 4's mining corpus** — see the governance flag below.

**A fortunate fit worth pointing out:** Stage 3's key mechanism needs to know
*"how often does the pathway `LoanDesk ID box → DocVault search box` get
proven?"* — which is a pair of one-way hashes and a number. **That's already a
pattern-level summary with no content in it.** So the thing that makes Pulse
distinctive happens to be the thing that federates cleanly.

That wasn't designed in. It's luck, and it shouldn't be assumed to hold for
everything else without checking each one.

**And the part that doesn't fit — now handled by a deliberate bet.** Stage 4's
process mining assumes one big pool of cases. Mining separately and merging the
*results* is a genuinely harder problem.

**Decision: Stage 4 is being built against a single pooled corpus of hashed
identifiers** — as a *working assumption*, not an approved design:

> ⚠️ **OPEN GOVERNANCE ITEM.** Stage 4 assumes pooling HMAC-hashed identifiers
> across business units is permitted. **Data governance and InfoSec have not
> confirmed this.** If they refuse, we fall back to the federated
> local-mine-then-merge approach — the candidate designs are already written and
> deliberately kept. Pooled mining is **not** final architecture until confirmed.

**Why bet rather than wait:** this is a conversation to have, not a problem to
solve. Blocking the most algorithmically mature part of the system on an
unanswered policy question would stall everything for no research gain.

**Three cheap things make the bet safe to lose:**

1. The corpus sits behind an interface, so swapping "pooled" for "federated" is
   a boundary change rather than a rewrite of every phase.
2. **The activity dictionary is shared and versioned from day one.** This is the
   one that really matters — if each business unit invented its own names for the
   same steps, their results could never be merged afterwards. Costs nothing now;
   impossible to retrofit cheaply.
3. Where two approaches are equally good, prefer the one that works on summed
   counts rather than individual cases.

**If governance says no**, phases 4.4, 4.5 and 4.7 would need rework; 4.3 would
be unaffected. Known in advance rather than discovered.

---

## 5. Build once, move by config

Everything external — storage, secrets, sensing, audit — sits behind an
interface with two implementations:

| What | On your machine now | At Wells Fargo later |
|---|---|---|
| Database | Local SQLite file | Internal database |
| Secrets | Local encrypted file | Internal Vault |
| Sensing | Accessibility + browser | Same, plus vision tier |
| Reversal vault | Local encrypted store | Internal tokenization service |
| Audit log | Local file | Internal audit pipeline |

**No business logic knows which one it's talking to.** If a stage's code
mentions SQLite or a file path, that's a bug.

**One config file** says where everything points. Moving environments is an edit
to that file — not a rewrite, not a branch, not a port.

**Containerised from the start** (Docker Compose locally), so the local shape
matches the eventual clustered multi-datacenter deployment instead of needing
the classic "script on my laptop → real service" rewrite.

**One honest exception:** the capture agent itself can't be containerised — it
runs on a real Windows desktop and hooks into the accessibility layer and the
browser. Everything *downstream* of capture containerises fine. Worth knowing so
the containerisation goal doesn't distort the capture design.

---

## 6. Things we test at this level

Cross-cutting rules need cross-cutting tests:

| Test | Passes when |
|---|---|
| **Provenance survives** | A vision-sourced value is still marked as vision-sourced in the Stage 6 document |
| **No silent merging** | Force the two tiers to disagree → both readings kept, flagged, no merged value. **Zero tolerance** |
| **No cleartext anywhere** | Search the whole store, all exports, all logs for a sentinel ID → zero hits outside the reversal vault |
| **Hash stability** | One ID written five ways → one hash. Five different IDs → five hashes |
| **Adapter swap** | Full pipeline runs on local adapters, then on a second set, changing **only the config file**. No code change |
| **Audit completeness** | Every reversal-vault access appears in the audit log with who/why/when |
| **Not over-hashed** | Button labels and screen titles are still readable — Stage 5 can't work otherwise |

---

## 7. What's still open

| Item | Whose call |
|---|---|
| **Federated Stage 4 mining is unsolved** — needs its own research pass | Research, before Stage 4 |
| Data classification and storage location | InfoSec / data governance |
| Works council / employee consent posture | Legal / HR |
| Where vision inference runs (desktop vs central) — drives endpoint cost | Architecture, after measurement |
| HMAC key rotation strategy | Security architecture |
| Freedom-to-operate on the DLP clipboard patents. **Internal use is not exempt from patent infringement under US law** — this needs real counsel, not a workaround | Internal IP counsel |

---

## Worth debating

1. **"Is the vision tier worth building at all?"** Genuinely open. Measure
   structural coverage first (Stage 1's coverage map). If the accessibility layer
   reaches well over 90% of real work, the vision tier becomes an option rather
   than a core component and the whole project gets cheaper. **Measure before
   building it.**

2. **"Hashing makes the output less useful."** Partly true — the final document
   can't show real loan IDs. I think that's the right trade inside a bank, and
   the reversal vault handles the genuine exceptions. But it's your call, and
   it's worth knowing the cost rather than discovering it at review time.

3. **"Federation makes Stage 4 harder for what benefit?"** Fair challenge. The
   benefit is that no single system holds a company-wide behavioural dataset. The
   cost is a genuinely unsolved mining problem. If governance would permit pooled
   hashed data, Stage 4 gets much simpler — worth asking before assuming it
   wouldn't.

4. **"Are we now just rebuilding SKAN?"** We've adopted their coverage model
   (vision where structure doesn't exist). What stays different: we use vision as
   a *fallback* rather than a primary, so most values are exact rather than
   recognised; and we tag provenance so the difference is visible. If we ever
   stop doing those two things, the honest answer would become yes.
