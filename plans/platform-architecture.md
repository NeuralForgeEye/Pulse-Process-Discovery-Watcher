# Platform Architecture — cross-cutting concerns

**Applies to:** every stage. Read this alongside `pulse-architecture.md`.
**Research backing:** `research/deployment-sensing-and-data-controls.md`.
**Plain-English version:** `manual-readable/platform.md`.
**Status:** blueprint only — no implementation code has been written.

> **Why this document exists.** Sensing provenance, data controls, deployment
> shape and environment abstraction cut across all seven stages. Writing them
> into each stage blueprint would duplicate the same text seven times and
> guarantee they drift apart. They live here; each stage blueprint references
> this document rather than restating it.

---

## 1. Deployment context

Pulse runs **inside Wells Fargo's own environment**. It is an internal tool.

This is not a detail — it inverts the problem external vendors solve. SKAN
needs a gateway server because their infrastructure sits outside the bank and
data must be sanitised before crossing that boundary. **We have no boundary to
cross.** We therefore inherit the *controls* that make such systems acceptable,
without inheriting the *architecture* built to move data out.

Practical consequences:

- No vendor Data Processing Agreement, no cross-boundary transport problem.
- **But the internal bar is unchanged:** identifiers protected at rest and in
  transit, audited access, defined retention, data classification approved
  through the existing governance path.
- Target shape is **clustered and multi-datacenter**, serving a large internal
  audience. Design for that from the first commit; do not write a
  single-machine script and plan to scale it later.

---

## 2. Sensing architecture: tiered, arbitrated, provenance-tagged

### 2.1 The three sensing tiers

| Tier | Mechanism | Where it applies | Value quality |
|---|---|---|---|
| **T1 — Accessibility** | Windows UI Automation (Stage 1 Phase 1.3) | Native Windows applications exposing a UIA provider | **Exact.** The application states the value |
| **T2 — DOM** | Chrome MV3 extension (Stage 1 Phase 1.6) | Web applications in Chromium browsers | **Exact**, plus semantic field identity (accessible name, label association) |
| **T3 — Computer vision** | Screen-region OCR / visual element detection | Citrix, VDI, mainframe terminals, canvas-rendered apps — surfaces with no structural layer | **Inferred.** A reading of pixels, with a recognition confidence |

### 2.2 Arbitration

A per-application-surface policy selects the **cheapest sufficient** sensor:

1. Probe T1/T2 availability for the surface (does UIA expose a usable tree? is
   this a browser tab we can reach?).
2. If a structural sensor yields a usable element tree, **use it and do not run
   CV** — CV costs orders of magnitude more compute for a worse value.
3. If not, fall back to T3 and **record the fallback and its reason**.
4. Cache the decision per surface signature; re-probe on capture-health signals
   (Stage 7 Phase 7.2), because an application update can change availability in
   either direction.

### 2.3 Provenance tagging — mandatory, non-negotiable

Every captured value carries:

```
sensor:            t1_uia | t2_dom | t3_cv
sensor_confidence: 1.0 for T1/T2 exact reads; the recogniser's score for T3
sensor_agreement:  agree | disagree | single_sensor | not_cross_checked
fallback_reason:   why a lower tier was used, when applicable
```

**Rules that must not be relaxed:**

- **Never silently merge values of different provenance into one "clean"
  record.** A CV-guessed value and an exact structural read stay distinguishable
  end to end, through every stage, into Stage 6's output.
- Where both a structural sensor and CV observe the same identifier,
  **agreement reinforces confidence; disagreement is flagged, never averaged**.
  An averaged value is a fabricated value.
- Downstream stages must be able to **filter or weight by sensor tier**, and
  Stage 6 must be able to report accuracy **per surface**, not as a single
  blended number.

**Why this is load-bearing:** without provenance tagging, CV's weaker
performance on legacy surfaces disappears inside an average, and every accuracy
claim the system makes becomes unfalsifiable. With it, "we are exact on modern
applications and approximate on mainframe screens, and here is which is which"
is a statement that can be checked. That distinction is the difference between
a measurement and a marketing figure, and it is one of the four differentiators.

