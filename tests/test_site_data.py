# SPDX-License-Identifier: BUSL-1.1
import importlib.util
import sys
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("site_data", Path(__file__).resolve().parents[1] / "scripts" / "build-site-data.py")
site_data = importlib.util.module_from_spec(spec)
sys.modules["site_data"] = site_data
spec.loader.exec_module(site_data)

CHANGELOG = """# Changelog

## Unreleased

- not shown

## 0.5.1 — 2026-10-15

- Fix: a wrapped
  continuation line with `code` and <script>x</script>
- Second **bold** item

## 0.5.0 — 2026-10-14

- Older
"""
SHA = "a" * 64


class SiteDataTests(unittest.TestCase):
    def test_changelog_parsing(self):
        r = site_data.parse_changelog(CHANGELOG)
        self.assertEqual([x["version"] for x in r], ["0.5.1", "0.5.0"])
        self.assertEqual(len(r[0]["items"]), 2)
        self.assertIn("continuation line", r[0]["items"][0])

    def test_inline_escapes_html(self):
        out = site_data.inline("`x` <script>alert(1)</script> **b**")
        self.assertNotIn("<script>", out)
        self.assertIn("<code>x</code>", out)
        self.assertIn("<b>b</b>", out)

    def test_checksum_only_for_matching_file(self):
        sums = f"{SHA}  Nivora-0.5.1.dmg\n{'b' * 64}  other.dmg\n"
        self.assertEqual(site_data.checksum_for("0.5.1", sums), SHA)
        self.assertEqual(site_data.checksum_for("0.5.2", sums), "")
        self.assertEqual(site_data.checksum_for("0.5.1", "not a checksum file"), "")

    def test_download_block_never_invents_a_hash(self):
        self.assertNotIn("shasum", site_data.download_block("0.5.1", ""))
        self.assertIn(SHA, site_data.download_block("0.5.1", SHA))
        self.assertIn("releases/download/v0.5.1/Nivora-0.5.1.dmg", site_data.download_block("0.5.1", SHA))

    def test_feed_is_wellformed_and_escaped(self):
        import xml.dom.minidom
        xml.dom.minidom.parseString(site_data.feed(site_data.parse_changelog(CHANGELOG)))


if __name__ == "__main__":
    unittest.main()
