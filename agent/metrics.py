# SPDX-License-Identifier: BUSL-1.1
"""Prometheus text exposition (version 0.0.4) rendered from a snapshot. Stdlib only, no labels with free text."""
from __future__ import annotations

import re
from typing import Any


def _label(value: Any) -> str:
    s = re.sub(r"[\x00-\x1f]", "", str(value))
    return s.replace("\\", "\\\\").replace('"', '\\"')


def render_metrics(s: dict[str, Any]) -> str:
    t = s.get("traffic") or {}
    lines: list[str] = []

    def metric(name: str, help_: str, kind: str, samples: list[tuple[dict[str, str], float]]):
        lines.append(f"# HELP {name} {help_}")
        lines.append(f"# TYPE {name} {kind}")
        for labels, value in samples:
            lab = ",".join(f'{k}="{_label(v)}"' for k, v in labels.items())
            lines.append(f"{name}{{{lab}}} {value}" if lab else f"{name} {value}")

    metric("nivora_health_score", "Network health score, 0-100.", "gauge", [({}, float((s.get("health") or {}).get("score") or 0))])
    metric("nivora_flows", "Current number of flows.", "gauge", [({}, float(len(s.get("flows") or [])))])
    metric("nivora_traffic_bytes_per_second", "Live traffic rate.", "gauge", [
        ({"direction": "rx"}, float(t.get("rx_bps") or 0)), ({"direction": "tx"}, float(t.get("tx_bps") or 0))])
    metric("nivora_findings", "Current findings by severity.", "gauge", [
        ({"severity": sev}, float(sum(1 for f in s.get("findings") or [] if f.get("severity") == sev)))
        for sev in ("critical", "warning", "info")])
    metric("nivora_listeners", "Listening sockets.", "gauge", [({}, float(len(s.get("listeners") or [])))])
    metric("nivora_port_conflicts", "Ports bound by more than one process.", "gauge", [({}, float(len(s.get("port_conflicts") or [])))])
    apps = sorted(s.get("apps") or [], key=lambda a: a.get("tx_bps", 0) + a.get("rx_bps", 0), reverse=True)[:20]
    metric("nivora_app_bytes_per_second", "Live per-app rate for the 20 busiest apps.", "gauge",
           [({"app": a.get("name", ""), "direction": d}, float(a.get(f"{d}_bps") or 0)) for a in apps for d in ("rx", "tx")])
    return "\n".join(lines) + "\n"