### 2.4 Cross-validation opportunity

Where a surface supports both tiers (a browser page also visible to CV), run
**both periodically as a calibration sample** — not continuously. This yields a
measured, ongoing estimate of T3's real accuracy *on this customer's actual
screens*, rather than a vendor benchmark. Sample rate configurable; default low.

### 2.5 Honest status of the CV tier

**The T3 implementation cannot be validated outside the Wells Fargo
environment** — the Citrix, VDI and mainframe surfaces it exists to read are not
available on a development machine. It must therefore be:

- built behind the same interface as T1/T2, so it is swappable and testable in
  isolation;
- exercised against **recorded** screen samples where those can be obtained
  lawfully within the bank;
- **flagged as untested in every status report and never demonstrated as
  proven** until it has run against real target surfaces.

---

## 3. Data controls

### 3.1 Classify before deciding

| Class | Examples | Treatment |
|---|---|---|
| **Sensitive identifier** | Loan ID, ECN, account number, customer reference | **Keyed HMAC at the point of capture.** Cleartext never enters the pipeline |
| **Structural / procedural** | Field names, button labels, screen titles, control types, timestamps | **Readable, unhashed.** Stages 4 and 5 need to read these; hashing them would break event abstraction and process-type labelling for no security gain |
| **Free text** | Comment fields, notes | Redaction pipeline (Presidio), retain redacted form |
| **Sensitive by policy** | Password fields, blocklisted applications | **Never captured at all** |

The second row matters as much as the first. **Over-hashing is a real failure
mode**: a system that hashes button labels cannot tell a QA/QC process from a
data-entry process, and cannot produce a readable document. Protect what is
sensitive; leave readable what is procedural.

### 3.2 Keyed HMAC at the point of capture

- **HMAC-SHA256**, key retrieved from the internal Vault via the secrets
  interface (§4.2). Never a hardcoded or derived-from-hostname key.
- **Normalise before hashing** — case-fold, strip separators and whitespace,
  optionally strip a known prefix — so `LN-48213`, `ln 48213` and `LN48213`
  produce one hash, preserving matching across formatting variation.
- **Also hash token components** where an identifier decomposes
  (`LN` + `48213`), so a bare `48213` elsewhere can still match. This partially
  recovers the substring matching that hashing otherwise destroys.
- Hashing happens **in the capture host, before the event reaches the store**.
  The pipeline never holds cleartext, so the pipeline does not have to be
  trusted with it.
- **Key rotation** changes all hashes. Version every hash with its key
  generation, and keep a re-hash path for the reversal vault, or historical data
  stops matching new data at the first rotation.

**What this costs, recorded plainly:** fuzzy matching (edit-distance
similarity between near-miss identifiers) is impossible on hashes. Normalisation
and token hashing cover the common cases. If a real corpus later shows
significant unmatched near-miss identifiers, that is a finding to escalate, not
a reason to quietly reintroduce cleartext.

### 3.3 Reversal vault

- A **separate, narrowly-scoped, fully audited** store mapping hash → encrypted
  real value. Same shape as PCI card tokenization.
- **Not reachable from the main pipeline.** Different service, different
  credentials, different network path.
- Access requires an authenticated human identity, a stated reason, and produces
  an audit record. Rate-limited and alertable.
- Exists for the rare case where a reviewer must see a real value behind a
  flagged episode — not for routine operation. If it is being used routinely,
  something upstream is wrong.

### 3.4 Audit

Every access to sensitive data or to the reversal path is logged and
reviewable: who, what, when, why, which records. This matches the audit
expectations imposed on external vendors, and applies to us despite being
internal. In a regulated QA/QC context this audit trail may be as valuable as
the process maps.

### 3.5 Data classification and storage location

**Not a technical decision.** Follow Wells Fargo's internal data governance
policy through the same approval path used for the db_discovery project's
encrypted connection strings. This blueprint states the *requirement*; the
*answer* comes from InfoSec / data governance.

### 3.6 No individual performance surveillance

