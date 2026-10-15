# SPDX-License-Identifier: BUSL-1.1
"""Evidence for a single flow ("why this flow?") and the impact of rules, shadow rules included."""
from __future__ import annotations

from typing import Any

from nivora_core import endpoint_host, endpoint_port


def explain_flow(snapshot: dict[str, Any], flow_id: str) -> dict[str, Any] | None:
    flow = next((f for f in snapshot.get("flows") or [] if f.get("id") == flow_id), None)
    if flow is None:
        return None
    app = flow.get("process") or "Unknown"
    host = endpoint_host(flow.get("remote", ""))
    port = endpoint_port(flow.get("remote", ""))
    iface = flow.get("interface") or ""
    vpn_active = [v.get("name") for v in snapshot.get("vpn") or [] if v.get("active")]
    total = sum(float(f.get("total_bps") or 0) for f in snapshot.get("flows") or []) or 0.0
    share = round(100 * float(flow.get("total_bps") or 0) / total, 1) if total else 0.0
    new = [d for d in (snapshot.get("behavior") or {}).get("new_destinations") or []
           if d.get("app") in {app, flow.get("bundle_id")} and d.get("remote") in {host, flow.get("remote")}]
    rules = [h for h in snapshot.get("rule_hits") or [] if h.get("flow_id") == flow_id]
    findings = [x for x in snapshot.get("findings") or []
                if x.get("app") in {app, flow.get("bundle_id")} or (host and x.get("remote") == host)]
    reasons: list[str] = []
    reasons.append(f"{app} (pid {flow.get('pid') or '?'}) opened a {flow.get('protocol') or 'network'} connection to {host or flow.get('remote') or 'unknown'}"
                   + (f":{port}" if port else "") + ".")
    if new:
        reasons.append("This destination is new for this app since the learned baseline.")
    if iface:
        reasons.append(f"It leaves via {iface}" + (", a tunnel interface." if iface.startswith(("utun", "ppp", "ipsec")) and vpn_active else "."))
    if share >= 1:
        reasons.append(f"It accounts for {share}% of current traffic.")
    for h in rules:
        reasons.append(f"Rule {h.get('rule_id')} ({h.get('action')}) matches this flow.")
    for x in findings[:3]:
        reasons.append(f"Related finding: {x.get('title')}.")
    return {
        "flow": flow,
        "app": app, "destination": {"host": host, "port": port},
        "path": {"interface": iface, "vpn_active": vpn_active},
        "traffic_share_percent": share,
        "new_destination": bool(new),
        "rules": rules, "findings": findings,
        "reasons": reasons,
    }


def rule_impact(flows: list[dict[str, Any]], rules: list[dict[str, Any]], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per rule: how much live traffic it matches and whether it would be enforced.

    `shadow` rules count what they would block without ever enforcing.
    """
    by_id = {f.get("id"): f for f in flows}
    out = []
    for rule in rules:
        matched = [by_id[h["flow_id"]] for h in hits if h.get("rule_id") == rule.get("id") and h.get("flow_id") in by_id]
        action = rule.get("action")
        out.append({
            "rule_id": rule.get("id"), "action": action,
            "enforced": action == "block",
            "would_block": action in {"block", "shadow"},
            "flows": len(matched),
            "apps": sorted({f.get("process") or "Unknown" for f in matched}),
            "bytes": sum(int(f.get("bytes_in") or 0) + int(f.get("bytes_out") or 0) for f in matched),
            "bps": round(sum(float(f.get("total_bps") or 0) for f in matched), 2),
        })
    return out
