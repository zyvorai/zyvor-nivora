# SPDX-License-Identifier: BUSL-1.1
import importlib.util
import sys
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("site_terminal", Path(__file__).resolve().parents[1] / "scripts" / "build-site-terminal.py")
st = importlib.util.module_from_spec(spec)
sys.modules["site_terminal"] = st
spec.loader.exec_module(st)


class TerminalTests(unittest.TestCase):
    def test_terminal_html_escapes_and_hides_other_tabs(self):
        out = st.terminal_html([("a", "$ x <script>alert(1)</script>"), ("b", "second")])
        self.assertNotIn("<script>", out)
        self.assertEqual(out.count("hidden"), 1)
        self.assertEqual(st.terminal_html([]), "")

    def test_maturity_comes_from_readme_and_marks_unverified(self):
        out = st.maturity_html()
        self.assertIn("Content filter", out)
        self.assertIn('class="no"', out)  # at least one row is not fully verified
        self.assertNotIn("**", out)

    def test_capture_runs_real_cli_output(self):
        tabs = dict(st.capture())
        self.assertEqual(set(tabs), {"health", "trust", "explain", "policy"})
        self.assertIn('"score"', tabs["health"])
        self.assertIn("dry_run", tabs["policy"])


if __name__ == "__main__":
    unittest.main()
