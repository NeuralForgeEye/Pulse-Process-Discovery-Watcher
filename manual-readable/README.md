# manual-readable/

Plain-English explanations of what we are building, why, and how you can see it
working with your own hands. No jargon without a translation next to it.

**This folder is for reading and arguing with.** The other folders are for
building from.

| Folder | What lives there | Written for |
|---|---|---|
| `manual-readable/` | The story. What we're building, in normal words, with examples and pictures. | You, reviewing and pushing back |
| `plans/` | The build blueprints. Exact steps, exact libraries, exact pass/fail tests. | Whoever (or whatever) writes the code |
| `research/` | The evidence. What was actually checked, what competitors already do, the arguments for and against each choice. | Anyone asking "how do you know that?" |
| `../plans/pulse-architecture.md` | The 7-stage plan. The source of truth. | Everyone |

Every claim in this folder traces back to something in `plans/` or `research/`.
If you read something here that sounds confident, you can go check the receipt.

---

## Reading order

1. **`00-the-big-picture.md`** — the whole system, all seven stages, in one
   sitting. Start here.
2. **`platform.md`** — the decisions that apply to every stage: how we sense,
   how data is protected, where it runs. Read this second; the stage files
   assume it.
3. **`stage-1.md`** through **`stage-7.md`** — one file per stage, in order.
   Each covers that stage's phases, what gets built, what we use and why not the
   alternative, and exactly how you test it yourself.

All seven exist. Each was written **after** researching that stage — real papers,
real libraries, prior-art checks, and the argument for and against each choice —
so the per-stage files describe what we're actually going to build, not a guess
at it. Where something wasn't verified, the file says so in those words.

**Rough reading time:** the big picture is ~15 minutes. Each stage file is
~10–20 minutes. You don't have to read them in order once you've read the big
picture — but Stages 1→2→3 build on each other tightly, so that sequence is worth
keeping.

**If you only read three:** the big picture, `platform.md` (the decisions that
bind everything), and Stage 3 (where the defensible idea lives).

---

## How each stage file is laid out

The same shape every time, so you always know where to look:

- **What this stage does** — one paragraph, no jargon.
- **The picture** — a diagram of what flows in and what flows out.
- **The phases** — for each one:
  - what we're building
  - what we're using to build it, and why that and not the alternative
  - a real example from the running story
  - what exists on disk when it's finished
  - **how you test it yourself** — actual steps you can perform
- **What you'll have when the stage is done** — and what you still won't have.
- **Worth debating** — the parts I'm least sure about, in plain English.

---

## A note on dates

There are none, on purpose. Git records when every file changed, so writing
dates inside the files just creates a second version of the truth that quietly
goes stale. If you want to know when something was written, `git log` the file.
