# Pulse — Flow Chart Presentation

*Built for talking through with a manager/business audience. Boxes are left uncolored on purpose — add your own colors (each Mermaid box has a `class` you can restyle). Solid-border style = built and tested with real numbers. Dashed-border style = designed, not built yet.*

---

## 1. The Big Picture — Seven Stages

**One line on the whole thing:** raw activity goes in on the left, a finished, trustworthy process document comes out on the right.

```mermaid
flowchart LR
    S1["STAGE 1<br/>Watching<br/>-----------<br/>Records every click, app switch,<br/>and window change<br/>-----------<br/>OUTPUT: a timeline of raw events"]
    S2["STAGE 2<br/>Case Boundaries<br/>-----------<br/>Cuts the endless recording into<br/>individual cases<br/>-----------<br/>OUTPUT: a list of separate cases"]
    S3["STAGE 3<br/>Connecting Apps<br/>-----------<br/>Proves how information moved<br/>between different systems<br/>-----------<br/>OUTPUT: one connected story per case"]
    S4["STAGE 4<br/>Finding the Pattern<br/>-----------<br/>Finds the real process common<br/>to hundreds of cases<br/>-----------<br/>OUTPUT: one process map"]
    S5["STAGE 5<br/>Naming the Process<br/>-----------<br/>Labels what kind of process it is<br/>-----------<br/>OUTPUT: a category label + confidence"]
    S6["STAGE 6<br/>Final Report<br/>-----------<br/>Packages everything into one<br/>readable document<br/>-----------<br/>OUTPUT: the process document"]
    S7["STAGE 7 optional<br/>Staying Current<br/>-----------<br/>Watches for the real process<br/>quietly changing later<br/>-----------<br/>OUTPUT: a change alert for a human"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7

    classDef built fill:#ffffff,stroke:#222222,stroke-width:3px;
    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class S1 built
    class S2,S3,S4,S5,S6,S7 planned
```

**Where we actually are on this chart today:** only the first **two of ten phases inside Stage 1** are done (see below) — so on this 7-box picture, we are still *inside box 1*, not past it yet. Everything from the middle of Stage 1 onward is designed but not built.

---

## 2. Stage 1 — Watching (capture)

**One line — what happens:** Pulse quietly records what you clicked, which app/window you were in, and what you copied — across every application, all the time.
**One line — how the output is shown:** a plain time-ordered table (what we demoed): time, app, window, action. Not a video, not raw database bytes.

```mermaid
flowchart TD
    P1["1.1 Event Schema and Store<br/>Defines what one recorded<br/>event looks like, saves it safely<br/>STATUS: BUILT and TESTED"]
    P2["1.2 Desktop Capture<br/>Watches clicks, app switches,<br/>window open/close<br/>STATUS: BUILT and TESTED"]
    P3["1.3 Read On-Screen Text<br/>Reads the actual words/values<br/>visible on screen, not just 'a click happened'<br/>STATUS: planned — next up"]
    P4["1.4 Highlight Capture<br/>Records when someone<br/>highlights/selects text as its own signal<br/>STATUS: planned"]
    P5["1.5 Copy/Paste Capture<br/>Links a copy in one app<br/>to a paste in another<br/>STATUS: planned"]
    P6["1.6 Browser Capture<br/>Same watching, inside<br/>Chrome/Edge tabs<br/>STATUS: planned"]
    P7["1.7 One Merged Timeline<br/>Combines every source into<br/>one correctly-ordered record<br/>STATUS: planned"]
    P8["1.8 Privacy Rules<br/>Hashes sensitive IDs like loan numbers;<br/>keeps labels/titles readable<br/>STATUS: planned"]
    P9["1.9 Full Acceptance Test<br/>Proves it all works together<br/>across several real apps<br/>STATUS: planned"]
    P10["1.10 Fallback for Old Screens<br/>Computer-vision reading for<br/>mainframe / Citrix screens<br/>STATUS: planned — cannot be tested until inside the bank"]

    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9 --> P10

    classDef built fill:#ffffff,stroke:#222222,stroke-width:3px;
    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class P1,P2 built
    class P3,P4,P5,P6,P7,P8,P9,P10 planned
```

**Real numbers behind the two "built and tested" boxes:** 10,000/10,000 events written and read back correctly; 20/20 broken records correctly rejected; 5/5 hard-kill tests recovered with no damage; ~3,290 events/sec (needed ≥2,000); 4 live test runs each with 100% of app switches captured, 100% correctly attributed to the right app, and zero keystrokes ever recorded.

