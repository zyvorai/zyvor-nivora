# SPDX-License-Identifier: BUSL-1.1
"""Native panes and web views must not drift apart silently.

Differences are allowed only if listed below, so adding a pane on one side
fails this test until the other side (or this list) is updated.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Intentional gaps, tracked for the native-parity work. Shrink these, never grow them quietly.
WEB_ONLY = {"map", "domains", "dns", "routes", "vpn"}
NATIVE_ONLY = {"alerts"}


def native_panes():
    src = (ROOT / "native/App/Model/NivoraStore.swift").read_text()
    body = src.split("enum Pane: String", 1)[1].split("var id:", 1)[0]
    names = set()
    for line in body.splitlines():
        if line.strip().startswith("case "):
            names.update(re.findall(r"(\w+)\s*=\s*\"", line))
    return names


def web_views():
    html = (ROOT / "web/index.html").read_text()
    return set(re.findall(r'<button data-view="(\w+)"', html))


class PaneParity(unittest.TestCase):
    def test_sets_are_parsed(self):
        self.assertGreaterEqual(len(native_panes()), 10)
        self.assertGreaterEqual(len(web_views()), 10)

    def test_differences_are_the_documented_ones(self):
        native, web = native_panes(), web_views()
        self.assertEqual(web - native, WEB_ONLY)
        self.assertEqual(native - web, NATIVE_ONLY)


if __name__ == "__main__":
    unittest.main()
