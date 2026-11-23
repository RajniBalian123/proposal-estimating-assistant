"""Checks for matching, confidence, scheduling, and review rules."""

import unittest
from pathlib import Path

from src.estimate import (
    build_estimate,
    confidence_for,
    hours_csv,
    load_json,
    parse_tds,
    schedule_xml,
    similarity,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = load_json(ROOT / "data" / "wbs_templates.json")["deliverable_types"]
PAST = load_json(ROOT / "data" / "past_estimates.json")
TDS = (ROOT / "data" / "sample_tds.md").read_text(encoding="utf-8")


class TestMatching(unittest.TestCase):
    def test_similarity_is_symmetric_and_bounded(self):
        s = similarity(TDS, PAST[0]["scope"])
        self.assertGreater(s, 0.0)
        self.assertLessEqual(s, 1.0)
        self.assertEqual(s, similarity(PAST[0]["scope"], TDS))

    def test_parse_finds_deliverables_stage_disciplines(self):
        found, stage, disciplines = parse_tds(TDS, TEMPLATES)
        self.assertIn("Walkdown Report", found)
        self.assertIn("Technical Specification", found)
        self.assertEqual(stage, "Detailed")
        self.assertIn("Mechanical", disciplines)


class TestConfidence(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(confidence_for(0.30, True), ("High", 85))
        self.assertEqual(confidence_for(0.15, True), ("Medium", 60))
        self.assertEqual(confidence_for(0.30, False), ("Low", 35))
        self.assertEqual(confidence_for(0.05, True), ("Low", 35))

    def test_low_confidence_rows_are_visible_not_hidden(self):
        est = build_estimate(TDS, TEMPLATES, PAST)
        self.assertTrue(all(l.confidence in ("High", "Medium", "Low") for l in est.lines))
        self.assertEqual(len(est.low_confidence_lines),
                         sum(1 for l in est.lines if l.confidence == "Low"))


class TestEstimate(unittest.TestCase):
    def test_total_is_engineering_plus_pm(self):
        est = build_estimate(TDS, TEMPLATES, PAST)
        self.assertAlmostEqual(est.total_hours, est.engineering_hours + est.pm_hours, places=1)
        self.assertAlmostEqual(est.pm_hours, round(est.engineering_hours * 0.10, 1), places=1)

    def test_schedule_duration_is_positive(self):
        est = build_estimate(TDS, TEMPLATES, PAST)
        self.assertGreater(est.duration_days(), 0)

    def test_exports_contain_every_line(self):
        est = build_estimate(TDS, TEMPLATES, PAST)
        csv = hours_csv(est)
        self.assertIn("TOTAL", csv)
        self.assertIn("Walkdown Report", csv)
        xml = schedule_xml(est)
        self.assertIn("<schedule>", xml)
        self.assertIn("duration_days", xml)


class TestReview(unittest.TestCase):
    def test_owner_cannot_approve_own_estimate(self):
        est = build_estimate(TDS, TEMPLATES, PAST, owner="a", reviewer="b")
        est.submit()
        with self.assertRaises(ValueError):
            est.approve("a")

    def test_approved_content_requires_reopening(self):
        est = build_estimate(TDS, TEMPLATES, PAST, owner="a", reviewer="b")
        est.submit()
        est.approve("b")
        self.assertEqual(est.status, "approved")
        with self.assertRaises(ValueError):
            est.edit_line_hours(0, 1)
        reopened = est.reopen()
        self.assertEqual(reopened.revision, 2)
        self.assertEqual(reopened.status, "draft")


if __name__ == "__main__":
    unittest.main()