---

## 3. Stage 2 — Finding Where One Case Starts and Ends

**One line — what happens:** Slices the nonstop recording into individual, separate cases (e.g. "this is one loan review, start to finish").
**One line — how the output is shown:** a list of episodes, each with a start time, end time, and the case identifier it was anchored on.

```mermaid
flowchart TD
    Q1["2.1 Case Data Model<br/>Defines what 'one case' means,<br/>plus a hand-checked answer key<br/>STATUS: planned"]
    Q2["2.2 Timeline Enrichment<br/>Adds helper signals to<br/>the raw timeline<br/>STATUS: planned"]
    Q3["2.3 Find Case IDs<br/>Finds and standardizes loan IDs,<br/>ticket numbers, etc. on screen<br/>STATUS: planned"]
    Q4["2.4 Baseline Segmenter<br/>A simple control-group method,<br/>to compare everything else against<br/>STATUS: planned"]
    Q5["2.5 Main Method<br/>Anchors episode boundaries on<br/>case IDs actually seen on screen<br/>STATUS: planned"]
    Q6["2.6 Fallback Method<br/>Handles stretches with<br/>no visible case ID<br/>STATUS: planned"]
    Q7["2.7 Arbitration<br/>Decides between methods,<br/>flags unclear boundaries for a human<br/>STATUS: planned"]
    Q8["2.8 Accuracy Test<br/>Measures how well it<br/>sliced real data<br/>STATUS: planned"]

    Q1 --> Q2 --> Q3 --> Q4 --> Q5 --> Q6 --> Q7 --> Q8

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8 planned
```

---

## 4. Stage 3 — Connecting the Dots Across Applications

**One line — what happens:** Proves *how* a value (like a loan ID) actually moved from one application to another during a case — using real evidence, ranked from strongest (a proven copy/paste) to weakest (just visible around the same time).
**One line — how the output is shown:** one connected story per case: "opened App A, saw loan ID, opened App B, searched using that same loan ID" — with each link labeled by how sure we are.

```mermaid
flowchart TD
    R1["3.1 Evidence Model<br/>Defines the evidence types<br/>+ a hand-checked answer key<br/>STATUS: planned"]
    R2["3.2 Candidate Matching<br/>Narrows down which values<br/>might be linked<br/>STATUS: planned"]
    R3["3.3 Strongest Evidence<br/>Proven copy-then-paste<br/>transfers<br/>STATUS: planned"]
    R4["3.4 Weaker Evidence<br/>Deliberate highlighting,<br/>or just visible on screen<br/>STATUS: planned"]
    R5["3.5 Scoring<br/>Turns evidence into a<br/>calibrated confidence score<br/>STATUS: planned"]
    R6["3.6 Population Backup<br/>Weak single instances get<br/>backed up if the SAME link repeats<br/>across hundreds of other cases<br/>STATUS: planned — the most defensible idea in the project"]
    R7["3.7 Story Assembly<br/>Builds one connected<br/>narrative per case<br/>STATUS: planned"]
    R8["3.8 Accuracy Test<br/>Measures how well the<br/>links hold up<br/>STATUS: planned"]

    R1 --> R2 --> R3 --> R4 --> R5 --> R6 --> R7 --> R8

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class R1,R2,R3,R4,R5,R6,R7,R8 planned
```

---

## 5. Stage 4 — Finding the Real Process Across Many Cases

**One line — what happens:** Looks across hundreds of individual cases and finds the pattern that actually holds up — the backbone steps everyone does, the optional branches, and the rare one-off mistakes.
**One line — how the output is shown:** one process map/diagram showing the steps in order, including where it branches.

```mermaid
flowchart TD
    T1["4.1 Group Similar Cases<br/>Groups cases that look like<br/>the same kind of task<br/>STATUS: planned"]
    T2["4.2 Name the Steps<br/>Turns raw clicks into named<br/>business steps, e.g. 'Search for loan document'<br/>STATUS: planned"]
    T3["4.3 Backbone vs Noise<br/>Separates 'nearly everyone<br/>does this' from rare exceptions<br/>STATUS: planned"]
    T4["4.4 Discover the Map<br/>Runs the actual process-mining<br/>algorithm<br/>STATUS: planned"]
    T5["4.5 Quality Check<br/>Measures how good/trustworthy<br/>the discovered map is<br/>STATUS: planned"]
    T6["4.6 Cross-App View<br/>Shows the map as it flows<br/>across applications<br/>STATUS: planned"]
    T7["4.7 Variants & Exceptions<br/>Captures the branches and<br/>unusual paths<br/>STATUS: planned"]
    T8["4.8 Formal Acceptance<br/>Final sign-off test<br/>for this stage<br/>STATUS: planned"]

    T1 --> T2 --> T3 --> T4 --> T5 --> T6 --> T7 --> T8

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class T1,T2,T3,T4,T5,T6,T7,T8 planned
```

