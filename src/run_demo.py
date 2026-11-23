"""Demo runner: build an estimate from the synthetic scope document."""

from pathlib import Path

from src.estimate import build_estimate, hours_csv, load_json, schedule_xml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    templates = load_json(ROOT / "data" / "wbs_templates.json")["deliverable_types"]
    past = load_json(ROOT / "data" / "past_estimates.json")
    tds = (ROOT / "data" / "sample_tds.md").read_text(encoding="utf-8")

    est = build_estimate(tds, templates, past,
                         owner="amara.estimate-owner", reviewer="jordan.reviewer")

    print(f"{est.title} — stage: {est.stage}; disciplines: {', '.join(est.disciplines)}")
    print(f"{'Deliverable':<28}{'Task':<44}{'Hours':>7}  {'Conf':<6}  Source")
    for line in est.lines:
        print(f"{line.deliverable:<28}{line.task:<44}{line.hours:>7.1f}  "
              f"{line.confidence:<6}  {line.source}")
    print(f"\nEngineering hours: {est.engineering_hours:.1f}")
    print(f"Project Management (10%): {est.pm_hours:.1f}")
    print(f"Total hours: {est.total_hours:.1f}")
    print(f"Schedule duration: {est.duration_days()} working days")
    low = est.low_confidence_lines
    print(f"Low-confidence rows: {len(low)} (template hours — review these first)")

    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "estimate_hours.csv").write_text(hours_csv(est), encoding="utf-8")
    (out / "estimate_schedule.xml").write_text(schedule_xml(est), encoding="utf-8")
    print(f"\nWrote {out / 'estimate_hours.csv'} and {out / 'estimate_schedule.xml'}")

    # Review workflow: owner cannot approve their own estimate.
    est.submit()
    try:
        est.approve("amara.estimate-owner")
    except ValueError as exc:
        print(f"\nOwner self-approval blocked: {exc}")
    est.approve("jordan.reviewer")
    print(f"Status after review: {est.status} (revision {est.revision})")
    try:
        est.edit_line_hours(0, 99)
    except ValueError as exc:
        print(f"Edit after approval blocked: {exc}")
    reopened = est.reopen()
    print(f"Reopened as revision {reopened.revision} ({reopened.status}) — "
          "approved content stays immutable")


if __name__ == "__main__":
    main()
