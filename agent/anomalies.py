# SPDX-License-Identifier: BUSL-1.1
"""Explainable rate-based anomaly findings. New-destination detection lives in HistoryStore."""
from __future__ import annotations

from typing import Any

HIGH_APP_BPS = 5 * 1024 * 1024


def detect_anomalies(current: dict[str, Any], high_bps: float = HIGH_APP_BPS) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    flows = current.get("flows") or []
    per_app: dict[str, float] = {}
    for f in flows:
        name = f.get("process") or "unknown"
        per_app[name] = per_app.get(name, 0.0) + float(f.get("total_bps") or 0)
    if per_app:
        top = max(per_app, key=per_app.get)
        if per_app[top] > high_bps:
            findings.append({"severity": "warning", "kind": "anomaly", "title": "High bandwidth application",
                             "detail": f"{top} is using {per_app[top] / 1048576:.1f} MB/s.", "app": top})
    vpn_ifaces = {i.get("name") for i in current.get("interfaces") or [] if str(i.get("name") or "").startswith(("utun", "ppp", "ipsec"))}
    active = any(v.get("active") for v in current.get("vpn") or [])
    seen = {f.get("interface") for f in flows if f.get("interface")}
    if active and seen & vpn_ifaces and seen - vpn_ifaces:
        findings.append({"severity": "info", "kind": "anomaly", "title": "Mixed VPN and direct traffic",
                         "detail": "Some flows use a tunnel interface while others bypass it."})
    return findings


def merge_findings(existing: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {(f.get("kind"), f.get("title"), f.get("app"), f.get("remote")) for f in existing}
    for f in extra:
        key = (f.get("kind"), f.get("title"), f.get("app"), f.get("remote"))
        if key not in seen:
            existing.append(f)
            seen.add(key)
    return existing
