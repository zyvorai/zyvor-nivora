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

    def test_native_fixture_tracks_demo_collector_keys(self):
        """The XCTest fixture must carry every top-level key the demo collector emits."""
        import json, subprocess, sys, tempfile
        fixture = json.loads((ROOT / "native" / "Tests" / "Fixtures" / "demo-snapshot.json").read_text())
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run([sys.executable, str(ROOT / "agent" / "nivora.py"), "--demo", "--once",
                                  "--no-history", "--rules", f"{d}/rules.json"],
                                 capture_output=True, text=True, check=True).stdout
        self.assertEqual(set(json.loads(out)), set(fixture),
                         "regenerate native/Tests/Fixtures/demo-snapshot.json from `nivora.py --demo --once`")

    def test_capture_helper_is_shell_free_and_limits_match_collector(self):
        """The helper only execs tcpdump with a fixed argv; Swift and Python validators share limits."""
        helper = (ROOT / "native" / "CaptureHelper" / "main.swift").read_text()
        validator = (ROOT / "native" / "CaptureHelper" / "Validator.swift").read_text()
        for banned in ["/bin/sh", "/bin/bash", "system(", "popen(", "-c\""]:
            self.assertNotIn(banned, helper + validator)
        self.assertIn('static let tcpdump = "/usr/sbin/tcpdump"', helper)
        self.assertIn("getpeereid", helper)          # peer credentials are checked
        self.assertIn("0o700", helper)               # captures directory is root-only
        import sys
        sys.path.insert(0, str(ROOT / "agent"))
        import capture
        pairs = {
            "defaultSnaplen": capture.DEFAULT_SNAPLEN, "maxSnaplen": capture.MAX_SNAPLEN, "minSnaplen": capture.MIN_SNAPLEN,
            "defaultSeconds": capture.DEFAULT_SECONDS, "maxSeconds": capture.MAX_SECONDS,
            "defaultMB": capture.DEFAULT_MB, "maxMB": capture.MAX_MB,
        }
        for name, value in pairs.items():
            m = re.search(rf"{name} = (\d+)", validator)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1)), value, name)

    def test_every_local_collector_module_is_bundled_and_installed(self):
        """nivora.py imports sibling modules; the app bundle and the launchd installer must ship them all."""
        src = (ROOT / "agent" / "nivora.py").read_text()
        local = {p.stem for p in (ROOT / "agent").glob("*.py")} - {"nivora", "nivoractl"}
        needed = {m for m in re.findall(r"^(?:from|import) (\w+)", src, re.M) if m in local}
        self.assertTrue(needed, "expected sibling imports")
        project = (ROOT / "native" / "project.yml").read_text()
        installer = (ROOT / "scripts" / "install-macos.sh").read_text()
        for mod in needed:
            self.assertIn(f"../agent/{mod}.py", project, f"{mod}.py missing from the app bundle resources")
            self.assertIn(f"agent/{mod}.py", installer, f"{mod}.py missing from install-macos.sh")
        self.assertNotRegex(project, r"(?m)^    resources:", "xcodegen ignores a top-level resources: key; use sources with buildPhase: resources")
        self.assertRegex(project, r"(?s)path: \.\./web\s+type: folder\s+buildPhase: resources")

    def test_unsigned_install_is_documented_where_users_look(self):
        """Release builds are unsigned: the README, the site and docs/INSTALL.md must say so and say what to do."""
        install = (ROOT / "docs" / "INSTALL.md").read_text()
        for needle in ["not signed", "Open Anyway", "xattr -dr com.apple.quarantine", "SHA256SUMS"]:
            self.assertIn(needle.lower(), install.lower(), needle)
        self.assertIn("docs/INSTALL.md", (ROOT / "README.md").read_text())
        site = (ROOT / "site" / "index.html").read_text()
        self.assertIn("Open Anyway", site)
        self.assertIn("docs/install.html", site)  # the site's own copy of docs/INSTALL.md (scripts/build-docs.py)

    def test_release_version_is_single_sourced(self):
        """package.json, the collector, the Xcode project and the DMG script must agree."""
        import json
        version = json.loads((ROOT / "package.json").read_text())["version"]
        self.assertRegex((ROOT / "agent" / "nivora_core.py").read_text(), rf'VERSION = "{re.escape(version)}"')
        yml = (ROOT / "native" / "project.yml").read_text()
        self.assertIn(f"MARKETING_VERSION: {version}", yml)
        # xcodegen otherwise writes a literal 1.0 into Info.plist, so About/Finder showed the wrong version
        self.assertIn("CFBundleShortVersionString: $(MARKETING_VERSION)", yml)
        fixture = json.loads((ROOT / "native" / "Tests" / "Fixtures" / "demo-snapshot.json").read_text())
        self.assertEqual(fixture["version"], version, "regenerate native/Tests/Fixtures/demo-snapshot.json")
        self.assertIn("package.json", (ROOT / "scripts" / "package-dmg.sh").read_text())

    def test_release_workflow_checks_tag_and_stays_unsigned(self):
        wf = (ROOT / ".github" / "workflows" / "release.yml").read_text()
        self.assertIn("tags: ['v*']", wf)
        self.assertIn("package.json", wf)          # tag must match the version
        self.assertIn("--draft", wf)               # never publishes on its own
        self.assertIn("./scripts/package-dmg.sh", wf)
        self.assertNotIn("notarytool", wf)         # no signing claims without credentials

    def test_brand_assets_are_wired_in(self):
        """One master SVG; the icns, favicon and share image derive from it and are actually referenced."""
        for rel in ["docs/brand/nivora-icon.svg", "native/Nivora.icns", "web/favicon.svg",
                    "web/apple-touch-icon.png", "docs/social/og.png", "scripts/build-brand.sh"]:
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertEqual((ROOT / "docs/brand/nivora-icon.svg").read_text(), (ROOT / "web/favicon.svg").read_text())
        project = (ROOT / "native" / "project.yml").read_text()
        self.assertIn("path: Nivora.icns", project)
        self.assertIn("CFBundleIconFile: Nivora", project)
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('rel="icon" href="favicon.svg"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertEqual((ROOT / "native" / "Nivora.icns").read_bytes()[:4], b"icns")

    def test_zyvor_name_copyright_and_licence_match_vytrix(self):
        """Same owner, notice and licence wording as ../zyvor-vytrix, everywhere users look."""
        owner = "Zyvor AI Labs Private Limited"
        self.assertIn(f"Licensor: {owner}", (ROOT / "LICENSE").read_text())
        self.assertIn("Licensed Work: Zyvor Nivora", (ROOT / "LICENSE").read_text())
        self.assertIn(f"Copyright 2026 {owner}", (ROOT / "NOTICE").read_text())
        self.assertIn(f"NSHumanReadableCopyright: Copyright © 2026 {owner}.", (ROOT / "native" / "project.yml").read_text())
        self.assertIn(owner, (ROOT / "native" / "App" / "Views" / "WelcomeView.swift").read_text())
        self.assertIn(owner, (ROOT / "web" / "index.html").read_text())
        self.assertIn("BUSL-1.1", (ROOT / "scripts" / "build-brand.sh").read_text())

    def test_static_demo_data_tracks_collector_and_assets_are_relative(self):
        """web/demo-snapshot.json must carry the collector's top-level keys; the page must work under a sub-path."""
        import json, subprocess, sys, tempfile
        demo = json.loads((ROOT / "web" / "demo-snapshot.json").read_text())
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run([sys.executable, str(ROOT / "agent" / "nivora.py"), "--demo", "--once", "--no-history",
                                  "--rules", f"{d}/r.json"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(set(json.loads(out)), set(demo),
                         "regenerate web/demo-snapshot.json from `nivora.py --demo --once --no-history`")
        html = (ROOT / "web" / "index.html").read_text()
        for needle in ('href="styles.css"', 'src="demo.js"', 'src="app.js"'):
            self.assertIn(needle, html)
        self.assertIn("from './lib.js'", (ROOT / "web" / "app.js").read_text())
        self.assertLess(html.index('src="demo.js"'), html.index('src="app.js"'))

    def test_pages_workflow_and_site_basics(self):
        wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
        for needle in ("actions/deploy-pages", "actions/upload-pages-artifact", "./scripts/build-site.sh", "scripts/site-check.mjs", "pages: write"):
            self.assertIn(needle, wf)
        site = (ROOT / "site" / "index.html").read_text()
        self.assertIn("© 2026 Zyvor AI Labs Private Limited", site)
        self.assertIn("BUSL-1.1", site)
        self.assertIn("Zyvor Nivora", site)
        for rel in ("site/site.css", "site/site.js", "site/theme.js", "site/404.html", "site/robots.txt", "site/sitemap.xml"):
            self.assertTrue((ROOT / rel).is_file(), rel)
        # honest claims: the only affirmative notarisation claim is the signed (paid) build's card, which
        # scripts/package-signed.sh really notarizes; every other mention (free builds, developer build) is a negation.
        self.assertIn("unsigned", site.lower())
        cards = site.split('<div class="card">')
        signed_card = [c for c in cards if 'id="buy-signed"' in c]
        self.assertEqual(len(signed_card), 1, "exactly one card sells the signed build")
        rest = site.replace(signed_card[0], "").lower()
        for m in re.finditer(r"notari[sz]", rest):
            before = rest[max(0, m.start() - 60):m.start()]
            self.assertTrue("not " in before or "cannot" in before or "n't" in before,
                            f"affirmative notarisation claim outside the signed build card: ...{before}{rest[m.start():m.start()+14]}")

    def test_readme_images_exist_and_legal_matches_vytrix(self):
        readme = (ROOT / "README.md").read_text()
        refs = re.findall(r"!\[[^\]]*\]\(([^)#]+)\)|<img[^>]+src=\"([^\"]+)\"", readme)
        local = [a or b for a, b in refs if not (a or b).startswith("http")]
        self.assertTrue(local, "README should show screenshots")
        for rel in local:
            self.assertTrue((ROOT / rel).is_file(), f"README references missing image {rel}")
        self.assertIn("Business Source License 1.1", readme)
        self.assertIn("Copyright © 2026 Zyvor AI Labs Private Limited", readme)
        self.assertIn("commercial license from Zyvor AI Labs Private Limited", readme)
        self.assertIn("unsigned", readme.lower())      # honest about signing
        self.assertIn("https://zyvorai.github.io/zyvor-nivora/demo/", readme)

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
