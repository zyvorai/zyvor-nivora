# SPDX-License-Identifier: BUSL-1.1
"""Attribute processes (and so flows) to a project folder via the process working directory."""
from __future__ import annotations

import os
from typing import Any

MARKERS = (".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Package.swift")


def parse_lsof_cwd(text: str) -> dict[int, str]:
    """Parse `lsof -nP -a -d cwd -Fpn` into {pid: cwd}."""
    out: dict[int, str] = {}
    pid = 0
    for line in text.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("n") and pid:
            out[pid] = line[1:]
    return out


def project_root(cwd: str, home: str | None = None, exists=os.path.exists) -> str:
    """Nearest ancestor of cwd (inside the home directory) holding a project marker, else ''."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    path = os.path.realpath(cwd)
    if path == home or not path.startswith(home + os.sep):
        return ""
    for _ in range(12):
        if any(exists(os.path.join(path, m)) for m in MARKERS):
            return path
        parent = os.path.dirname(path)
        if parent == path or parent == home or not parent.startswith(home):
            return ""
        path = parent
    return ""


def attribute_projects(flows: list[dict[str, Any]], cwd_by_pid: dict[int, str], home: str | None = None, exists=os.path.exists) -> list[dict[str, Any]]:
    cache: dict[str, str] = {}
    for f in flows:
        cwd = cwd_by_pid.get(int(f.get("pid") or 0))
        if not cwd:
            continue
        root = cache.get(cwd)
        if root is None:
            root = cache[cwd] = project_root(cwd, home, exists)
        if root:
            f["project"] = root
    return flows


def summarize_projects(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    b: dict[str, dict[str, Any]] = {}
    for f in flows:
        p = f.get("project")
        if not p:
            continue
        r = b.setdefault(p, {"project": p, "name": os.path.basename(p), "flows": 0, "bps": 0.0, "apps": set()})
        r["flows"] += 1
        r["bps"] += float(f.get("total_bps") or 0)
        r["apps"].add(f.get("process") or "Unknown")
    return sorted(({**r, "bps": round(r["bps"], 2), "apps": sorted(r["apps"])} for r in b.values()), key=lambda r: r["bps"], reverse=True)
