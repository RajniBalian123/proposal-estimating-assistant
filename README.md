# Proposal Estimating Assistant — Demo

A working demo of the estimating pattern behind a proposal-response system:
take in a technical scope document, retrieve what the organization already
knows from past estimates, and generate an editable work-breakdown estimate
with hour confidence, a schedule, and a review workflow.

This is a personal demo project, rebuilt from scratch with synthetic data. It
captures the pattern — scope intake, nearest-past-estimate lookup, WBS
templates, confidence scoring, scheduling, review and approval — without any
client code, client data, or proprietary material.

## The problem

Estimating engineering work from a scope document is slow and inconsistent
when it starts from a blank spreadsheet every time. The organization already
has the answer in its history: past estimates for similar scopes. The system
makes that history usable — matched, explained, and editable — instead of
letting every estimate start from zero.

## How it works

```
Technical scope document (TDS)
  -> parse deliverables and stages/disciplines
  -> nearest past-estimate lookup (scope similarity)
  -> expand deliverables through WBS templates into hour rows
  -> hour confidence per row (High / Medium / Low)
  -> project-management hours (default 10% of engineering hours)
  -> schedule (stages sequential, same-stage disciplines in parallel)
  -> review workflow (draft -> submitted -> approved / rejected)
  -> exports (hours CSV, schedule XML)
```

## Worked example: scope document → estimate → quote package

This is the exact output of `python -m src.run_demo` on the sample scope in
`data/sample_tds.md` — a fictional heat-exchanger replacement at the
Harborview Generating Station, Detailed design stage, Mechanical and
Electrical / I&C disciplines, six deliverables, package due within 12 weeks.

**Step 1 — intake.** The scope document is parsed into its deliverables
(Design Plan, Walkdown Report, Technical Specification, Design Manual,
Vendor Documentation Review, Closeout) and its stage/disciplines.

**Step 2 — nearest past-estimate lookup.** Five deliverables match past
estimate PE-1042 (similarity 0.18); Vendor Documentation Review matches
PE-1018 (similarity 0.12). Every matched row lands at Medium confidence —
close enough to ground the hours, weak enough that the engineer should still
check them.

**Step 3 — estimate.** WBS templates expand each deliverable into hour rows:

| Deliverable | Tasks | Hours |
| --- | ---: | ---: |
| Design Plan | 4 | 40.0 |
| Walkdown Report | 4 | 56.0 |
| Technical Specification | 4 | 64.0 |
| Design Manual | 4 | 76.0 |
| Vendor Documentation Review | 4 | 28.0 |
| Closeout | 3 | 20.0 |
| **Engineering subtotal** | **23** | **284.0** |
| Project Management (10% of engineering) | 3 | 28.4 |
| **Total** | **26** | **312.4** |

The biggest single row is "Draft design manual" at 40.0 hours; the smallest
are "Receive and log vendor documents" and "Issue review package" at 3.5
hours each. No row is Low confidence in this run, so nothing is flagged as
template-only hours.

**Step 4 — schedule.** Duration comes from hours, one resource per task, and
7.5 hours per working day: **10.1 working days** end to end. Stages run
sequentially and same-stage disciplines run in parallel, so the 40-hour
design-manual draft (5.3 days) sets the pace rather than the raw total.

**Step 5 — quote package.** The estimate exports to `out/estimate_hours.csv`
and `out/estimate_schedule.xml` — the hours and schedule that go into the
proposal's quote. Review integrity holds throughout: the owner cannot approve
their own estimate, the estimate is approved as revision 1, and editing
approved content is blocked until it is reopened as revision 2.

## Hour confidence

Confidence is a property of the evidence behind the hours, not a measure of
AI quality:

- **High** — a close scope match in past estimates, or an engineer edit.
- **Medium** — a title match or a weaker scope match.
- **Low** — WBS template hours, or a poor scope match.

Stored as 0–100. An estimate with Low-confidence rows is still usable — the
confidence is visible on the row, so the engineer knows exactly which hours
to scrutinize.

## Run it

```bash
python -m src.run_demo
```

Pure standard library, no dependencies. It reads the synthetic scope in
`data/sample_tds.md`, matches it against `data/past_estimates.json`, expands
the WBS templates in `data/wbs_templates.json`, and prints the estimate with
hours, confidence, and schedule — plus the hours CSV and schedule XML under
`out/`.

Run the checks:

```bash
python -m unittest discover -s tests -v
```

## What this proves

- Retrieval over organizational memory: the estimate is grounded in past
  work, not invented from a template alone.
- Explainable hours: every row carries its source (which past estimate, or
  the template) and a confidence label.
- Editable estimates: the engineer can add or remove packages and tasks, or
  stop a package after an earlier task. Edits stay on this estimate; they do
  not change the organization's templates.
- Scheduling from effort: duration in working days comes from hours,
  resources, and hours per working day — not from a drawn Gantt chart.
- Review integrity: the reviewer cannot be the estimate owner, and approved
  content requires reopening. A review decision is recorded against the exact
  revision reviewed.

## Layout

- `src/estimate.py` — the estimating engine: parsing, matching, confidence,
  scheduling, review workflow, exports.
- `src/run_demo.py` — the demo runner.
- `data/` — synthetic WBS templates, past estimates, and a sample scope
  document. All fictional.
- `docs/design.md` — the full design: intake, retrieval, estimating engine,
  scheduling, review, and the wider system it sits in.
- `tests/` — checks for matching, confidence, scheduling, and review rules.

## What production adds

Real document ingestion (PDF/Word/Excel parsing, chunking, embeddings),
a model gateway for the nearest-estimate lookup, a database with Drizzle-style
typed schemas, background jobs for sync and embedding, SSO with role-based
access, and the full response-drafting side (retrieval over the knowledge base
to draft written responses, section by section). None of those are claimed here.
