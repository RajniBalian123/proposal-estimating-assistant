"""Estimating engine: scope -> WBS estimate with confidence, schedule, review.

Pure standard library. The matching here is keyword overlap on scope text —
a stand-in for the embedding-based nearest-past-estimate lookup used in
production. The contract is what matters: every hour has a source and a
confidence, and the review workflow protects approved content.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
    "is", "are", "by", "at", "from", "including", "required", "within",
    "after", "before", "this", "that", "it", "its", "as", "be", "will",
}

STAGES = ["Conceptual", "Preliminary", "Detailed", "Execution", "Closeout"]


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class WBSLine:
    deliverable: str
    task: str
    hours: float
    confidence: str  # High / Medium / Low
    confidence_score: int  # 0-100
    source: str
    resources: int = 1

    @property
    def duration_days(self) -> float:
        return self.hours / (self.resources * Estimate.HOURS_PER_DAY)


@dataclass
class Estimate:
    HOURS_PER_DAY: float = 7.5
    PM_PCT: float = 0.10

    title: str = ""
    lines: list[WBSLine] = field(default_factory=list)
    stage: str = "Detailed"
    disciplines: list[str] = field(default_factory=list)
    status: str = "draft"
    owner: str = ""
    reviewer: str = ""
    revision: int = 1
    assumptions: list[str] = field(default_factory=list)
    _approved: bool = False

    @property
    def engineering_hours(self) -> float:
        return sum(l.hours for l in self.lines if l.deliverable != "Project Management")

    @property
    def pm_hours(self) -> float:
        return round(self.engineering_hours * self.PM_PCT, 1)

    @property
    def total_hours(self) -> float:
        return self.engineering_hours + self.pm_hours

    @property
    def low_confidence_lines(self) -> list[WBSLine]:
        return [l for l in self.lines if l.confidence == "Low"]

    def duration_days(self) -> float:
        """Stages run in sequence; packages within a stage run in parallel."""
        by_package: dict[str, float] = {}
        for line in self.lines:
            by_package[line.deliverable] = by_package.get(line.deliverable, 0.0) + line.duration_days
        stage_days = max(by_package.values()) if by_package else 0.0
        return round(stage_days, 1)

    def submit(self) -> None:
        if self.status != "draft":
            raise ValueError(f"cannot submit from {self.status}")
        self.status = "submitted"

    def approve(self, reviewer: str) -> None:
        if self.status != "submitted":
            raise ValueError(f"cannot approve from {self.status}")
        if reviewer == self.owner:
            raise ValueError("owner cannot review their own estimate")
        if reviewer != self.reviewer:
            raise ValueError("only the assigned reviewer can approve")
        self.status = "approved"
        self._approved = True

    def request_changes(self, reviewer: str) -> None:
        if reviewer != self.reviewer:
            raise ValueError("only the assigned reviewer can request changes")
        self.status = "rejected"
        self._approved = False

    def reopen(self) -> "Estimate":
        """Approved content is immutable; reopening creates a new revision."""
        if not self._approved:
            raise ValueError("only approved estimates need reopening")
        new = Estimate(
            title=self.title, lines=list(self.lines), stage=self.stage,
            disciplines=list(self.disciplines), status="draft",
            owner=self.owner, reviewer=self.reviewer,
            revision=self.revision + 1,
            assumptions=list(self.assumptions),
        )
        return new

    def edit_line_hours(self, index: int, hours: float) -> None:
        if self._approved:
            raise ValueError("approved content requires reopening — create a new revision")
        line = self.lines[index]
        self.lines[index] = WBSLine(
            deliverable=line.deliverable, task=line.task, hours=hours,
            confidence="High", confidence_score=90,
            source="engineer edit", resources=line.resources,
        )


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_tds(text: str, templates: list[dict]) -> tuple[list[str], str, list[str]]:
    """Find deliverables, stage, and disciplines named in the scope text."""
    lowered = text.lower()
    found = [t["name"] for t in templates if t["name"].lower() in lowered]
    stage = next((s for s in STAGES if s.lower() in lowered), "Detailed")
    disciplines = []
    if "mechanical" in lowered:
        disciplines.append("Mechanical")
    if "electrical" in lowered or "instrumentation" in lowered:
        disciplines.append("Electrical / I&C")
    return found, stage, disciplines


def confidence_for(score: float, matched: bool) -> tuple[str, int]:
    if matched and score >= 0.25:
        return "High", 85
    if matched and score >= 0.12:
        return "Medium", 60
    return "Low", 35


def build_estimate(tds_text: str, templates: list[dict], past: list[dict],
                   owner: str = "estimate-owner", reviewer: str = "assigned-reviewer") -> Estimate:
    deliverables, stage, disciplines = parse_tds(tds_text, templates)
    est = Estimate(title="Estimate from technical scope document",
                   stage=stage, disciplines=disciplines,
                   owner=owner, reviewer=reviewer)
    est.assumptions.append(
        "Hours depend on the scope as stated in the TDS, site access for the "
        "walkdown, and vendor information being available when required.")
    for name in deliverables:
        if name == "Project Management":
            continue
        template = next(t for t in templates if t["name"] == name)
        template_hours = sum(t["hours"] for t in template["tasks"])
        best, best_score = None, 0.0
        for p in past:
            if name not in p["deliverables"]:
                continue
            score = similarity(tds_text, p["scope"])
            if score > best_score:
                best, best_score = p, score
        matched = best is not None and best_score >= 0.12
        confidence, conf_score = confidence_for(best_score, matched)
        if matched:
            total = float(best["deliverables"][name])
            source = f"past estimate {best['id']} (similarity {best_score:.2f})"
        else:
            total = float(template_hours)
            source = "WBS template (no past estimate matched)"
        for task in template["tasks"]:
            share = task["hours"] / template_hours if template_hours else 0
            est.lines.append(WBSLine(
                deliverable=name, task=task["name"],
                hours=round(total * share, 1),
                confidence=confidence, confidence_score=conf_score,
                source=source))
    # Project Management: percentage of engineering hours, on the project.
    pm_template = next(t for t in templates if t["name"] == "Project Management")
    pm_total = round(est.engineering_hours * Estimate.PM_PCT, 1)
    pm_tasks = pm_template["tasks"]
    for task in pm_tasks:
        est.lines.append(WBSLine(
            deliverable="Project Management", task=task["name"],
            hours=round(pm_total / len(pm_tasks), 1),
            confidence="Medium", confidence_score=60,
            source="PM percentage of engineering hours"))
    return est


def hours_csv(est: Estimate) -> str:
    """SAP-style hours file: Description, Work (hrs), Unit, Work Center,
    Plant, Activity, Material. A file download, not a live SAP connection."""
    rows = ["Description,Work (hrs),Unit,Work Center,Plant,Activity,Material"]
    for line in est.lines:
        rows.append(
            f'"{line.deliverable} — {line.task}",{line.hours},HR,ENG,1000,ENG-DES,MAT-NONE')
    rows.append(f'"TOTAL",{est.total_hours},HR,,,,')
    return "\n".join(rows) + "\n"


def schedule_xml(est: Estimate) -> str:
    """P6-oriented schedule export: sequenced lines with durations in days."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<schedule>"]
    lines.append(f'  <estimate title="{est.title}" stage="{est.stage}" '
                 f'total_hours="{est.total_hours}" duration_days="{est.duration_days()}"/>')
    for i, line in enumerate(est.lines):
        pred = f' predecessor="{i}"' if i > 0 and line.deliverable == est.lines[i - 1].deliverable else ""
        lines.append(
            f'  <activity id="A{i + 1}" deliverable="{line.deliverable}" '
            f'task="{line.task}" hours="{line.hours}" '
            f'duration_days="{line.duration_days:.1f}"{pred}/>')
    lines.append("</schedule>")
    return "\n".join(lines) + "\n"
