"""Tests for plan_explain.py — standard library only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import plan_explain

CLEAN = {
    "id": "plan-test",
    "version": 2,
    "goal": "Summarise two source papers for a reviewer",
    "constraints": ["Do not share the papers outside the team"],
    "assumptions": ["Both papers are available as PDFs"],
    "steps": [
        {"id": "s1", "action": "Fetch the two source papers",
         "why": "The summary must come from the papers, not memory",
         "estimate": {"minutes": 5, "usd": 0.10}},
        {"id": "s2", "action": "Count words per section",
         "why": "Section lengths show where the papers spend their effort",
         "estimate": {"minutes": 10, "usd": 0.20}},
        {"id": "s3", "action": "Summarise the findings",
         "why": "The reviewer asked for a one-page summary",
         "estimate": {"minutes": 15, "usd": 1.20}},
        {"id": "s4", "action": "Send the summary to the reviewer",
         "why": "The reviewer is waiting for it",
         "estimate": {"minutes": 5, "usd": 0.40},
         "permission_gated": True, "irreversible": True,
         "failure_points": ["Reviewer address wrong"]},
    ],
}


def risky_plan():
    return {
        "id": "plan-risky-test",
        "version": 1,
        "goal": "Publish the weekly digest to the public list",
        "steps": [
            {"id": "s1", "action": "Draft the digest",
             "why": "The list expects it every Friday",
             "estimate": {"minutes": 20, "usd": 0.50}},
            {"id": "s2", "action": "Publish the digest to the public list",
             "irreversible": True,
             "estimate": {"minutes": 5, "usd": 6.00}},
        ],
    }


class TestExplain(unittest.TestCase):
    def test_summary_names_goal_and_step_count(self):
        exp = plan_explain.explain(CLEAN)
        self.assertIn("Summarise two source papers", exp["summary"])
        self.assertIn("4 steps", exp["summary"])

    def test_gated_irreversible_step_wording(self):
        exp = plan_explain.explain(CLEAN)
        s4 = exp["steps"][3]["text"]
        self.assertIn("cannot be undone", s4)
        self.assertIn("waits for your permission", s4)

    def test_ungated_irreversible_is_high_concern(self):
        exp = plan_explain.explain(risky_plan())
        highs = [c for c in exp["concerns"] if c["severity"] == "HIGH"]
        self.assertEqual(len(highs), 1)
        self.assertIn("s2", highs[0]["text"])
        self.assertIn("Do not approve", exp["bottom_line"])

    def test_step_without_why_is_medium_concern(self):
        exp = plan_explain.explain(risky_plan())
        mediums = [c["text"] for c in exp["concerns"]
                   if c["severity"] == "MEDIUM"]
        self.assertTrue(any("s2" in t and "no reason" in t for t in mediums))

    def test_unpriced_step_is_unknown_not_zero(self):
        plan = json.loads(json.dumps(CLEAN))
        del plan["steps"][1]["estimate"]
        exp = plan_explain.explain(plan)
        self.assertEqual(exp["cost"]["unknown_steps"], ["s2"])
        self.assertEqual(exp["cost"]["total_usd"], 1.70)
        self.assertTrue(any("unknown" in c["text"].lower()
                            for c in exp["concerns"]))

    def test_cost_totals_add_up(self):
        exp = plan_explain.explain(CLEAN)
        self.assertEqual(exp["cost"]["total_usd"], 1.90)
        self.assertEqual(exp["cost"]["total_minutes"], 35)
        self.assertEqual(exp["cost"]["unknown_steps"], [])

    def test_no_constraints_is_medium_concern(self):
        exp = plan_explain.explain(risky_plan())
        self.assertTrue(any("no constraints" in c["text"]
                            for c in exp["concerns"]))

    def test_clean_plan_bottom_line_is_clear(self):
        exp = plan_explain.explain(CLEAN)
        self.assertEqual(exp["concerns"], [])
        self.assertIn("Nothing in this plan needs a warning",
                      exp["bottom_line"])

    def test_markdown_render_has_all_sections(self):
        md = plan_explain.render_markdown(plan_explain.explain(CLEAN))
        for heading in ("What it will do", "What it will cost",
                        "What could go wrong", "Before you decide",
                        "Bottom line"):
            self.assertIn(heading, md)
        self.assertIn("$1.90", md)

    def test_cli_missing_file_exits_2(self):
        here = os.path.dirname(os.path.abspath(__file__))
        tool = os.path.join(here, "..", "plan_explain.py")
        result = subprocess.run(
            [sys.executable, tool, "no-such-plan.json"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