---

## 6. Stage 5 — Naming What Kind of Process It Is

**One line — what happens:** Looks at the shape of the process map plus the actual words on screen ("Approve," "Reviewer Comments") and proposes what type of process this is.
**One line — how the output is shown:** a label like "QA/QC review," with the evidence behind the guess, confirmed or corrected by a human the first several times.

```mermaid
flowchart TD
    U1["5.1 Naming Vocabulary<br/>Adopts a standard business-<br/>process category list<br/>STATUS: planned"]
    U2["5.2 Shape Evidence<br/>Reads clues from the<br/>map's shape<br/>STATUS: planned"]
    U3["5.3 Language Evidence<br/>Reads clues from on-screen<br/>words and labels<br/>STATUS: planned"]
    U4["5.4 Combine Evidence<br/>Merges both clues into<br/>one best guess<br/>STATUS: planned"]
    U5["5.5 Human Confirms<br/>A person confirms or<br/>corrects the first several guesses<br/>STATUS: planned"]

    U1 --> U2 --> U3 --> U4 --> U5

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class U1,U2,U3,U4,U5 planned
```

---

## 7. Stage 6 — Producing the Final Output

**One line — what happens:** Packages everything learned into one clear written document — this is the actual deliverable the whole project exists to produce.
**One line — how the output is shown:** a structured report: steps in order, how apps connect, branches/exceptions, the process type, plus diagrams, and an honest "what we don't know" section.

```mermaid
flowchart TD
    V1["6.1 Description Model<br/>Builds the model + keeps<br/>every claim's evidence trail<br/>STATUS: planned"]
    V2["6.2 Written Document<br/>Generates the actual<br/>human-readable report<br/>STATUS: planned"]
    V3["6.3 Diagrams & Exports<br/>Produces visual diagrams<br/>+ machine-readable files<br/>STATUS: planned"]
    V4["6.4 'What We Don't Know'<br/>A mandatory honesty<br/>section, built automatically<br/>STATUS: planned"]
    V5["6.5 Comprehension Test<br/>Proves a stranger can<br/>actually understand it<br/>STATUS: planned"]

    V1 --> V2 --> V3 --> V4 --> V5

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class V1,V2,V3,V4,V5 planned
```

---

## 8. Stage 7 — Keeping It Current (optional for v1)

**One line — what happens:** Because Pulse never stops watching, it can notice later if the real process quietly changed, instead of the document silently going stale.
**One line — how the output is shown:** an alert to a human — "this process may have changed" — with a diff, never a silent auto-update.

```mermaid
flowchart TD
    W1["7.1 Baseline Snapshots<br/>Saves a versioned copy<br/>of the current map<br/>STATUS: planned"]
    W2["7.2 Capture-Health Watch<br/>Checks that Pulse's OWN<br/>sensing hasn't broken<br/>STATUS: planned — recommended even for v1"]
    W3["7.3 Drift Detection<br/>Detects the real-world<br/>process shifting<br/>STATUS: planned"]
    W4["7.4 Human Review<br/>A person reviews and<br/>accepts/rejects the change<br/>STATUS: planned"]

    W1 --> W2 --> W3 --> W4

    classDef planned fill:#ffffff,stroke:#222222,stroke-width:1px,stroke-dasharray: 6 4;
    class W1,W2,W3,W4 planned
```

---

## How to use this for your presentation

- Each stage's Mermaid box block has a `classDef` at the bottom — that's where you set colors (e.g. `classDef built fill:#c6f6c5,...` for green). Change the hex codes, nothing else needs to change.
- Solid border = built & tested. Dashed border = designed, not built. That's the honest state right now — most of the chart is still dashed.
- If your viewer doesn't render Mermaid automatically (GitHub and VS Code with the Mermaid preview extension both do), export each diagram as an image first and paste those into your slide deck.
