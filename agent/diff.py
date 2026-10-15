# SPDX-License-Identifier: BUSL-1.1
"""Compare two snapshots ("what is different from when it worked") and narrate a time window."""
from __future__ import annotations

from typing import Any

from nivora_core import endpoint_host


def _flow_keys(s: dict[str, Any]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for f in s.get("flows") or []:
        k = (f.get("process") or "Unknown", endpoint_host(f.get("remote", "")) or f.get("remote", ""))
        out[k] = out.get(k, 0.0) + float(f.get("total_bps") or 0)
    return out


def _listener_keys(s: dict[str, Any]) -> set[tuple[Any, ...]]:
    return {(l.get("process"), l.get("protocol"), l.get("port"), l.get("exposure")) for l in s.get("listeners") or []}


def _default_routes(s: dict[str, Any]) -> set[tuple[Any, ...]]:
    return {(r.get("family"), r.get("gateway"), r.get("interface")) for r in s.get("routes") or [] if r.get("default")}


def diff_snapshots(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Changes from snapshot `a` (earlier) to `b` (later)."""
    fa, fb = _flow_keys(a), _flow_keys(b)
    apps_a = {x.get("name"): float(x.get("rx_bps") or 0) + float(x.get("tx_bps") or 0) for x in a.get("apps") or []}
    apps_b = {x.get("name"): float(x.get("rx_bps") or 0) + float(x.get("tx_bps") or 0) for x in b.get("apps") or []}
    movers = sorted(({"app": n, "before_bps": round(apps_a.get(n, 0), 1), "after_bps": round(apps_b.get(n, 0), 1),
                      "delta_bps": round(apps_b.get(n, 0) - apps_a.get(n, 0), 1)} for n in set(apps_a) | set(apps_b)),
                    key=lambda x: abs(x["delta_bps"]), reverse=True)
    la, lb = _listener_keys(a), _listener_keys(b)
    da, db = set((a.get("dns") or {}).get("servers") or []), set((b.get("dns") or {}).get("servers") or [])
    na = {n.get("mac") or n.get("ip") for n in a.get("neighbors") or []}
    nb = {n.get("mac") or n.get("ip") for n in b.get("neighbors") or []}
    ta = {(f.get("kind"), f.get("title")) for f in a.get("findings") or []}
    tb = [f for f in b.get("findings") or [] if (f.get("kind"), f.get("title")) not in ta]
    ha, hb = int((a.get("health") or {}).get("score") or 0), int((b.get("health") or {}).get("score") or 0)
    return {
        "from": a.get("timestamp"), "to": b.get("timestamp"),
        "health": {"before": ha, "after": hb, "delta": hb - ha},
        "flows_added": [{"app": k[0], "remote": k[1]} for k in sorted(set(fb) - set(fa))][:50],
        "flows_removed": [{"app": k[0], "remote": k[1]} for k in sorted(set(fa) - set(fb))][:50],
        "app_movers": [m for m in movers if m["delta_bps"]][:10],
        "listeners_added": [list(x) for x in sorted(lb - la, key=str)][:20],
        "listeners_removed": [list(x) for x in sorted(la - lb, key=str)][:20],
        "dns": {"added": sorted(db - da), "removed": sorted(da - db)},
        "default_route_changed": _default_routes(a) != _default_routes(b),
        "default_routes": {"before": sorted(map(list, _default_routes(a)), key=str), "after": sorted(map(list, _default_routes(b)), key=str)},
        "devices_added": sorted(x for x in nb - na if x)[:20],
        "devices_removed": sorted(x for x in na - nb if x)[:20],
        "findings_new": [{"severity": f.get("severity"), "title": f.get("title"), "detail": f.get("detail")} for f in tb][:20],
    }


def narrate_incident(first: dict[str, Any], last: dict[str, Any], events: list[dict[str, Any]], start: str, end: str) -> dict[str, Any]:
    """A deterministic what-changed narrative: ordered steps with the evidence behind each."""
    d = diff_snapshots(first, last)
    steps: list[dict[str, Any]] = []
    for e in events:
        steps.append({"ts": e.get("ts"), "kind": e.get("kind"), "text": f"{e.get('title')}" + (f" — {e['detail']}" if e.get("detail") else "")})
    if d["default_route_changed"]:
        steps.append({"ts": end, "kind": "route", "text": "The default route differs from the start of the window."})
    for m in d["app_movers"][:3]:
        if abs(m["delta_bps"]) >= 100_000:
            steps.append({"ts": end, "kind": "traffic", "text": f"{m['app']} moved {m['delta_bps'] / 1048576:+.2f} MB/s over the window."})
    for f in d["findings_new"][:5]:
        steps.append({"ts": end, "kind": "finding", "text": f"New finding: {f['title']}."})
    steps.sort(key=lambda x: str(x.get("ts") or ""))
    h = d["health"]
    headline = f"Health went {h['before']} → {h['after']} ({h['delta']:+d}); " if h["delta"] else f"Health stayed at {h['after']}; "
    headline += f"{len(d['flows_added'])} flow group(s) appeared, {len(d['flows_removed'])} ended, {len(events)} event(s) recorded."
    return {"window": {"from": start, "to": end}, "headline": headline, "steps": steps, "diff": d}
