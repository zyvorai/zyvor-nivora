# SPDX-License-Identifier: BUSL-1.1
"""Port ownership and conflict detection over snapshot listeners."""
from __future__ import annotations

from typing import Any


def _groups(listeners: list[dict[str, Any]]) -> dict[tuple[str, int], dict[int, dict[str, Any]]]:
    groups: dict[tuple[str, int], dict[int, dict[str, Any]]] = {}
    for l in listeners:
        port = int(l.get("port") or 0)
        if port <= 0:
            continue
        key = (str(l.get("protocol") or ""), port)
        groups.setdefault(key, {}).setdefault(int(l.get("pid") or 0), l)
    return groups


def find_conflicts(listeners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ports bound by more than one distinct process for the same protocol."""
    out = []
    for (proto, port), owners in _groups(listeners).items():
        if len(owners) < 2:
            continue
        out.append({
            "port": port, "protocol": proto,
            "severity": "warning" if len(owners) == 2 else "critical",
            "owners": [{"process": o.get("process"), "pid": o.get("pid"), "address": o.get("address")} for o in owners.values()],
        })
    return sorted(out, key=lambda c: (c["port"], c["protocol"]))


def annotate_listeners(listeners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicted = {(c["protocol"], c["port"]) for c in find_conflicts(listeners)}
    for l in listeners:
        l["conflict"] = (str(l.get("protocol") or ""), int(l.get("port") or 0)) in conflicted
    return listeners
