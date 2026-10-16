# SPDX-License-Identifier: BUSL-1.1
"""What did this sandbox or VM reach? Per-workload egress from FluxVM network data, observation only."""
from __future__ import annotations

from typing import Any

from nivora_core import classify_remote, endpoint_host


def _hubble(fluxvm: dict[str, Any]) -> list[dict[str, Any]]:
    h = fluxvm.get("hubble_flows")
    if isinstance(h, dict):
        h = h.get("flows")
    return [x for x in h if isinstance(x, dict)] if isinstance(h, list) else []


def _workloads(fluxvm: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for kind in ("vms", "sandboxes"):
        src = fluxvm.get(kind) or []
        if isinstance(src, dict):
            src = src.get("items") or []
        for w in src:
            if isinstance(w, dict) and w.get("id"):
                out.append({"id": str(w["id"]), "kind": kind[:-1], "state": w.get("state"), "backend": w.get("backend")})
    ends = fluxvm.get("network_endpoints") or []
    if isinstance(ends, dict):
        ends = ends.get("items") or []
    known = {w["id"] for w in out}
    for e in ends:
        if isinstance(e, dict) and e.get("id") and str(e["id"]) not in known:
            out.append({"id": str(e["id"]), "kind": "endpoint", "state": e.get("state"), "backend": None})
    return out


def egress_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    fx = snapshot.get("fluxvm") or {}
    if not fx.get("connected"):
        return {"connected": False, "workloads": [], "note": "FluxVM did not answer on the configured API endpoint."}
    dests: dict[str, dict[str, int]] = {}
    for fl in _hubble(fx):
        src = str(fl.get("source") or "")
        dst = endpoint_host(str(fl.get("destination") or ""))
        if src and dst:
            dests.setdefault(src, {})
            dests[src][dst] = dests[src].get(dst, 0) + 1
    workloads = _workloads(fx)
    for src in dests:
        if src not in {w["id"] for w in workloads}:
            workloads.append({"id": src, "kind": "unknown", "state": None, "backend": None})
    for w in workloads:
        rows = [{"host": h, "count": c, "scope": classify_remote(h)} for h, c in sorted(dests.get(w["id"], {}).items(), key=lambda x: -x[1])]
        w["destinations"] = rows[:50]
        w["external"] = sum(1 for r in rows if r["scope"] == "internet")
    return {"connected": True, "workloads": sorted(workloads, key=lambda w: -w["external"]),
            "host_flows": fx.get("host_flow_count", 0)}