Aggregate by default. Per-person views only on an explicit, logged request.
Stage 4 Phase 4.7 and Stage 7 both make individual comparison technically
trivial; the guard is policy and must be enforced in code, not left to
intention. Breaching this destroys the workforce consent the whole capture layer
depends on.

---

## 4. Environment-agnostic architecture

**Build once; move environments by configuration, never by rewrite.**

### 4.1 Ports and adapters

Every external dependency sits behind an interface with at least two
implementations — one for local development, one for the bank:

| Port | Local adapter | Wells Fargo adapter |
|---|---|---|
| `EventStore` | SQLite (WAL) | Internal database per governance approval |
| `SecretsProvider` | Local encrypted file | Internal Vault |
| `Sensor` | T1 UIA / T2 DOM | Same, plus T3 CV |
| `ReversalVault` | Local encrypted store | Internal tokenization service |
| `AuditSink` | Local append-only log | Internal audit/SIEM pipeline |
| `SummaryTransport` | Local directory | Internal messaging between business units |

**No business logic knows which adapter it is using.** If a stage's code
mentions SQLite or a file path, that is a defect.

### 4.2 One environment file

A single config file declares where storage, secrets, sensing, audit and
transport point. **Moving from a development machine to the bank is an edit to
that one file** — not a rebuild, not a branch, not a port.

### 4.3 Containerised from the start

Docker Compose locally, so the local shape matches the clustered
multi-datacenter target: separate capture host, processing service, store, and
(later) summary transport. Avoids the "script on my machine → service in
production" rewrite that this decision exists to prevent.

**Note the one thing that cannot be containerised:** the capture host itself
runs on the user's Windows desktop, hooking into UIA and the browser. It is a
desktop agent, not a container workload. Everything *downstream* of capture
containerises cleanly. Do not let the containerisation goal distort the capture
layer's design.

---

## 5. Federated topology

**Even hashed data is not pooled company-wide by default.** Mine locally per
business unit / datacenter; share only **pattern-level summaries** centrally.

### 5.1 What may be shared centrally

- Field-pair relationship counts: `(from_path_hash, to_path_hash) → count`
- Activity-level frequency summaries
- Process model structures (no case data)
- Quality and coverage metrics

**A fit worth noticing:** Stage 3's population corroboration needs exactly
`(from_path_hash → to_path_hash, count)` — a pair of one-way hashes and an
integer, containing no content. The mechanism that produces our distinctive
capability is therefore already federation-shaped. That was not designed in; it
is a fortunate property, and it should not be assumed to hold for other
mechanisms without checking each one.

### 5.2 What stays local

Raw events, episodes, links, reversal vault, anything actor-identifiable.

### 5.3 ⚠️ OPEN GOVERNANCE ITEM — Stage 4 currently assumes pooling

> **OPEN GOVERNANCE ITEM: Stage 4 currently assumes pooling of HMAC-hashed
> identifiers across business units is permitted. This has not been confirmed by
> data governance/InfoSec. If later found not permitted, fall back to the
> federated local-mine-then-merge-models approach (candidate designs already
> drafted under PA-1) instead of pooled mining. Do not treat pooled mining as
> final/approved architecture until confirmed.**

**Status: working assumption, not a settled decision.** Stage 4 is being built
against a single pooled corpus of HMAC-hashed identifiers. This is a deliberate
choice to keep Stage 4 tractable while the governance question is answered — not
a conclusion that federation was rejected on its merits.

**The federated candidate designs below are retained deliberately.** They are the
fallback plan, not superseded work. Do not delete them.

### 5.4 Keeping the fallback cheap — design constraints that apply now

If pooled mining is later refused, the cost of switching should be a boundary
change, not a rewrite. Three constraints, all cheap to honour today and
expensive to retrofit:

1. **Put the corpus behind a `CorpusProvider` port** (same pattern as §4.1).
   `PooledCorpusProvider` now; `FederatedCorpusProvider` is the fallback
   implementation. **No Stage 4 phase may reach past this interface** to assume
   it can enumerate every episode in the company.
