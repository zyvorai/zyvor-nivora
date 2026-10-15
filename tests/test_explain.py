# SPDX-License-Identifier: BUSL-1.1
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from explain import explain_flow, rule_impact
from nivora_core import RuleStore, apply_rule_preview, demo_snapshot


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self.snap = demo_snapshot()
        self.flow = self.snap["flows"][0]

    def test_explain_known_flow(self):
        out = explain_flow(self.snap, self.flow["id"])
        self.assertEqual(out["app"], self.flow["process"])
        self.assertTrue(out["reasons"][0].startswith(self.flow["process"]))
        self.assertGreaterEqual(out["traffic_share_percent"], 0)

    def test_explain_unknown_flow(self):
        self.assertIsNone(explain_flow(self.snap, "nope"))

    def test_shadow_rule_counts_but_is_not_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(str(Path(d) / "rules.json"))
            rule = store.add({"action": "shadow", "app": self.flow["process"]})
            self.assertNotIn("expires_at", rule)
            rules = store.list()
        hits = apply_rule_preview(self.snap["flows"], rules)
        impact = rule_impact(self.snap["flows"], rules, hits)
        self.assertEqual(len(impact), 1)
        self.assertFalse(impact[0]["enforced"])
        self.assertTrue(impact[0]["would_block"])
        self.assertGreaterEqual(impact[0]["flows"], 1)

    def test_block_rule_is_enforced_and_leased(self):
        with tempfile.TemporaryDirectory() as d:
            rule = RuleStore(str(Path(d) / "rules.json")).add({"action": "block", "domain": "example.com"})
        self.assertIn("expires_at", rule)


if __name__ == "__main__":
    unittest.main()
