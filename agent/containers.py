# SPDX-License-Identifier: BUSL-1.1
"""Container runtime awareness: tag flows owned by Docker, Podman, Colima, OrbStack, Lima."""
from __future__ import annotations

import re
from typing import Any

_RUNTIMES = (
    ("docker", re.compile(r"(?i)\b(docker|com\.docker\.[\w.]+|vpnkit)\b")),
    ("podman", re.compile(r"(?i)\b(podman|gvproxy)\b")),
    ("colima", re.compile(r"(?i)\bcolima\b")),
    ("lima", re.compile(r"(?i)\b(limactl|lima|qemu-system-[\w-]+)\b")),
    ("orbstack", re.compile(r"(?i)\b(orbstack|orbstack helper)\b")),
    ("rancher-desktop", re.compile(r"(?i)\b(rancher[ -]desktop|k3s|containerd)\b")),
)


def detect_runtime(process: str) -> str:
    """Return the runtime name for a process name, or '' if not a container runtime."""
    for name, pattern in _RUNTIMES:
        if pattern.search(process or ""):
            return name
    return ""


def enrich_flows_with_containers(flows: list[dict[str, Any]], lsof_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    runtime_pids = {}
    for row in lsof_rows or []:
        rt = detect_runtime(row.get("process", ""))
        if rt and row.get("pid"):
            runtime_pids[row["pid"]] = rt
    for flow in flows:
        rt = detect_runtime(flow.get("process", "")) or runtime_pids.get(flow.get("pid"), "")
        flow["container"] = bool(rt)
        if rt:
            flow["runtime"] = rt
    return flows


def summarize_containers(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for f in flows:
        if not f.get("container"):
            continue
        rt = f.get("runtime") or "container"
        b = buckets.setdefault(rt, {"runtime": rt, "flows": 0, "bytes_in": 0, "bytes_out": 0, "apps": set()})
        b["flows"] += 1
        b["bytes_in"] += int(f.get("bytes_in") or 0)
        b["bytes_out"] += int(f.get("bytes_out") or 0)
        if f.get("process"):
            b["apps"].add(f["process"])
    out = [{**b, "apps": sorted(b["apps"])} for b in buckets.values()]
    return sorted(out, key=lambda x: x["bytes_in"] + x["bytes_out"], reverse=True)
