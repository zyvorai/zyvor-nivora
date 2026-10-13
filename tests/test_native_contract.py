# SPDX-License-Identifier: BUSL-1.1
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class NativeContractTests(unittest.TestCase):
    def test_rule_matcher_is_allow_first_and_expiry_aware(self):
        source = (ROOT / "native" / "FilterData" / "FilterDataProvider.swift").read_text()
        allow = source.index('rule.action == "allow"')
        block = source.index('rule.action == "block"')
        self.assertLess(allow, block, "explicit allow must be evaluated before broader block")
        self.assertIn("expires_at", source)
        self.assertIn("matches(rule,", source)

    def test_native_palette_matches_web_tokens(self):
        """Native Palette (Theme.swift) and web CSS tokens are both the Netra palette."""
        swift = (ROOT / "native" / "App" / "Views" / "Theme.swift").read_text()
        css = (ROOT / "web" / "styles.css").read_text()
        pairs = re.findall(r'static let (\w+) = Color\(light: "(#[0-9a-f]{6})", dark: "(#[0-9a-f]{6})"\)', swift)
        palette = {n: (l, d) for n, l, d in pairs}
        def token(name, scope):
            m = re.search(r"--%s:(#[0-9a-fA-F]{6})" % re.escape(name), scope)
            return m.group(1).lower() if m else None
        light = css[: css.index("@media(prefers-color-scheme:dark)")]
        dark = css[css.index('html[data-theme="dark"]{'):]
        expected = {"textPrimary": "text", "textSecondary": "text-secondary", "accent": "blue", "cyan": "cyan",
                    "green": "green", "amber": "orange", "purple": "purple", "danger": "red", "panel": "bg-elevated-2"}
        for swift_name, css_name in expected.items():
            self.assertIn(swift_name, palette, swift_name)
            self.assertEqual(palette[swift_name][0], token(css_name, light), f"light {swift_name}")
        for swift_name, css_name in {"textPrimary": "text", "textSecondary": "text-secondary", "accent": "blue",
                                    "cyan": "cyan", "green": "green", "purple": "purple", "danger": "red", "page": "bg"}.items():
            self.assertEqual(palette[swift_name][1], token(css_name, dark), f"dark {swift_name}")
        self.assertEqual(palette["page"][0], "#ffffff")

    def test_network_extension_uses_macos_apis(self):
        sources = "".join(p.read_text() for d in ("Shared", "FilterData") for p in (ROOT / "native" / d).glob("*.swift"))
        for banned in ("sourceAppIdentifier", "NEFilterControlProvider", ".remoteEndpoint", ".localEndpoint"):
            self.assertNotIn(banned, sources, banned)
        self.assertIn("sourceAppAuditToken", sources)
        self.assertIn("startSystemExtensionMode", (ROOT / "native" / "FilterData" / "main.swift").read_text())
        self.assertFalse((ROOT / "native" / "FilterControl").exists())
        project = (ROOT / "native" / "project.yml").read_text()
        self.assertIn("type: system-extension", project)
        self.assertIn("content-filter-provider-systemextension", project)
        self.assertIn("com.apple.developer.system-extension.install", project)
        self.assertIn("com.apple.networkextension.filter-data", project)

    def test_native_app_is_split_like_vytrix(self):
        for rel in ("NivoraApp.swift", "Model/NivoraStore.swift", "Model/Preferences.swift", "Model/Alerts.swift",
                    "Model/CollectorProcess.swift", "Views/RootView.swift", "Views/Components.swift", "Views/Theme.swift",
                    "Views/SettingsView.swift", "Views/MenuBarView.swift"):
            self.assertTrue((ROOT / "native" / "App" / rel).is_file(), rel)
        app = (ROOT / "native" / "App" / "NivoraApp.swift").read_text()
        self.assertIn("--appearance", app)
        self.assertIn("--section", app)

    def test_native_accents_match_web_accents(self):
        swift = (ROOT / "native" / "App" / "Model" / "Preferences.swift").read_text()
        lib = (ROOT / "web" / "lib.js").read_text()
        web = dict(re.findall(r"(\w+): '(#[0-9a-f]{6})'", re.search(r"ACCENTS = \{([^}]*)\}", lib).group(1)))
        native = dict(re.findall(r'case \.(\w+): return Color\(hex: "(#[0-9a-f]{6})"\)', swift))
        self.assertEqual(web, native)

    def test_sources_carry_spdx_and_license_matches_vytrix_terms(self):
        tag = "SPDX-License-Identifier: BUSL-1.1"
        missing = []
        for pattern in ("agent/*.py", "tests/*.py", "scripts/*.sh", "web/*.js", "native/**/*.swift", "tests/*.mjs"):
            for path in ROOT.glob(pattern):
                if tag not in "".join(path.read_text().splitlines(True)[:3]):
                    missing.append(str(path.relative_to(ROOT)))
        self.assertEqual(missing, [])
        text = (ROOT / "LICENSE").read_text()
        for needle in ("Business Source License 1.1", "Licensor: Zyvor AI Labs Private Limited",
                       "Additional Use Grant: None", "Change License: Apache License 2.0"):
            self.assertIn(needle, text)

if __name__ == "__main__":
    unittest.main()
