# SPDX-License-Identifier: BUSL-1.1
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReleaseTools(unittest.TestCase):
    def test_sbom_matches_package_version(self):
        bom = load("build-sbom").build()
        self.assertEqual(bom["bomFormat"], "CycloneDX")
        self.assertEqual(bom["metadata"]["component"]["version"],
                         json.loads((ROOT / "package.json").read_text())["version"])

    def test_cask_update(self):
        mod = load("update-cask")
        src = 'cask "x" do\n  version "0.1.0"\n  sha256  "aa"\nend\n'
        out = mod.update(src, "0.2.0", "bb")
        self.assertIn('version "0.2.0"', out)
        self.assertIn('sha256  "bb"', out)
        self.assertEqual(mod.find_sha("bb  /p/Nivora-0.2.0.dmg\n", "0.2.0"), "bb")
        with self.assertRaises(SystemExit):
            mod.find_sha("bb  Nivora-0.1.0.dmg", "0.2.0")

    def test_cask_matches_package_version(self):
        cask = (ROOT / "packaging/homebrew/nivora.rb").read_text()
        ver = json.loads((ROOT / "package.json").read_text())["version"]
        self.assertIn(f'version "{ver}"', cask)


class NotarizeAndPagesTests(unittest.TestCase):
    def test_notarize_dry_run_touches_nothing_and_is_valid_bash(self):
        out = subprocess.run([str(ROOT / "scripts/notarize-mini.sh"), "--dry-run"], capture_output=True, text=True, check=True).stdout
        ver = json.loads((ROOT / "package.json").read_text())["version"]
        self.assertIn("Developer ID Application: ZYVORAI LABS PRIVATE LIMITED (NX667LTDQ2)", out)
        self.assertIn("Macora-Notary", out)
        self.assertIn(f"Nivora-{ver}.dmg", out)
        for needed in ("--options runtime", "notarytool submit", "stapler staple", "spctl --assess"):
            self.assertIn(needed, out)
        script = out[out.index("#!/usr/bin/env bash"):]
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_notarize_never_handles_the_api_key(self):
        src = (ROOT / "scripts/notarize-mini.sh").read_text()
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn(".p8", code)
        self.assertNotIn("Downloads", code)
        self.assertNotIn("--deep \"$APP_ID", code)

    def test_pages_runner_falls_back_to_github_hosted(self):
        wf = (ROOT / ".github/workflows/pages.yml").read_text()
        self.assertIn("vars.PAGES_RUNNER", wf)
        self.assertIn("'ubuntu-latest'", wf)
        self.assertNotIn("runs-on:  [self-hosted", wf)


if __name__ == "__main__":
    unittest.main()