2. **Make the activity dictionary globally versioned and shared from day one.**
   This is the critical one. Under federation, each business unit would derive
   its *own* activity dictionary from its own screens — and two units' models
   cannot be merged if `Search loan document` in one is `Activity 17` in the
   other. **A shared, versioned dictionary is a hard prerequisite for every
   federated candidate**, and building it now costs almost nothing because we
   need a reviewable dictionary regardless (Stage 4 Phase 4.2).
3. **Prefer aggregatable statistics where they are equally good.** Directly-
   follows counts, activity frequencies and transition counts all sum across
   units; trace-level operations do not. Where two approaches are of comparable
   quality, choose the one that would still work on summaries.

**Which Stage 4 phases would break under federation** (so the blast radius is
known rather than discovered):

| Phase | Under federation |
|---|---|
| 4.1 grouping | Partially — feature vectors are shareable; clustering would need to run centrally on those |
| 4.2 event abstraction | **Works only if the dictionary is shared** — see constraint 2 |
| 4.3 frequency | Fine — counts aggregate |
| 4.4 discovery | **Breaks** — needs traces |
| 4.5 quality | **Breaks** — alignments need traces |
| 4.6 cross-app view | Partially — OC-DFG needs the OCEL log |
| 4.7 variants | **Breaks** — needs traces |

### 5.5 Federated candidate designs (retained — the fallback plan)

Three candidate approaches, none yet evaluated:

1. **Merge models** — discover locally, reconcile structures centrally.
   Hardest; process model merging is its own research area.
2. **Share activity-level summaries** — send directly-follows counts centrally
   and discover from the aggregate. Loses case-level structure but is simple and
   leaks nothing beyond hashes and counts. **Probably the pragmatic start.**
3. **Central mining on hashed data by exception** — pool hashed episodes where
   governance permits. Simplest technically, weakest on the federation principle.

**These remain unevaluated.** If governance permits pooling, they stay on the
shelf. If it does not, candidate 2 (share activity-level summaries) is the
pragmatic starting point — and it only works if constraint 2 above (shared
activity dictionary) has been honoured from the start.

---

## 6. Validation checkpoints for this document

Cross-cutting concerns need cross-cutting tests:

- **Provenance integrity:** a value captured by T3 CV is still identifiable as
  T3 in Stage 6's final output. Trace one end to end. Pass = the tag survives
  every stage.
- **No-merge rule:** construct a case where T1 and T3 disagree on the same
  identifier. The system must flag it, and must **not** emit a single merged
  value. Automated test, zero tolerance.
- **No cleartext:** search the entire event store, exports and logs for a
  sentinel identifier value used during a capture run. Pass = **zero
  occurrences** anywhere outside the reversal vault.
- **Hash stability:** the same identifier in five formatting variants produces
  one hash; five different identifiers produce five.
- **Adapter swap:** run the full pipeline against local adapters, then against
  a second set of adapters, changing **only the environment file**. Pass = no
  code change required, identical results.
- **Audit completeness:** every reversal-vault access in a test run appears in
  the audit sink with actor, reason and timestamp.
- **Over-hashing check:** button labels and screen titles remain readable in the
  store. Stage 5 cannot work otherwise.

---

## 7. Open items

| # | Item | Owner |
|---|---|---|
| **PA-1** | **OPEN GOVERNANCE ITEM — pooled vs federated mining.** Stage 4 currently assumes pooling of HMAC-hashed identifiers across business units is permitted. **Not confirmed.** Federated fallback designs retained in §5.5; cheap-fallback constraints in §5.4 | **Data governance / InfoSec** — confirm or refuse |
| **PA-2** | Data classification and storage location | InfoSec / data governance (db_discovery approval path) |
| **PA-3** | Works council / employee consent posture for content-bearing capture | Legal / HR |
| **PA-4** | Where CV inference runs — endpoint or central. Drives endpoint footprint, the main objection a desktop team will raise | Architecture, after measurement |
| **PA-5** | HMAC key rotation and re-hash strategy | Security architecture |
| **PA-6** | Freedom-to-operate on DLP clipboard patents. Internal use is **not** exempt from infringement under US law | Internal IP counsel |
