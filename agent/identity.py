# SPDX-License-Identifier: BUSL-1.1
"""Executable path and code-signing identity for flows (best effort, cached, read-only)."""
from __future__ import annotations

import re
import subprocess
from typing import Any, Callable


def parse_ps(text: str) -> dict[int, str]:
    """Parse `ps -axo pid=,comm=` into {pid: executable path}."""
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+?)\s*$", line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def parse_codesign(text: str, returncode: int = 0) -> dict[str, Any]:
    """Interpret `codesign -dv --verbose=2` output (it writes to stderr)."""
    if "not signed at all" in text:
        return {"signed": False, "adhoc": False, "apple": False, "team_id": "", "authority": ""}
    fields = dict(m.groups() for m in re.finditer(r"^(\w+)=(.*)$", text, re.M))
    authorities = re.findall(r"^Authority=(.*)$", text, re.M)
    team = fields.get("TeamIdentifier", "")
    adhoc = "adhoc" in fields.get("Signature", "").lower() or "flags=0x2(adhoc)" in text
    if returncode != 0 and not fields:
        return {"signed": False, "adhoc": False, "apple": False, "team_id": "", "authority": "", "unknown": True}
    return {
        "signed": True, "adhoc": adhoc,
        "apple": any(a.startswith(("Software Signing", "Apple Root CA", "Apple Code Signing")) for a in authorities) or fields.get("Identifier", "").startswith("com.apple."),
        "team_id": "" if team == "not set" else team,
        "authority": authorities[0] if authorities else "",
    }


def _run_codesign(path: str) -> tuple[str, int]:
    try:
        p = subprocess.run(["codesign", "-dv", "--verbose=2", path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=2, check=False)
        return p.stderr, p.returncode
    except (OSError, subprocess.TimeoutExpired):
        return "", 1


class IdentityResolver:
    def __init__(self, run: Callable[[str], tuple[str, int]] = _run_codesign, budget: int = 12):
        self.run, self.budget, self.cache = run, budget, {}

    def annotate(self, flows: list[dict[str, Any]], ps_text: str) -> list[dict[str, Any]]:
        paths = parse_ps(ps_text)
        left = self.budget
        for f in flows:
            path = paths.get(int(f.get("pid") or 0))
            if not path:
                continue
            f["path"] = path
            if path not in self.cache:
                if left <= 0:
                    continue
                left -= 1
                self.cache[path] = parse_codesign(*self.run(path))
            f["identity"] = self.cache[path]
        return flows


def identity_findings(flows: list[dict[str, Any]], is_internet: Callable[[str], bool]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for f in flows:
        ident = f.get("identity")
        if not ident or ident.get("unknown") or ident.get("signed") and not ident.get("adhoc"):
            continue
        if not is_internet(f.get("remote", "")):
            continue
        seen.setdefault(f.get("process") or "Unknown", f)
    out = []
    for app, f in seen.items():
        ident = f["identity"]
        kind = "ad-hoc signed" if ident.get("signed") else "unsigned"
        out.append({"severity": "info" if ident.get("signed") else "warning", "kind": "identity",
                    "title": f"{kind.capitalize()} binary contacting the internet",
                    "detail": f"{app} ({f.get('path', 'unknown path')}) is {kind}.", "app": app})
    return out[:10]
