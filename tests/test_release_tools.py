# SPDX-License-Identifier: BUSL-1.1
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
