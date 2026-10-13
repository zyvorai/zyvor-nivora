# SPDX-License-Identifier: BUSL-1.1
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from nivora_core import filter_flows, parse_filter  # noqa: E402

VECTORS = json.loads((ROOT / "tests" / "fixtures" / "filter-vectors.json").read_text())


class FilterTests(unittest.TestCase):
    def test_shared_vectors(self):
        for case in VECTORS["cases"]:
            got = [f["id"] for f in filter_flows(VECTORS["flows"], case["q"])]
            self.assertEqual(got, case["expect"], case["q"])

    def test_parse_shapes(self):
        terms = parse_filter('app:"Google Chrome" !port:22 >1mbps')
        self.assertEqual([t["kind"] for t in terms], ["app", "port", "rate"])
        self.assertEqual(terms[0]["value"], "google chrome")
        self.assertTrue(terms[1]["negate"])
        self.assertEqual(terms[2]["bits"], 1e6)


if __name__ == "__main__":
    unittest.main()
