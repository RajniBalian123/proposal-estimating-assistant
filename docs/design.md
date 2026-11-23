# Design: proposal estimating, from scope document to reviewed estimate

Status: demo of the estimating pattern, with synthetic data. It does not claim
production ingestion, real past estimates, or a live review system.

## 1. The flow

A pursuit starts from a technical scope document (TDS) that lists required
work. It may arrive as PDF, Word, or Excel. The system produces an Estimate:
the TDS's deliverables expanded through WBS templates into editable hour
rows. Hours come from matching past estimates, or from the WBS template when
no past estimate matches.

```
TDS (scope document)
  -> parse: deliverables, engineering stages, disciplines
  -> retrieve: nearest past estimates by scope similarity
  -> expand: WBS templates into hour rows
  -> confidence: High / Medium / Low per row, from match strength
  -> schedule: sequenced lines, stages sequential, disciplines parallel
  -> review: draft -> submitted -> approved / rejected
  -> exports: hours CSV, schedule XML
```

## 2. The domain, in plain words

- **TDS** — the client's technical scope document. The input that starts an
  estimate.
- **Deliverable Type** — a named work package: Project Management, Design
  Plan, Walkdown Report, Design Change Notice (DCN), Technical Specification,
  Design Manual, Vendor Documentation Review, Closeout, and older packages
  (Report, Calculation, Bill of Material, Drawings). An estimate can cover one
  or many **engineering stages** (Conceptual, Preliminary, Detailed, Execution
  / turnover, Closeout) and **disciplines** (mechanical, electrical /
  instrumentation & control). Those are confirmed on create.
- **WBS Template** — the reusable task tree for one deliverable type,
  including standard sub-tasks and placeholder hours. Versioned;
  administrators may add custom task rows.
- **Estimate** — the generated WBS for one TDS. The engineer can add or
  remove packages and tasks, or stop a package after an earlier task. Those
  edits stay on this estimate; they do not change the organization's templates.
- **Estimate Tab** — one stage × discipline slice of an estimate. Project
  Management sits on the project, not on a discipline tab.
- **WBS Line** — one task row, with hours the engineer can edit inline.
- **Resource Type** — the short name that looks up work center, activity, and
  material for a WBS line (e.g. project manager, senior engineer, admin).
- **Hour Confidence** — High, Medium, or Low, for how strongly the hours are
  supported by matching past scopes. High is a close scope match or an
  engineer edit; Medium is a title match or a weaker scope match; Low is
  template hours or a poor scope match. Stored as 0–100.
- **Estimate Schedule** — the sequenced WBS lines. Effort is hours. Calendar
  duration in working days comes from working-day assumptions (hours per
  working day, default 7.5, and resource count). Same-stage disciplines run in
  parallel; a later stage waits for the previous one.
- **Logic Tie** — a finish-to-start predecessor between WBS lines. Tasks
  inside a package stay sequential.
- **Estimate Assumption** — a stated condition the hours depend on (scope,
  access, exclusions), generated with the estimate for the engineer to confirm.
  Not a contractual commitment.
- **Estimate Status** — draft, submitted, approved, or rejected. Owners and
  assigned editors may edit draft, submitted, and rejected work. Approved
  content requires reopening.
- **Estimate Reviewer** — a named person assigned to review one estimate. Can
  read its full budget and approve or request changes to the saved revision
  they reviewed. Assignment alone does not permit editing. The reviewer cannot
  be the estimate owner, and cannot review their own estimate.

## 3. Nearest-past-estimate lookup

Hours from history beat hours from a blank template — but only when the match
is real. The demo scores similarity between the incoming scope text and each
past estimate's scope text (normalized token overlap), then:

- Takes the best match per deliverable above a threshold.
- Falls back to template hours when nothing matches.
- Records the source on every row: which past estimate matched, the similarity
  score, and the resulting confidence.

In production this lookup is embedding-based (scope text embedded through a
model gateway, nearest neighbours over past estimates), with the same
confidence contract on top. The demo's keyword overlap is a stand-in for the
retrieval step, not the production ranker — the point is the contract: every
hour has a source and a confidence.

## 4. Scheduling

Effort is hours; duration is derived. For each WBS line:

```
duration_days = hours / (resources × hours_per_working_day)
```

Stages run in sequence; within a stage, disciplines run in parallel. Logic
ties connect finish-to-start predecessors. Project Management hours are the
estimate's PM percentage of engineering hours (default 10%), excluding the
whole PM deliverable; unresolved engineering hours make the PM task
provisional. The schedule exports as a P6-oriented XML file — a file download,
not a live scheduling-system connection.

## 5. Review integrity

- The estimate owner manages access and budget and can keep editing submitted
  work — but cannot review their own estimate.
- A reviewer is assigned per estimate and decides on the saved revision they
  reviewed. Later changes belong to subsequent work and do not rewrite that
  decision.
- Approved content requires reopening to change. A restatement is a new
  revision, not a silent edit.

## 6. The wider system this sits in

Estimating is one half of a proposal-response system. The other half takes in
a request from a prospective client, retrieves what the organization already
knows from its knowledge base (ingested documents, synced from document
systems, ranked by priority tier and staleness), and drafts a response section
by section. The same retrieval discipline applies: priority tiers decide how
strongly a document is favoured, staleness rules decide whether retrieved
knowledge should still be trusted, and no tier means the document is excluded
from results.

The production shape is a monorepo: a web app with API routes, background job
workers for sync and embedding, a typed database layer, and SSO with
role-based access. The demo here is the estimating engine only, in plain
Python, so the pattern can be read and run without that stack.
