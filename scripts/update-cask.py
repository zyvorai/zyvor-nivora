#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Set `version` and `sha256` in the Homebrew cask from package.json and a SHA256SUMS-style file.

usage: update-cask.py [SHA256SUMS.txt|Nivora-X.Y.Z.dmg.sha256]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASK = ROOT / "packaging/homebrew/nivora.rb"


def update(text, version, sha):
    text, n1 = re.subn(r'(?m)^(\s*version\s+)"[^"]*"', rf'\g<1>"{version}"', text)
    text, n2 = re.subn(r'(?m)^(\s*sha256\s+)"[^"]*"', rf'\g<1>"{sha}"', text)
    if n1 != 1 or n2 != 1:
        raise SystemExit("cask must contain exactly one version and one sha256 line")
    return text


def find_sha(sums, version):
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].endswith(f"Nivora-{version}.dmg"):
            return parts[0]
    raise SystemExit(f"no checksum for Nivora-{version}.dmg")


if __name__ == "__main__":
    version = json.loads((ROOT / "package.json").read_text())["version"]
    sums = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / f"Nivora-{version}.dmg.sha256").read_text()
    CASK.write_text(update(CASK.read_text(), version, find_sha(sums, version)))
    print(f"cask -> {version}")
