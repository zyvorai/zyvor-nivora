# SPDX-License-Identifier: BUSL-1.1
import pathlib, re, subprocess, tempfile, unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "install-macos.sh"


class InstallScriptTests(unittest.TestCase):
    def test_run_collector_has_no_literal_escaped_quotes(self):
        src = SCRIPT.read_text()
        m = re.search(r'<<EOF\n(#!/bin/bash\n.*?)\nEOF\n', src, re.S)
        self.assertIsNotNone(m)
        with tempfile.TemporaryDirectory() as d:
            appdir = f"{d}/Application Support/Nivora"
            out = subprocess.run(
                ["bash", "-c", f'APPDIR="$1"; PORT=9857; cat <<EOF\n{m.group(1)}\nEOF', "x", appdir],
                capture_output=True, text=True, check=True).stdout
            self.assertNotIn('\\"', out)
            self.assertIn(f'"{appdir}/agent/nivora.py"', out)
            self.assertIn('--port "9857"', out)
            subprocess.run(["bash", "-n"], input=out, text=True, check=True)


if __name__ == "__main__":
    unittest.main()
