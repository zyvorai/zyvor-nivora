# SPDX-License-Identifier: BUSL-1.1
from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import hashlib
import ipaddress
import json
import os
import platform
import re
import socket
import sqlite3
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from projects import attribute_projects, parse_lsof_cwd

VERSION = "0.3.0"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(p or "") for p in parts).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "-"):
            return default
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


class CommandRunner:
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def run(self, argv: list[str]) -> str:
        try:
            p = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            return p.stdout if p.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""


def parse_lsof(text: str) -> list[dict[str, Any]]:
    """Parse `lsof -nP -iTCP -iUDP` output into connection rows.

    The parser is deliberately forgiving: it accepts TCP state suffixes and
    IPv6 endpoints and ignores rows that do not contain an internet endpoint.
    """
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("COMMAND "):
            continue
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        command, pid, user, _fd, _type, _device, _sizeoff, node, name = parts
        if node not in {"TCP", "UDP"}:
            continue
        state = ""
        m_state = re.search(r"\s+\(([^)]+)\)\s*$", name)
        if m_state:
            state = m_state.group(1)
            name = name[: m_state.start()].strip()
        local, remote = name, ""
        if "->" in name:
            local, remote = name.split("->", 1)
        rows.append(
            {
                "id": stable_id(command, pid, node, local, remote),
                "process": command,
                "pid": as_int(pid),
                "user": user,
                "protocol": node.lower(),
                "local": local,
                "remote": remote,
                "state": state,
                "bytes_in": 0,
                "bytes_out": 0,
                "interface": "",
                "rtt_ms": 0.0,
                "source": "lsof",
            }
        )
    return rows


def _norm_header(value: str) -> str:
    v = value.strip().lower().replace(" ", "_")
    v = re.sub(r"[^a-z0-9_.-]+", "_", v)
    aliases = {
        "bytes_in": "bytes_in",
        "bytes_out": "bytes_out",
        "rxbytes": "bytes_in",
        "txbytes": "bytes_out",
        "rtt_avg": "rtt_ms",
        "rtt": "rtt_ms",
        "interface": "interface",
        "state": "state",
        "local": "local",
        "remote": "remote",
        "protocol": "protocol",
    }
    return aliases.get(v, v)


def parse_nettop(text: str) -> list[dict[str, Any]]:
    """Parse CSV-like `nettop -x` output.

    macOS has changed the exact column set across releases. The parser finds
    known columns by header name and also understands the first process column
    (`name.pid`). Unknown columns are ignored.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    reader = csv.reader(lines)
    raw_rows = list(reader)
    if not raw_rows:
        return []
    headers = [_norm_header(x) for x in raw_rows[0]]
    out: list[dict[str, Any]] = []
    for raw in raw_rows[1:]:
        if not raw or all(not x.strip() for x in raw):
            continue
        if len(raw) < len(headers):
            raw += [""] * (len(headers) - len(raw))
        row = {headers[i]: raw[i].strip() for i in range(min(len(headers), len(raw)))}
        identity = row.get("process") or row.get("process_name") or row.get("name") or row.get("proc") or raw[0].strip()
        m = re.match(r"^(.*?)[.:]([0-9]+)$", identity)
        process = identity
        pid = 0
        if m:
            process, pid = m.group(1), int(m.group(2))
        # Some versions emit child socket rows beginning with spaces; skip rows
        # that carry no process identity at all.
        if not process:
            continue
        local = row.get("local") or row.get("local_address") or ""
        remote = row.get("remote") or row.get("remote_address") or ""
        out.append(
            {
                "id": stable_id(process, pid, row.get("protocol"), local, remote),
                "process": process,
                "pid": pid,
                "user": "",
                "protocol": (row.get("protocol") or "").lower(),
                "local": local,
                "remote": remote,
                "state": row.get("state", ""),
                "bytes_in": as_int(row.get("bytes_in")),
                "bytes_out": as_int(row.get("bytes_out")),
                "interface": row.get("interface", ""),
                "rtt_ms": as_float(row.get("rtt_ms")),
                "source": "nettop",
            }
        )
    return out



def parse_extension_events(path: str, limit: int = 4000) -> list[dict[str, Any]]:
    """Read the most recent NetworkExtension JSONL flow reports.

    The control provider emits cumulative byte counters. Keep only the latest
    record per flow id so app traffic is not double-counted.
    """
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        return []
    try:
        with p.open("rb") as fh:
            # Small local log by design; cap memory even if a stale build grew it.
            data = fh.read(8 * 1024 * 1024).decode("utf-8", "replace")
    except OSError:
        return []
    lines = data.splitlines()[-limit:]
    latest: dict[str, dict[str, Any]] = {}
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        flow_id = str(e.get("flow_id") or e.get("id") or "")
        if not flow_id:
            continue
        latest[flow_id] = {
            "id": flow_id,
            "process": e.get("process") or e.get("bundle_id") or "Unknown",
            "bundle_id": e.get("bundle_id", ""),
            "pid": as_int(e.get("pid")),
            "user": "",
            "protocol": str(e.get("protocol", "")).lower(),
            "local": e.get("local", ""),
            "remote": e.get("remote", ""),
            "state": e.get("state") or e.get("event") or "observed",
            "bytes_in": as_int(e.get("bytes_in")),
            "bytes_out": as_int(e.get("bytes_out")),
            "interface": e.get("interface", ""),
            "rtt_ms": as_float(e.get("rtt_ms")),
            "source": "networkextension",
        }
    return list(latest.values())

def parse_netstat_routes(text: str, family: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started = False
    for line in text.splitlines():
        if line.startswith("Destination"):
            started = True
            continue
        if not started or not line.strip() or line.startswith("Routing") or line.startswith("Internet"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        destination, gateway = parts[0], parts[1]
        interface = parts[-1] if len(parts) >= 4 else ""
        flags = parts[2]
        rows.append(
            {
                "family": family,
                "destination": destination,
                "gateway": gateway,
                "flags": flags,
                "interface": interface,
                "default": destination in {"default", "0.0.0.0", "::/0"},
            }
        )
    return rows


def parse_scutil_dns(text: str) -> dict[str, Any]:
    resolvers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        m = re.match(r"\s*resolver #([0-9]+)", line)
        if m:
            if current:
                resolvers.append(current)
            current = {"index": int(m.group(1)), "nameservers": [], "search": []}
            continue
        if current is None:
            continue
        m = re.match(r"\s*nameserver\[[0-9]+\]\s*:\s*(.+)", line)
        if m:
            current["nameservers"].append(m.group(1).strip())
            continue
        m = re.match(r"\s*search domain\[[0-9]+\]\s*:\s*(.+)", line)
        if m:
            current["search"].append(m.group(1).strip())
            continue
        m = re.match(r"\s*if_index\s*:\s*([0-9]+)\s*\(([^)]+)\)", line)
        if m:
            current["if_index"] = int(m.group(1))
            current["interface"] = m.group(2)
        m = re.match(r"\s*domain\s*:\s*(.+)", line)
        if m:
            current["domain"] = m.group(1).strip()
    if current:
        resolvers.append(current)
    servers: list[str] = []
    for r in resolvers:
        for ns in r.get("nameservers", []):
            if ns not in servers:
                servers.append(ns)
    return {"resolvers": resolvers, "servers": servers}


def parse_ifconfig(text: str) -> list[dict[str, Any]]:
    interfaces: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if line and not line[0].isspace():
            if current:
                interfaces.append(current)
            name = line.split(":", 1)[0]
            current = {
                "name": name,
                "flags": line.split("<", 1)[1].split(">", 1)[0].split(",") if "<" in line else [],
                "ipv4": [],
                "ipv6": [],
                "mac": "",
                "mtu": as_int(re.search(r"\bmtu\s+(\d+)", line).group(1)) if re.search(r"\bmtu\s+(\d+)", line) else 0,
                "status": "unknown",
            }
            continue
        if current is None:
            continue
        s = line.strip()
        if s.startswith("inet "):
            current["ipv4"].append(s.split()[1])
        elif s.startswith("inet6 "):
            current["ipv6"].append(s.split()[1].split("%", 1)[0])
        elif s.startswith("ether "):
            current["mac"] = s.split()[1]
        elif s.startswith("status: "):
            current["status"] = s.split(":", 1)[1].strip()
    if current:
        interfaces.append(current)
    for item in interfaces:
        n = item["name"]
        item["kind"] = (
            "vpn" if n.startswith("utun") else
            "loopback" if n == "lo0" else
            "bridge" if n.startswith("bridge") else
            "wifi_or_ethernet" if n.startswith("en") else
            "virtual" if n.startswith(("vmnet", "vmenet", "awdl", "llw")) else
            "other"
        )
    return interfaces


def parse_scutil_nc(text: str) -> list[dict[str, Any]]:
    vpns: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = re.match(r"\s*([* -])\s*\(([^)]+)\)\s+([^\s]+)\s+\"(.+)\"", line)
        if not m:
            continue
        marker, status, service_id, name = m.groups()
        vpns.append({"name": name, "service_id": service_id, "status": status, "active": marker == "*"})
    return vpns



def parse_networksetup_hardware_ports(text: str) -> dict[str, dict[str, str]]:
    """Map BSD devices (en0, en7...) to macOS hardware-port labels."""
    out: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if not line:
            if current.get("device"):
                out[current["device"]] = dict(current)
            current = {}
            continue
        if line.startswith("Hardware Port:"):
            current["hardware_port"] = line.split(":", 1)[1].strip()
        elif line.startswith("Device:"):
            current["device"] = line.split(":", 1)[1].strip()
        elif line.startswith("Ethernet Address:"):
            current["ethernet_address"] = line.split(":", 1)[1].strip()
    return out


def enrich_interface_hardware(interfaces: list[dict[str, Any]], ports: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    for item in interfaces:
        meta = ports.get(item.get("name", ""), {})
        label = meta.get("hardware_port", "")
        if label:
            item["hardware_port"] = label
            low = label.lower()
            if "wi-fi" in low or "airport" in low:
                item["kind"] = "wifi"
            elif "thunderbolt" in low:
                item["kind"] = "thunderbolt"
            elif "ethernet" in low:
                item["kind"] = "ethernet"
        if not item.get("mac") and meta.get("ethernet_address"):
            item["mac"] = meta["ethernet_address"]
    return interfaces


def parse_airport_network(text: str) -> str:
    if ":" not in text:
        return ""
    value = text.split(":", 1)[1].strip()
    if value.lower().startswith("you are not associated"):
        return ""
    return value


def parse_arp(text: str) -> list[dict[str, Any]]:
    """Parse `arp -an` without requiring root."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = re.search(r"\(([^)]+)\)\s+at\s+([^\s]+)\s+on\s+([^\s]+)", line)
        if not m:
            continue
        ip, mac, interface = m.groups()
        out.append({
            "id": stable_id("arp", ip, interface), "family": "ipv4", "ip": ip,
            "mac": "" if mac == "(incomplete)" or mac == "<incomplete>" else mac,
            "interface": interface, "state": "incomplete" if "incomplete" in mac else "reachable",
        })
    return out


def parse_ndp(text: str) -> list[dict[str, Any]]:
    """Best-effort parser for `ndp -an` across macOS releases."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("neighbor"):
            continue
        parts = line.split()
        if not parts or ":" not in parts[0]:
            continue
        ip = parts[0]
        interface = next((x for x in parts if re.fullmatch(r"(?:en|utun|bridge|llw|awdl|lo|vmnet)\w*\d*", x)), "")
        mac = next((x for x in parts[1:] if re.fullmatch(r"(?:[0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}", x)), "")
        out.append({"id": stable_id("ndp", ip, interface), "family": "ipv6", "ip": ip, "mac": mac, "interface": interface, "state": "reachable"})
    return out


def derive_listeners(lsof_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    listeners: list[dict[str, Any]] = []
    for row in lsof_rows:
        if row.get("remote"):
            continue
        port = endpoint_port(row.get("local", ""))
        if not port:
            continue
        host = endpoint_host(row.get("local", ""))
        exposure = "loopback" if host in {"127.0.0.1", "::1", "localhost"} else "all" if host in {"*", "0.0.0.0", "::"} else "local"
        listeners.append({
            "id": stable_id("listener", row.get("process"), row.get("pid"), row.get("protocol"), row.get("local")),
            "process": row.get("process", "Unknown"), "pid": as_int(row.get("pid")),
            "protocol": row.get("protocol", ""), "address": host, "port": port,
            "state": row.get("state") or ("LISTEN" if row.get("protocol") == "tcp" else "BOUND"),
            "exposure": exposure,
        })
    return sorted(listeners, key=lambda x: (x["exposure"] != "all", x["port"], x["process"]))


def _timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def annotate_rates(flows: list[dict[str, Any]], previous: dict[str, Any] | None, timestamp: str) -> list[dict[str, Any]]:
    prev_flows = {f.get("id"): f for f in (previous or {}).get("flows", []) if f.get("id")}
    now = _timestamp(timestamp)
    then = _timestamp((previous or {}).get("timestamp"))
    elapsed = (now - then).total_seconds() if now and then else 0.0
    if elapsed <= 0 or elapsed > 300:
        elapsed = 0.0
    for flow in flows:
        rx = tx = 0.0
        old = prev_flows.get(flow.get("id"))
        flow["first_seen"] = (old or {}).get("first_seen") or (old or {}).get("last_seen") or timestamp
        flow["last_seen"] = timestamp
        if old and elapsed:
            rx = max(0, as_int(flow.get("bytes_in")) - as_int(old.get("bytes_in"))) / elapsed
            tx = max(0, as_int(flow.get("bytes_out")) - as_int(old.get("bytes_out"))) / elapsed
        flow["rx_bps"] = round(rx, 2)
        flow["tx_bps"] = round(tx, 2)
        flow["total_bps"] = round(rx + tx, 2)
    return flows


def compute_traffic(flows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(flows)
    rx = sum(as_float(x.get("rx_bps")) for x in rows)
    tx = sum(as_float(x.get("tx_bps")) for x in rows)
    by_iface: Counter[str] = Counter()
    for f in rows:
        if f.get("interface"):
            by_iface[f["interface"]] += as_int(f.get("bytes_in")) + as_int(f.get("bytes_out"))
    return {
        "rx_bps": round(rx, 2), "tx_bps": round(tx, 2), "total_bps": round(rx + tx, 2),
        "active_flows": len(rows),
        "internet_flows": sum(classify_remote(endpoint_host(x.get("remote", ""))) in {"internet", "domain"} for x in rows),
        "vpn_flows": sum(str(x.get("interface", "")).startswith("utun") for x in rows),
        "top_interface": by_iface.most_common(1)[0][0] if by_iface else "",
    }


def compute_health(snapshot: dict[str, Any]) -> dict[str, Any]:
    interfaces = snapshot.get("interfaces", [])
    routes = snapshot.get("routes", [])
    dns = snapshot.get("dns", {})
    flows = snapshot.get("flows", [])
    findings = snapshot.get("findings", [])
    active_nonloop = [i for i in interfaces if i.get("name") != "lo0" and (i.get("status") == "active" or "UP" in i.get("flags", []))]
    route_score = 100 if any(r.get("default") for r in routes) else 0
    interface_score = 100 if active_nonloop else 10
    dns_score = 100 if dns.get("servers") else 0
    rtts = [as_float(f.get("rtt_ms")) for f in flows if as_float(f.get("rtt_ms")) > 0]
    median_rtt = statistics.median(rtts) if rtts else 0.0
    if not rtts: latency_score = 90
    elif median_rtt <= 50: latency_score = 100
    elif median_rtt <= 100: latency_score = 85
    elif median_rtt <= 175: latency_score = 65
    elif median_rtt <= 300: latency_score = 45
    else: latency_score = 20
    critical = sum(f.get("severity") == "critical" for f in findings)
    warning = sum(f.get("severity") == "warning" for f in findings)
    security_score = max(20, 100 - critical * 35 - warning * 10)
    overall = round(route_score * .28 + dns_score * .18 + latency_score * .26 + interface_score * .13 + security_score * .15)
    status = "healthy" if overall >= 85 else "degraded" if overall >= 65 else "poor"
    components = [
        {"name": "Route", "score": route_score, "detail": "Default route present" if route_score else "No default route"},
        {"name": "DNS", "score": dns_score, "detail": f"{len(dns.get('servers', []))} resolver(s)" if dns_score else "No resolver visible"},
        {"name": "Latency", "score": latency_score, "detail": f"Median RTT {median_rtt:.1f} ms" if rtts else "No RTT sample"},
        {"name": "Interfaces", "score": interface_score, "detail": f"{len(active_nonloop)} active"},
        {"name": "Safety", "score": security_score, "detail": f"{critical} critical · {warning} warning"},
    ]
    return {"score": overall, "status": status, "median_rtt_ms": round(median_rtt, 1), "components": components}


def build_topology(snapshot: dict[str, Any], max_destinations: int = 24) -> dict[str, Any]:
    flows = snapshot.get("flows", [])
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    host_id = "host:this-mac"
    nodes[host_id] = {"id": host_id, "kind": "host", "label": snapshot.get("host", {}).get("name", "This Mac")}
    destination_bytes: Counter[str] = Counter()
    for f in flows:
        h = endpoint_host(f.get("remote", ""))
        if h:
            destination_bytes[h] += as_int(f.get("bytes_in")) + as_int(f.get("bytes_out"))
    allowed_dest = {h for h, _ in destination_bytes.most_common(max_destinations)}
    for f in flows:
        app = process_display_name(f.get("process") or f.get("app") or "Unknown")
        app_id = "app:" + stable_id(app, f.get("bundle_id", ""))
        nodes.setdefault(app_id, {"id": app_id, "kind": "app", "label": app, "bundle_id": f.get("bundle_id", "")})
        iface = f.get("interface") or "unknown"
        iface_id = "if:" + iface
        nodes.setdefault(iface_id, {"id": iface_id, "kind": "interface", "label": iface})
        key = (app_id, iface_id)
        e = edges.setdefault(key, {"source": app_id, "target": iface_id, "kind": "uses", "bytes": 0, "bps": 0.0, "flows": 0})
        e["bytes"] += as_int(f.get("bytes_in")) + as_int(f.get("bytes_out")); e["bps"] += as_float(f.get("total_bps")); e["flows"] += 1
        remote = endpoint_host(f.get("remote", ""))
        if remote and remote in allowed_dest:
            dest_id = "dst:" + stable_id(remote)
            nodes.setdefault(dest_id, {"id": dest_id, "kind": classify_remote(remote), "label": remote})
            key = (iface_id, dest_id)
            e = edges.setdefault(key, {"source": iface_id, "target": dest_id, "kind": "reaches", "bytes": 0, "bps": 0.0, "flows": 0})
            e["bytes"] += as_int(f.get("bytes_in")) + as_int(f.get("bytes_out")); e["bps"] += as_float(f.get("total_bps")); e["flows"] += 1
    for e in edges.values(): e["bps"] = round(e["bps"], 2)
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def correlate_fluxvm(fluxvm: dict[str, Any], flows: list[dict[str, Any]]) -> dict[str, Any]:
    needles = ("fluxvm", "vz-runner", "usernet", "vmnet")
    host_flows = [f for f in flows if any(n in str(f.get("process", "")).lower() for n in needles)]
    fluxvm["host_flows"] = host_flows[:200]
    fluxvm["host_flow_count"] = len(host_flows)
    endpoints = fluxvm.get("network_endpoints")
    hubble = fluxvm.get("hubble_flows")
    fluxvm["network_endpoint_count"] = len(endpoints) if isinstance(endpoints, list) else len(endpoints.get("items", [])) if isinstance(endpoints, dict) else 0
    fluxvm["hubble_flow_count"] = len(hubble) if isinstance(hubble, list) else len(hubble.get("flows", [])) if isinstance(hubble, dict) else 0
    return fluxvm


def diagnose_network(snapshot: dict[str, Any]) -> dict[str, Any]:
    health = snapshot.get("health") or compute_health(snapshot)
    causes: list[dict[str, Any]] = []
    if not any(r.get("default") for r in snapshot.get("routes", [])):
        causes.append({"severity": "critical", "title": "No default route", "detail": "The Mac has no reported path to external networks."})
    if not snapshot.get("dns", {}).get("servers"):
        causes.append({"severity": "critical", "title": "DNS unavailable", "detail": "No resolver is currently visible through scutil."})
    high = sorted([f for f in snapshot.get("flows", []) if as_float(f.get("rtt_ms")) >= 150], key=lambda x: as_float(x.get("rtt_ms")), reverse=True)
    if high:
        causes.append({"severity": "warning", "title": "High application latency", "detail": f"{high[0].get('process')} → {high[0].get('remote')} is {as_float(high[0].get('rtt_ms')):.1f} ms.", "flow_id": high[0].get("id")})
    active_vpn = [v for v in snapshot.get("vpn", []) if v.get("active")]
    vpn_rtt = [as_float(f.get("rtt_ms")) for f in snapshot.get("flows", []) if str(f.get("interface", "")).startswith("utun") and as_float(f.get("rtt_ms")) > 0]
    direct_rtt = [as_float(f.get("rtt_ms")) for f in snapshot.get("flows", []) if not str(f.get("interface", "")).startswith("utun") and as_float(f.get("rtt_ms")) > 0]
    if active_vpn and vpn_rtt and direct_rtt and statistics.median(vpn_rtt) > max(100, statistics.median(direct_rtt) * 2):
        causes.append({"severity": "warning", "title": "VPN path is materially slower", "detail": f"VPN median RTT {statistics.median(vpn_rtt):.1f} ms vs direct {statistics.median(direct_rtt):.1f} ms."})
    recent = snapshot.get("recent_events", [])[-10:]
    disruptive = [e for e in recent if e.get("kind") in {"route", "dns", "vpn", "interface"}]
    if disruptive:
        causes.append({"severity": "info", "title": "Recent network configuration change", "detail": disruptive[-1].get("title", "Network state changed."), "event": disruptive[-1]})
    summary = "Network looks healthy." if not causes and health.get("score", 0) >= 85 else (causes[0]["title"] + "." if causes else f"Network health is {health.get('status', 'unknown')}.")
    return {"summary": summary, "health": health, "causes": causes[:12], "recent_events": recent}

def endpoint_host(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if not endpoint:
        return ""
    if endpoint.startswith("[") and "]" in endpoint:
        return endpoint[1:endpoint.index("]")]
    # lsof prints `host:port`; unbracketed IPv6 remains ambiguous, so keep it.
    if endpoint.count(":") == 1:
        return endpoint.rsplit(":", 1)[0]
    return endpoint


def endpoint_port(endpoint: str) -> int:
    endpoint = endpoint.strip()
    if endpoint.startswith("[") and "]:" in endpoint:
        return as_int(endpoint.rsplit(":", 1)[1])
    if endpoint.count(":") == 1:
        return as_int(endpoint.rsplit(":", 1)[1])
    return 0


_FILTER_KEYS = {"app": "app", "process": "app", "host": "host", "port": "port", "proto": "proto",
                "protocol": "proto", "iface": "iface", "interface": "iface", "state": "state", "source": "source"}
_RATE_RE = re.compile(r"^([<>])(\d+(?:\.\d+)?)(bps|kbps|mbps|gbps)$", re.I)
_RATE_UNITS = {"bps": 1, "kbps": 1e3, "mbps": 1e6, "gbps": 1e9}


def _filter_tokens(query: str) -> list[str]:
    """Whitespace split that keeps double-quoted values together: app:"Google Chrome"."""
    out, cur, quoted = [], "", False
    for ch in query:
        if ch == '"':
            quoted = not quoted
        elif ch.isspace() and not quoted:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def parse_filter(query: str) -> list[dict[str, Any]]:
    """Parse the shared flow-filter grammar (see docs/API.md). Mirrored by web/lib.js parseFilter."""
    terms: list[dict[str, Any]] = []
    for tok in _filter_tokens(str(query or "")):
        negate = tok[0] in "!-" and len(tok) > 1
        body = tok[1:] if negate else tok
        m = _RATE_RE.match(tok)
        if m:
            terms.append({"kind": "rate", "op": m.group(1), "bits": float(m.group(2)) * _RATE_UNITS[m.group(3).lower()], "negate": False})
            continue
        key, sep, value = body.partition(":")
        if sep and key.lower() in _FILTER_KEYS and value:
            terms.append({"kind": _FILTER_KEYS[key.lower()], "value": value.lower(), "negate": negate})
        else:
            terms.append({"kind": "text", "value": tok.lower().lstrip("!") if tok.startswith("!") else tok.lower(),
                          "negate": tok.startswith("!") and len(tok) > 1})
    return terms


def _term_hit(flow: dict[str, Any], t: dict[str, Any]) -> bool:
    kind, value = t["kind"], t.get("value", "")
    remote, local = str(flow.get("remote", "")), str(flow.get("local", ""))
    if kind == "app":
        return value in str(flow.get("process", "")).lower() or value in str(flow.get("bundle_id", "") or "").lower()
    if kind == "host":
        return value in endpoint_host(remote).lower()
    if kind == "port":
        ports = {endpoint_port(remote), endpoint_port(local)}
        lo, _, hi = value.partition("-")
        try:
            a, b = int(lo), int(hi or lo)
        except ValueError:
            return False
        return any(a <= p <= b for p in ports if p)
    if kind in {"proto", "iface", "state", "source"}:
        field = {"proto": "protocol", "iface": "interface"}.get(kind, kind)
        return str(flow.get(field, "")).lower() == value
    return value in json.dumps(flow, sort_keys=True).lower()


def match_flow(flow: dict[str, Any], terms: list[dict[str, Any]]) -> bool:
    """AND across keys, OR across repeated values of the same key, negations always exclude."""
    includes: dict[str, list[dict[str, Any]]] = {}
    for t in terms:
        if t["kind"] == "rate":
            bps = float(flow.get("total_bps") or 0) * 8
            if (t["op"] == ">" and not bps > t["bits"]) or (t["op"] == "<" and not bps < t["bits"]):
                return False
        elif t["negate"]:
            if _term_hit(flow, t):
                return False
        else:
            includes.setdefault(t["kind"], []).append(t)
    return all(any(_term_hit(flow, t) for t in group) for group in includes.values())


def filter_flows(flows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    terms = parse_filter(query)
    return [f for f in flows if match_flow(f, terms)] if terms else list(flows)


# ---- exports -----------------------------------------------------------------------------------

EXPORT_COLUMNS = {
    "flows": ["process", "protocol", "local", "remote", "state", "interface", "rtt_ms", "rx_bps", "tx_bps", "bytes_in", "bytes_out"],
    "apps": ["name", "pid", "bundle_id", "connections", "rx_bps", "tx_bps", "bytes_in", "bytes_out", "domains"],
    "timeline": ["ts", "kind", "title", "detail"],
}
_PRIVATE_V4 = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|169\.254(?:\.\d{1,3}){2})\b")
_MAC = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")
_LINK_LOCAL_V6 = re.compile(r"\bfe80::[0-9a-fA-F:]*")
_SENSITIVE_KEYS = {"ssid", "domains", "search", "nameservers"}


class Redactor:
    """Replaces private addresses, MACs, SSIDs and hostnames with stable per-export tokens."""

    def __init__(self, salt: bytes | None = None):
        self.salt = salt or os.urandom(8)

    def token(self, kind: str, value: str) -> str:
        digest = hashlib.sha256(self.salt + kind.encode() + value.encode()).hexdigest()[:8]
        return f"{kind}-{digest}"

    def text(self, value: str) -> str:
        value = _MAC.sub(lambda m: self.token("mac", m.group(0).lower()), value)
        value = _LINK_LOCAL_V6.sub(lambda m: self.token("ip6", m.group(0)), value)
        return _PRIVATE_V4.sub(lambda m: self.token("ip", m.group(0)), value)

    def walk(self, obj: Any, key: str = "") -> Any:
        if isinstance(obj, dict):
            out = {k: self.walk(v, str(k)) for k, v in obj.items()}
            if key == "host" and isinstance(obj.get("name"), str) and obj["name"]:
                out["name"] = self.token("host", obj["name"])   # this Mac's hostname
            return out
        if isinstance(obj, list):
            return [self.walk(v, key) for v in obj]
        if isinstance(obj, str):
            if key in _SENSITIVE_KEYS and obj:
                return self.token(key.rstrip("s") or "name", obj)
            return self.text(obj)
        return obj


def export_rows(snapshot: dict[str, Any], timeline: list[dict[str, Any]], kind: str, query: str = "") -> list[dict[str, Any]]:
    if kind == "flows":
        return filter_flows(snapshot.get("flows", []), query)
    if kind == "apps":
        apps = snapshot.get("apps", [])
        terms = parse_filter(query)
        if not terms:
            return list(apps)
        return [a for a in apps if match_flow({**a, "process": a.get("name", ""), "remote": (a.get("domains") or [""])[0],
                                               "interface": (a.get("interfaces") or [""])[0]}, terms)]
    if kind == "timeline":
        return list(timeline)
    raise ValueError(f"unknown export kind: {kind}")


def _csv_cell(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text  # spreadsheet formula guard


def render_export(rows: list[dict[str, Any]], kind: str, fmt: str) -> tuple[bytes, str]:
    if fmt == "json":
        return json.dumps(rows, indent=2).encode(), "application/json"
    if fmt == "ndjson":
        return ("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + ("\n" if rows else "")).encode(), "application/x-ndjson"
    if fmt == "csv":
        import io
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        cols = EXPORT_COLUMNS.get(kind)
        if cols is None:
            raise ValueError("csv export is only available for flows, apps and timeline")
        writer.writerow(cols)
        for r in rows:
            writer.writerow([_csv_cell(r.get(c)) for c in cols])
        return buf.getvalue().encode(), "text/csv; charset=utf-8"
    raise ValueError(f"unknown export format: {fmt}")


def build_bundle(snapshot: dict[str, Any], timeline: list[dict[str, Any]], query: str = "", redactor: Redactor | None = None) -> bytes:
    """A zip with the snapshot, flows CSV, timeline NDJSON and a README; optionally redacted."""
    import io
    import zipfile
    snap = dict(snapshot)
    flows, tl = export_rows(snap, timeline, "flows", query), export_rows(snap, timeline, "timeline")
    if redactor:
        snap, flows, tl = redactor.walk(snap), redactor.walk(flows), redactor.walk(tl)
    readme = ("Nivora export bundle\n"
              f"Generated: {utc_now()}\nFilter: {query or '(none)'}\nRedacted: {'yes' if redactor else 'no'}\n"
              "Contains metadata only; no packet payloads.\n")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        z.writestr("snapshot.json", json.dumps(snap, indent=2))
        z.writestr("flows.csv", render_export(flows, "flows", "csv")[0])
        z.writestr("timeline.ndjson", render_export(tl, "timeline", "ndjson")[0])
    return out.getvalue()


def classify_remote(host: str) -> str:
    if not host:
        return "unknown"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "domain"
    if ip.is_loopback:
        return "loopback"
    if ip.is_private or ip.is_link_local:
        return "local"
    return "internet"


def process_display_name(name: str) -> str:
    if not name:
        return "Unknown"
    base = os.path.basename(name)
    base = re.sub(r"\.app$", "", base, flags=re.I)
    return base or name


def aggregate_apps(flows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], dict[str, Any]] = {}
    for f in flows:
        key = (process_display_name(f.get("app") or f.get("process") or "Unknown"), as_int(f.get("pid")))
        g = groups.setdefault(
            key,
            {
                "name": key[0],
                "pid": key[1],
                "bundle_id": f.get("bundle_id", ""),
                "connections": 0,
                "bytes_in": 0,
                "bytes_out": 0,
                "rx_bps": 0.0,
                "tx_bps": 0.0,
                "domains": Counter(),
                "remote_kinds": Counter(),
                "interfaces": Counter(),
            },
        )
        g["connections"] += 1
        g["bytes_in"] += as_int(f.get("bytes_in"))
        g["bytes_out"] += as_int(f.get("bytes_out"))
        g["rx_bps"] += as_float(f.get("rx_bps"))
        g["tx_bps"] += as_float(f.get("tx_bps"))
        remote = endpoint_host(f.get("remote", ""))
        if remote:
            g["domains"][remote] += 1
            g["remote_kinds"][classify_remote(remote)] += 1
        if f.get("interface"):
            g["interfaces"][f["interface"]] += 1
    out = []
    for g in groups.values():
        g["domains"] = [x for x, _ in g["domains"].most_common(8)]
        g["interfaces"] = [x for x, _ in g["interfaces"].most_common(4)]
        g["internet_connections"] = g["remote_kinds"].get("internet", 0) + g["remote_kinds"].get("domain", 0)
        del g["remote_kinds"]
        g["total_bytes"] = g["bytes_in"] + g["bytes_out"]
        g["rx_bps"] = round(g["rx_bps"], 2)
        g["tx_bps"] = round(g["tx_bps"], 2)
        g["total_bps"] = round(g["rx_bps"] + g["tx_bps"], 2)
        out.append(g)
    return sorted(out, key=lambda x: (x["total_bytes"], x["connections"]), reverse=True)


def derive_findings(snapshot: dict[str, Any], previous: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    flows = snapshot.get("flows", [])
    apps = snapshot.get("apps", [])
    routes = snapshot.get("routes", [])
    dns = snapshot.get("dns", {})
    vpns = snapshot.get("vpn", [])
    listeners = snapshot.get("listeners", [])

    if not any(r.get("default") for r in routes):
        findings.append({"severity": "critical", "kind": "route", "title": "No default route", "detail": "macOS currently reports no default IPv4/IPv6 route."})
    if not dns.get("servers"):
        findings.append({"severity": "warning", "kind": "dns", "title": "No DNS resolver visible", "detail": "scutil did not report any nameserver."})

    high_rtt_by_app: dict[str, dict[str, Any]] = {}
    for f in flows:
        port = endpoint_port(f.get("remote", ""))
        if port in {4444, 5555, 6667, 1337} and classify_remote(endpoint_host(f.get("remote", ""))) == "internet":
            findings.append({"severity": "warning", "kind": "flow", "title": f"Unusual outbound port {port}", "detail": f"{f.get('process','Unknown')} → {f.get('remote','')}", "flow_id": f.get("id")})
        if as_float(f.get("rtt_ms")) >= 250:
            key = process_display_name(f.get("process", "Unknown"))
            old = high_rtt_by_app.get(key)
            if old is None or as_float(f.get("rtt_ms")) > as_float(old.get("rtt_ms")):
                high_rtt_by_app[key] = f
    for app, flow in list(high_rtt_by_app.items())[:6]:
        findings.append({"severity": "warning", "kind": "latency", "title": f"High latency for {app}", "detail": f"{as_float(flow.get('rtt_ms')):.1f} ms to {flow.get('remote','')}", "flow_id": flow.get("id")})

    for app in apps:
        if app.get("bytes_out", 0) > 1_000_000_000:
            findings.append({"severity": "info", "kind": "volume", "title": "High outbound volume", "detail": f"{app['name']} has sent more than 1 GB in the current counter window."})
        if app.get("tx_bps", 0) > 25 * 1024 * 1024:
            findings.append({"severity": "info", "kind": "rate", "title": "High live upload rate", "detail": f"{app['name']} is sending at about {app['tx_bps']/1024/1024:.1f} MB/s."})

    for listener in listeners:
        if listener.get("exposure") == "all" and listener.get("port") not in {22, 53, 80, 443, 5353}:
            findings.append({"severity": "warning", "kind": "listener", "title": f"Service exposed on all interfaces: {listener.get('port')}", "detail": f"{listener.get('process','Unknown')} is listening on {listener.get('address')}:{listener.get('port')} ({listener.get('protocol','').upper()}).", "listener_id": listener.get("id")})

    if any(v.get("active") for v in vpns):
        findings.append({"severity": "info", "kind": "vpn", "title": "VPN is active", "detail": ", ".join(v["name"] for v in vpns if v.get("active"))})

    if previous:
        prev_default = {(r.get("family"), r.get("gateway"), r.get("interface")) for r in previous.get("routes", []) if r.get("default")}
        cur_default = {(r.get("family"), r.get("gateway"), r.get("interface")) for r in routes if r.get("default")}
        if prev_default and cur_default and prev_default != cur_default:
            findings.append({"severity": "warning", "kind": "route", "title": "Default route changed", "detail": f"{sorted(prev_default)} → {sorted(cur_default)}"})
    return findings[:80]

def timeline_events(current: dict[str, Any], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not previous:
        return [{"ts": current.get("timestamp", utc_now()), "kind": "startup", "title": "Nivora started observing", "detail": "Initial network snapshot captured."}]
    events: list[dict[str, Any]] = []
    ts = current.get("timestamp", utc_now())
    prev_if = {i["name"]: i for i in previous.get("interfaces", [])}
    cur_if = {i["name"]: i for i in current.get("interfaces", [])}
    for name in sorted(set(prev_if) | set(cur_if)):
        if name not in prev_if:
            events.append({"ts": ts, "kind": "interface", "title": f"Interface {name} appeared", "detail": cur_if[name].get("status", "")})
        elif name not in cur_if:
            events.append({"ts": ts, "kind": "interface", "title": f"Interface {name} disappeared", "detail": ""})
        elif prev_if[name].get("status") != cur_if[name].get("status"):
            events.append({"ts": ts, "kind": "interface", "title": f"{name} status changed", "detail": f"{prev_if[name].get('status')} → {cur_if[name].get('status')}"})
    prev_dns = tuple(previous.get("dns", {}).get("servers", []))
    cur_dns = tuple(current.get("dns", {}).get("servers", []))
    if prev_dns != cur_dns:
        events.append({"ts": ts, "kind": "dns", "title": "DNS resolver changed", "detail": f"{prev_dns or 'none'} → {cur_dns or 'none'}"})
    prev_def = {(r.get("family"), r.get("gateway"), r.get("interface")) for r in previous.get("routes", []) if r.get("default")}
    cur_def = {(r.get("family"), r.get("gateway"), r.get("interface")) for r in current.get("routes", []) if r.get("default")}
    if prev_def != cur_def:
        events.append({"ts": ts, "kind": "route", "title": "Default route changed", "detail": f"{sorted(prev_def)} → {sorted(cur_def)}"})
    prev_vpn = {v.get("service_id") for v in previous.get("vpn", []) if v.get("active")}
    cur_vpn = {v.get("service_id") for v in current.get("vpn", []) if v.get("active")}
    if prev_vpn != cur_vpn:
        names = [v.get("name", v.get("service_id", "VPN")) for v in current.get("vpn", []) if v.get("active")]
        events.append({"ts": ts, "kind": "vpn", "title": "VPN state changed", "detail": "Active: " + (", ".join(names) or "none")})
    prev_listeners = {(x.get("process"), x.get("protocol"), x.get("port"), x.get("exposure")) for x in previous.get("listeners", [])}
    cur_listeners = {(x.get("process"), x.get("protocol"), x.get("port"), x.get("exposure")) for x in current.get("listeners", [])}
    for item in sorted(cur_listeners - prev_listeners, key=lambda x: (x[2] or 0, str(x[0])))[:10]:
        events.append({"ts": ts, "kind": "listener", "title": f"New listening service on port {item[2]}", "detail": f"{item[0]} · {str(item[1]).upper()} · {item[3]}"})
    prev_rate = as_float(previous.get("traffic", {}).get("total_bps"))
    cur_rate = as_float(current.get("traffic", {}).get("total_bps"))
    if cur_rate > 1024 * 1024 and prev_rate > 0 and cur_rate >= prev_rate * 4:
        events.append({"ts": ts, "kind": "traffic", "title": "Traffic rate spiked", "detail": f"{prev_rate/1024/1024:.1f} → {cur_rate/1024/1024:.1f} MB/s"})
    return events


class FluxVMProbe:
    def __init__(self, base_url: str = "http://127.0.0.1:7788", token: str = "", timeout: float = 0.35):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(self.base_url + path, headers={"Accept": "application/json"})
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
            return None

    def collect(self) -> dict[str, Any]:
        # Probe liveness first. On Macs that do not run FluxVM, avoid paying the
        # timeout cost for every optional endpoint on every Nivora sample.
        health = self._get("/healthz")
        vms = self._get("/v1/vms") if health is not None else None
        connected = health is not None or vms is not None
        empty = {
            "connected": connected,
            "base_url": self.base_url,
            "health": health,
            "vms": vms if isinstance(vms, (list, dict)) else [],
            "sandboxes": [],
            "network_health": {},
            "network_endpoints": [],
            "hubble_flows": [],
            "network_observe": {},
            "network_telemetry": [],
        }
        if not connected:
            return empty

        # Current FluxVM network APIs. Older/newer builds may omit some; all are optional.
        sandboxes = self._get("/v1/sandboxes")
        network_health = self._get("/v1/network/health")
        network_endpoints = self._get("/v1/network/endpoints")
        hubble_flows = self._get("/v1/network/hubble/flows?limit=200")
        observe = self._get("/v1/network/observe")
        telemetry = self._get("/v1/network/telemetry")  # forward-compatible richer contract
        empty.update({
            "sandboxes": sandboxes if isinstance(sandboxes, (list, dict)) else [],
            "network_health": network_health if isinstance(network_health, (list, dict)) else {},
            "network_endpoints": network_endpoints if isinstance(network_endpoints, (list, dict)) else [],
            "hubble_flows": hubble_flows if isinstance(hubble_flows, (list, dict)) else [],
            "network_observe": observe if isinstance(observe, (list, dict)) else {},
            "network_telemetry": telemetry if isinstance(telemetry, (list, dict)) else [],
        })
        return empty


class HistoryStore:
    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS snapshots(ts TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS behavior(app TEXT NOT NULL, remote TEXT NOT NULL, port INTEGER NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(app,remote,port))")
            db.execute("CREATE TABLE IF NOT EXISTS devices(mac TEXT PRIMARY KEY, ip TEXT NOT NULL, interface TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS usage(day TEXT NOT NULL, app TEXT NOT NULL, bytes INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day,app))")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        try:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            yield db
            db.commit()
        finally:
            db.close()

    def add_snapshot(self, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, separators=(",", ":"))
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat(timespec="seconds")
        with self.lock, self._connect() as db:
            db.execute("INSERT OR REPLACE INTO snapshots(ts,payload) VALUES(?,?)", (snapshot["timestamp"], payload))
            db.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))

    def add_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with self.lock, self._connect() as db:
            db.executemany("INSERT INTO events(ts,payload) VALUES(?,?)", [(e["ts"], json.dumps(e, separators=(",", ":"))) for e in events])
            db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 5000)")

    def history(self, limit: int = 120) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 2000))
        with self.lock, self._connect() as db:
            rows = db.execute("SELECT payload FROM snapshots ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]

    def series(self, limit: int = 180) -> list[dict[str, Any]]:
        return [{
            "timestamp": s.get("timestamp"),
            "rx_bps": as_float(s.get("traffic", {}).get("rx_bps")),
            "tx_bps": as_float(s.get("traffic", {}).get("tx_bps")),
            "health": as_int(s.get("health", {}).get("score")),
            "flows": len(s.get("flows", [])),
            "apps": len(s.get("apps", [])),
        } for s in self.history(limit)]

    def snapshot_at(self, ts: str) -> dict[str, Any] | None:
        """Newest stored snapshot at or before `ts` (ISO 8601), else the oldest one after it."""
        with self.lock, self._connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE ts <= ? ORDER BY ts DESC LIMIT 1", (ts,)).fetchone()
            if row is None:
                row = db.execute("SELECT payload FROM snapshots WHERE ts > ? ORDER BY ts ASC LIMIT 1", (ts,)).fetchone()
        return json.loads(row[0]) if row else None

    def events_between(self, start: str, end: str, limit: int = 200) -> list[dict[str, Any]]:
        return [e for e in self.events(5000) if start <= str(e.get("ts") or "") <= end][-limit:]

    def events(self, limit: int = 500) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 5000))
        with self.lock, self._connect() as db:
            rows = db.execute("SELECT payload FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]

    def observe_behavior(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Persist per-app destinations and flag only destinations first seen after the baseline seed."""
        ts = snapshot.get("timestamp", utc_now())
        observations: list[tuple[str, str, int]] = []
        for flow in snapshot.get("flows", []):
            remote = endpoint_host(flow.get("remote", ""))
            if not remote or classify_remote(remote) in {"loopback", "local"}:
                continue
            app = flow.get("bundle_id") or process_display_name(flow.get("process", "Unknown"))
            observations.append((app, remote, endpoint_port(flow.get("remote", ""))))
        observations = list(dict.fromkeys(observations))
        new: list[dict[str, Any]] = []
        with self.lock, self._connect() as db:
            baseline_count = db.execute("SELECT COUNT(*) FROM behavior").fetchone()[0]
            for app, remote, port in observations:
                row = db.execute("SELECT first_seen,last_seen,hits FROM behavior WHERE app=? AND remote=? AND port=?", (app, remote, port)).fetchone()
                if row is None:
                    db.execute("INSERT INTO behavior(app,remote,port,first_seen,last_seen,hits) VALUES(?,?,?,?,?,1)", (app, remote, port, ts, ts))
                    if baseline_count > 0:
                        new.append({"ts": ts, "kind": "behavior", "title": f"New destination for {app}", "detail": f"{remote}:{port}" if port else remote, "app": app, "remote": remote, "port": port})
                else:
                    db.execute("UPDATE behavior SET last_seen=?, hits=hits+1 WHERE app=? AND remote=? AND port=?", (ts, app, remote, port))
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat(timespec="seconds")
            db.execute("DELETE FROM behavior WHERE last_seen < ?", (cutoff,))
            total = db.execute("SELECT COUNT(*) FROM behavior").fetchone()[0]
        return {"new_destinations": new, "known_destinations": total}

    def observe_devices(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Persist LAN devices by MAC; return findings for devices first seen after the baseline seed."""
        ts = snapshot.get("timestamp", utc_now())
        seen = {}
        for n in snapshot.get("neighbors", []):
            mac = (n.get("mac") or "").lower()
            # broadcast/multicast and incomplete entries are not devices
            if not mac or mac.startswith(("ff:ff:", "01:00:5e", "33:33")) or n.get("state") == "incomplete":
                continue
            seen[mac] = (n.get("ip") or "", n.get("interface") or "")
        new: list[dict[str, Any]] = []
        with self.lock, self._connect() as db:
            baseline = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
            for mac, (ip, iface) in seen.items():
                row = db.execute("SELECT 1 FROM devices WHERE mac=?", (mac,)).fetchone()
                if row is None:
                    db.execute("INSERT INTO devices VALUES(?,?,?,?,?)", (mac, ip, iface, ts, ts))
                    if baseline > 0:
                        new.append({"severity": "info", "kind": "lan", "title": "New device on the local network",
                                    "detail": f"{ip or 'unknown IP'} ({mac}) on {iface or 'unknown interface'}", "remote": ip})
                else:
                    db.execute("UPDATE devices SET ip=?, interface=?, last_seen=? WHERE mac=?", (ip, iface, ts, mac))
        return new

    def observe_usage(self, snapshot: dict[str, Any], elapsed: float) -> dict[str, int]:
        """Add rate*elapsed per app to today's usage; returns today's totals."""
        day = str(snapshot.get("timestamp", utc_now()))[:10]
        elapsed = max(0.0, min(elapsed, 300.0))
        add: dict[str, float] = {}
        for a in snapshot.get("apps", []):
            add[a.get("name", "Unknown")] = (as_float(a.get("rx_bps")) + as_float(a.get("tx_bps"))) * elapsed
        with self.lock, self._connect() as db:
            for app, b in add.items():
                if b >= 1:
                    db.execute("INSERT INTO usage(day,app,bytes) VALUES(?,?,?) ON CONFLICT(day,app) DO UPDATE SET bytes=bytes+?", (day, app, int(b), int(b)))
            db.execute("DELETE FROM usage WHERE day < date(?, '-60 day')", (day,))
            rows = db.execute("SELECT app, bytes FROM usage WHERE day=?", (day,)).fetchall()
        return {app: b for app, b in rows}


class RuleStore:
    def __init__(self, path: str):
        self.path = Path(os.path.expanduser(path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text())
            rules = data if isinstance(data, list) else []
        except (OSError, ValueError):
            rules = []
        now = dt.datetime.now(dt.timezone.utc)
        out = []
        for r in rules:
            item = dict(r)
            expires = item.get("expires_at")
            active = True
            if expires:
                try: active = dt.datetime.fromisoformat(expires.replace("Z", "+00:00")) > now
                except ValueError: active = False
            item["active"] = active
            out.append(item)
        return out

    def save(self, rules: list[dict[str, Any]]) -> None:
        clean = [{k:v for k,v in r.items() if k != "active"} for r in rules]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    @staticmethod
    def clean_rule(rule: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise a rule (leasing blocks); raises ValueError."""
        allowed = {"app", "domain", "ip", "port", "action", "expires_at", "note", "permanent", "duration_seconds"}
        clean = {k: rule.get(k) for k in allowed if rule.get(k) not in (None, "")}
        action = clean.get("action", "observe")
        if action not in {"observe", "block", "allow", "shadow"}:
            raise ValueError("action must be observe, block, allow or shadow")
        predicates = [clean.get(k) for k in ("app", "domain", "ip", "port")]
        if not any(x not in (None, "") for x in predicates):
            raise ValueError("a rule needs app, domain, ip or port")
        if clean.get("port") is not None:
            port = as_int(clean["port"])
            if not 1 <= port <= 65535: raise ValueError("port must be 1..65535")
            clean["port"] = port
        if clean.get("ip"):
            try: ipaddress.ip_address(str(clean["ip"]))
            except ValueError as exc: raise ValueError("invalid IP address") from exc
        if clean.get("domain"):
            clean["domain"] = str(clean["domain"]).strip().lower().rstrip(".")
        clean["action"] = action
        permanent = bool(clean.pop("permanent", False))
        duration = as_int(clean.pop("duration_seconds", 3600), 3600)
        if action == "block" and not clean.get("expires_at") and not permanent:
            duration = max(60, min(duration, 7 * 86400))
            clean["expires_at"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=duration)).isoformat(timespec="seconds")
            clean["lease_seconds"] = duration
        if clean.get("expires_at"):
            try: dt.datetime.fromisoformat(str(clean["expires_at"]).replace("Z", "+00:00"))
            except ValueError as exc: raise ValueError("expires_at must be ISO-8601") from exc
        return clean

    def add(self, rule: dict[str, Any]) -> dict[str, Any]:
        clean = self.clean_rule(rule)
        clean["id"] = stable_id(utc_now(), clean)
        clean["created_at"] = utc_now()
        with self.lock:
            rules = self.list()
            rules.append(clean)
            self.save(rules)
        return {**clean, "active": True}

    def remove(self, rule_id: str) -> bool:
        with self.lock:
            rules = self.list()
            new = [r for r in rules if r.get("id") != rule_id]
            if len(new) == len(rules):
                return False
            self.save(new)
            return True


def apply_rule_preview(flows: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits = []
    now = dt.datetime.now(dt.timezone.utc)
    for rule in rules:
        expires = rule.get("expires_at")
        if expires:
            try:
                if dt.datetime.fromisoformat(expires.replace("Z", "+00:00")) <= now:
                    continue
            except ValueError:
                pass
        for flow in flows:
            app = flow.get("bundle_id") or flow.get("process") or ""
            host = endpoint_host(flow.get("remote", ""))
            port = endpoint_port(flow.get("remote", ""))
            match = True
            names = f"{flow.get('bundle_id') or ''} {flow.get('process') or ''}".lower()
            if rule.get("app") and rule["app"].lower() not in names:
                match = False
            if rule.get("domain") and not (host == rule["domain"] or host.endswith("." + rule["domain"])):
                match = False
            if rule.get("ip") and host != rule["ip"]:
                match = False
            if rule.get("port") and port != as_int(rule["port"]):
                match = False
            if match:
                hits.append({"rule_id": rule.get("id"), "action": rule.get("action"), "flow_id": flow.get("id"), "app": app, "remote": flow.get("remote")})
    return hits


def demo_events(now: float | None = None) -> list[dict[str, Any]]:
    """A plausible recent history for the simulated Mac so the Time Machine pane has something to show."""
    now = time.time() if now is None else now
    def at(minutes_ago: float) -> str:
        return dt.datetime.fromtimestamp(now - minutes_ago * 60, dt.timezone.utc).isoformat(timespec="seconds")
    return [
        {"ts": at(190), "kind": "interface", "title": "Interface en0 appeared", "detail": "active"},
        {"ts": at(142), "kind": "dns", "title": "DNS resolver changed", "detail": "('192.168.1.1',) → ('1.1.1.1', '2606:4700:4700::1111')"},
        {"ts": at(97), "kind": "vpn", "title": "VPN state changed", "detail": "Active: Zyvor WireGuard"},
        {"ts": at(64), "kind": "listener", "title": "New listening service on port 7000", "detail": "AirPlayXPCHelper · TCP · all"},
        {"ts": at(23), "kind": "traffic", "title": "Traffic rate spiked", "detail": "0.4 → 3.1 MB/s"},
    ]


def demo_snapshot(now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    flows = [
        {"id":"f1","process":"Google Chrome","pid":510,"bundle_id":"com.google.Chrome","protocol":"tcp","local":"192.168.1.42:53001","remote":"142.250.183.14:443","state":"ESTABLISHED","bytes_in":734003200,"bytes_out":31457280,"rx_bps":1843200.0,"tx_bps":92160.0,"total_bps":1935360.0,"interface":"en0","rtt_ms":31.2,"source":"demo"},
        {"id":"f2","process":"Slack","pid":602,"bundle_id":"com.tinyspeck.slackmacgap","protocol":"tcp","local":"192.168.1.42:53102","remote":"13.107.6.175:443","state":"ESTABLISHED","bytes_in":98566144,"bytes_out":12582912,"rx_bps":125000.0,"tx_bps":18000.0,"total_bps":143000.0,"interface":"utun4","rtt_ms":181.0,"source":"demo"},
        {"id":"f3","process":"Xcode","pid":711,"bundle_id":"com.apple.dt.Xcode","protocol":"tcp","local":"192.168.1.42:53200","remote":"github.com:443","state":"ESTABLISHED","bytes_in":67108864,"bytes_out":83886080,"rx_bps":245000.0,"tx_bps":530000.0,"total_bps":775000.0,"interface":"en0","rtt_ms":36.0,"source":"demo"},
        {"id":"f4","process":"fluxvm-vz-runner","pid":889,"bundle_id":"dev.zyvor.fluxvm","protocol":"tcp","local":"10.0.2.15:40544","remote":"github.com:443","state":"ESTABLISHED","bytes_in":52428800,"bytes_out":10485760,"rx_bps":92000.0,"tx_bps":22000.0,"total_bps":114000.0,"interface":"vmnet8","rtt_ms":42.0,"source":"demo"},
        {"id":"f5","process":"Safari","pid":420,"bundle_id":"com.apple.Safari","protocol":"tcp","local":"192.168.1.42:53310","remote":"17.253.144.10:443","state":"ESTABLISHED","bytes_in":210000000,"bytes_out":8400000,"rx_bps":640000.0,"tx_bps":42000.0,"total_bps":682000.0,"interface":"en0","rtt_ms":24.0,"source":"demo"},
        {"id":"f6","process":"Mail","pid":455,"bundle_id":"com.apple.mail","protocol":"tcp","local":"192.168.1.42:53311","remote":"17.57.144.52:993","state":"ESTABLISHED","bytes_in":9000000,"bytes_out":1200000,"rx_bps":31000.0,"tx_bps":6000.0,"total_bps":37000.0,"interface":"en0","rtt_ms":48.0,"source":"demo"},
        {"id":"f7","process":"Dropbox","pid":690,"bundle_id":"com.getdropbox.dropbox","protocol":"tcp","local":"192.168.1.42:53390","remote":"162.125.1.18:443","state":"ESTABLISHED","bytes_in":41000000,"bytes_out":160000000,"rx_bps":110000.0,"tx_bps":340000.0,"total_bps":450000.0,"interface":"en0","rtt_ms":55.0,"source":"demo"},
        {"id":"f8","process":"mDNSResponder","pid":118,"bundle_id":"","protocol":"udp","local":"192.168.1.42:5353","remote":"224.0.0.251:5353","state":"","bytes_in":220000,"bytes_out":140000,"rx_bps":1200.0,"tx_bps":900.0,"total_bps":2100.0,"interface":"en0","rtt_ms":0.0,"source":"demo"},
    ]
    # Make the demo breathe: rates oscillate per flow and byte counters advance with the same rates,
    # so charts, sparklines and the diff view have real shape instead of flat blocks.
    import math
    for i, f in enumerate(flows):
        scale = 1.0 + 0.55 * math.sin(now / 9.0 + i * 1.7) + 0.2 * math.sin(now / 3.1 + i)
        scale = max(0.05, scale)
        for k in ("rx_bps", "tx_bps"):
            f[k] = round(f[k] * scale, 2)
        f["total_bps"] = round(f["rx_bps"] + f["tx_bps"], 2)
        f["bytes_in"] += int(f["rx_bps"] * (now % 3600))
        f["bytes_out"] += int(f["tx_bps"] * (now % 3600))
    snap = {
        "version": VERSION,
        "timestamp": utc_now(),
        "host": {"name":"zyvor-mac-studio","os":"macOS","release":"27.2","arch":"arm64","demo":True},
        "interfaces": [
            {"name":"en0","flags":["UP","RUNNING"],"ipv4":["192.168.1.42"],"ipv6":["fe80::1"],"mac":"00:11:22:33:44:55","mtu":1500,"status":"active","kind":"wifi","hardware_port":"Wi-Fi"},
            {"name":"utun4","flags":["UP","RUNNING"],"ipv4":[],"ipv6":["fe80::4"],"mac":"","mtu":1380,"status":"active","kind":"vpn"},
            {"name":"vmnet8","flags":["UP","RUNNING"],"ipv4":["10.0.2.1"],"ipv6":[],"mac":"","mtu":1500,"status":"active","kind":"virtual"},
        ],
        "wifi": {"interface":"en0","ssid":"Zyvor Lab"},
        "routes": [
            {"family":"ipv4","destination":"default","gateway":"192.168.1.1","flags":"UGSc","interface":"en0","default":True},
            {"family":"ipv6","destination":"default","gateway":"fe80::1%en0","flags":"UGcg","interface":"en0","default":True},
        ],
        "dns": {"servers":["1.1.1.1","2606:4700:4700::1111"],"resolvers":[{"index":1,"nameservers":["1.1.1.1"],"interface":"en0","search":[]}]},
        "vpn": [{"name":"Zyvor WireGuard","service_id":"demo-vpn","status":"Connected","active":True}],
        "neighbors": [
            {"id":"n1","family":"ipv4","ip":"192.168.1.1","mac":"aa:bb:cc:dd:ee:01","interface":"en0","state":"reachable"},
            {"id":"n2","family":"ipv4","ip":"192.168.1.20","mac":"aa:bb:cc:dd:ee:20","interface":"en0","state":"reachable"},
        ],
        "listeners": [
            {"id":"l1","process":"nivora","pid":990,"protocol":"tcp","address":"127.0.0.1","port":9857,"state":"LISTEN","exposure":"loopback"},
            {"id":"l2","process":"AirPlayXPCHelper","pid":400,"protocol":"tcp","address":"*","port":7000,"state":"LISTEN","exposure":"all"},
        ],
        "flows": flows,
        "fluxvm": {"connected":True,"base_url":"http://127.0.0.1:7788","health":{"status":"ok"},"vms":[{"id":"macos-build-07","backend":"vz","state":"running"}],"sandboxes":[{"id":"agent-3dd91","state":"running"}],"network_health":{"status":"ok"},"network_endpoints":[{"id":"macos-build-07"}],"hubble_flows":{"flows":[{"source":"macos-build-07","destination":"github.com"}]},"network_observe":{},"network_telemetry":[]},
        "capabilities": {"nettop":True,"network_extension":True,"fluxvm":True,"blocking":False,"neighbors":True,"listeners":True},
    }
    snap["apps"] = aggregate_apps(flows)
    snap["traffic"] = compute_traffic(flows)
    snap["fluxvm"] = correlate_fluxvm(snap["fluxvm"], flows)
    snap["findings"] = derive_findings(snap)
    snap["health"] = compute_health(snap)
    snap["topology"] = build_topology(snap)
    snap["behavior"] = {"new_destinations": [], "known_destinations": 4}
    snap["recent_events"] = []
    return snap


class MacCollector:
    def __init__(self, runner: CommandRunner | None = None, fluxvm_url: str = "http://127.0.0.1:7788", fluxvm_token: str = "", demo: bool = False):
        self.runner = runner or CommandRunner()
        self.fluxvm = FluxVMProbe(fluxvm_url, fluxvm_token)
        self.demo = demo

    def collect(self, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.demo:
            snap = demo_snapshot()
            prev = {f.get("id"): f for f in (previous or {}).get("flows", [])}
            for f in snap["flows"]:
                f["first_seen"] = (prev.get(f["id"]) or {}).get("first_seen") or snap["timestamp"]
                f["last_seen"] = snap["timestamp"]
            snap["findings"] = derive_findings(snap, previous)
            snap["health"] = compute_health(snap)
            return snap
        is_mac = platform.system() == "Darwin"
        timestamp = utc_now()
        ifconfig = self.runner.run(["ifconfig", "-a"]) if is_mac else ""
        hardware_text = self.runner.run(["networksetup", "-listallhardwareports"]) if is_mac else ""
        routes4 = self.runner.run(["netstat", "-rn", "-f", "inet"]) if is_mac else ""
        routes6 = self.runner.run(["netstat", "-rn", "-f", "inet6"]) if is_mac else ""
        dns_text = self.runner.run(["scutil", "--dns"]) if is_mac else ""
        vpn_text = self.runner.run(["scutil", "--nc", "list"]) if is_mac else ""
        nettop_text = self.runner.run(["nettop", "-P", "-L", "1", "-x", "-J", "bytes_in,bytes_out,rtt_avg,state,interface"]) if is_mac else ""
        lsof_text = self.runner.run(["lsof", "-nP", "-iTCP", "-iUDP"]) if is_mac else ""
        arp_text = self.runner.run(["arp", "-an"]) if is_mac else ""
        ndp_text = self.runner.run(["ndp", "-an"]) if is_mac else ""
        extension_path = str(Path.home() / "Library/Group Containers/group.dev.zyvor.nivora/flows.jsonl")
        extension_flows = parse_extension_events(extension_path)
        lsof_rows = parse_lsof(lsof_text)
        cwd_text = self.runner.run(["lsof", "-nP", "-a", "-d", "cwd", "-Fpn"]) if is_mac else ""
        flows = extension_flows or parse_nettop(nettop_text)
        if not flows:
            flows = [x for x in lsof_rows if x.get("remote")]
        annotate_rates(flows, previous, timestamp)
        attribute_projects(flows, parse_lsof_cwd(cwd_text))
        interfaces = parse_ifconfig(ifconfig)
        ports = parse_networksetup_hardware_ports(hardware_text)
        enrich_interface_hardware(interfaces, ports)
        wifi_device = next((dev for dev, meta in ports.items() if "wi-fi" in meta.get("hardware_port", "").lower() or "airport" in meta.get("hardware_port", "").lower()), "")
        wifi_ssid = parse_airport_network(self.runner.run(["networksetup", "-getairportnetwork", wifi_device])) if is_mac and wifi_device else ""
        routes = parse_netstat_routes(routes4, "ipv4") + parse_netstat_routes(routes6, "ipv6")
        dns = parse_scutil_dns(dns_text)
        vpn = parse_scutil_nc(vpn_text)
        neighbors = parse_arp(arp_text) + parse_ndp(ndp_text)
        listeners = derive_listeners(lsof_rows)
        fluxvm = correlate_fluxvm(self.fluxvm.collect(), flows)
        snap: dict[str, Any] = {
            "version": VERSION,
            "timestamp": timestamp,
            "host": {
                "name": socket.gethostname(),
                "os": platform.system(),
                "release": platform.release(),
                "arch": platform.machine(),
                "demo": False,
            },
            "interfaces": interfaces,
            "wifi": {"interface": wifi_device, "ssid": wifi_ssid},
            "routes": routes,
            "dns": dns,
            "vpn": vpn,
            "neighbors": neighbors,
            "listeners": listeners,
            "flows": flows,
            "fluxvm": fluxvm,
            "capabilities": {
                "nettop": bool(nettop_text),
                "network_extension": bool(extension_flows),
                "fluxvm": fluxvm.get("connected", False),
                "blocking": bool(extension_flows),
                "neighbors": bool(arp_text or ndp_text),
                "listeners": bool(lsof_text),
            },
        }
        snap["apps"] = aggregate_apps(flows)
        snap["traffic"] = compute_traffic(flows)
        snap["findings"] = derive_findings(snap, previous)
        snap["health"] = compute_health(snap)
        snap["topology"] = build_topology(snap)
        return snap


def answer_query(snapshot: dict[str, Any], question: str) -> dict[str, Any]:
    q = question.lower().strip()
    flows = snapshot.get("flows", [])
    apps = snapshot.get("apps", [])
    findings = snapshot.get("findings", [])
    if not q:
        return {"answer":"Ask about traffic, apps, ports, VPN, DNS, health, new destinations, local devices, FluxVM, or suspicious activity.","evidence":[]}
    if any(x in q for x in ["health", "why is", "why did", "slow", "latency", "network problem", "internet problem"]):
        d = diagnose_network(snapshot)
        return {"answer": d["summary"] + f" Health score: {d['health'].get('score', 0)}/100.", "evidence": d.get("causes", []) or d.get("recent_events", [])}
    if any(x in q for x in ["new destination", "new domain", "never seen", "first seen"]):
        new = snapshot.get("behavior", {}).get("new_destinations", [])
        return {"answer": f"Nivora saw {len(new)} new destination(s) since the learned baseline.", "evidence": new[:30]}
    if any(x in q for x in ["local device", "neighbor", "lan device"]):
        rows = snapshot.get("neighbors", [])
        return {"answer": f"Nivora currently sees {len(rows)} local neighbor(s) in ARP/NDP caches.", "evidence": rows[:40]}
    if any(x in q for x in ["listening", "listener", "open port", "server port"]):
        rows = snapshot.get("listeners", [])
        exposed = [x for x in rows if x.get("exposure") == "all"]
        return {"answer": f"There are {len(rows)} listening socket(s); {len(exposed)} are bound to all interfaces.", "evidence": rows[:40]}
    m = re.search(r"(?:port\s+)?(\d{2,5})", q)
    if "port" in q and m:
        port = int(m.group(1))
        hits = [f for f in flows if endpoint_port(f.get("local", "")) == port or endpoint_port(f.get("remote", "")) == port]
        listeners = [x for x in snapshot.get("listeners", []) if x.get("port") == port]
        return {"answer": f"Found {len(hits)} flow(s) and {len(listeners)} listener(s) involving port {port}.", "evidence": (hits + listeners)[:30]}
    if any(x in q for x in ["upload", "sent", "outbound", "sending"]):
        top = sorted(apps, key=lambda a: (a.get("tx_bps", 0), a.get("bytes_out", 0)), reverse=True)[:5]
        if top:
            return {"answer": f"{top[0]['name']} is the largest outbound sender now ({top[0].get('tx_bps',0)/1024:.1f} KB/s; {top[0]['bytes_out']} bytes in its counter window).", "evidence": top}
    if any(x in q for x in ["download", "received", "inbound"]):
        top = sorted(apps, key=lambda a: (a.get("rx_bps", 0), a.get("bytes_in", 0)), reverse=True)[:5]
        if top:
            return {"answer": f"{top[0]['name']} is receiving the most now ({top[0].get('rx_bps',0)/1024:.1f} KB/s).", "evidence": top}
    if "vpn" in q:
        active = [v for v in snapshot.get("vpn", []) if v.get("active")]
        return {"answer": "VPN active: " + ", ".join(v["name"] for v in active) if active else "No active configured VPN was reported by scutil.", "evidence": active}
    if "dns" in q:
        return {"answer": "Current DNS servers: " + (", ".join(snapshot.get("dns", {}).get("servers", [])) or "none reported"), "evidence": snapshot.get("dns", {}).get("resolvers", [])}
    if "flux" in q or "vm" in q or "sandbox" in q:
        f = snapshot.get("fluxvm", {})
        answer = "FluxVM is connected." if f.get("connected") else "FluxVM did not answer on the configured local API endpoint."
        if f.get("connected"):
            answer += f" Nivora sees {f.get('network_endpoint_count',0)} FluxVM network endpoint(s), {f.get('hubble_flow_count',0)} Hubble flow(s), and {f.get('host_flow_count',0)} host-attributed flow(s)."
        return {"answer": answer, "evidence": [f]}
    if any(x in q for x in ["suspicious", "security", "overnight", "bad"]):
        return {"answer": f"Nivora has {len(findings)} current finding(s).", "evidence": findings[:20]}
    if any(x in q for x in ["what changed", "changed recently", "recent change"]):
        recent = snapshot.get("recent_events", [])
        return {"answer": f"There are {len(recent)} recent network event(s) attached to the current snapshot.", "evidence": recent[-20:]}
    for app in apps:
        if app["name"].lower() in q:
            af = [f for f in flows if process_display_name(f.get("process", "")).lower() == app["name"].lower()]
            return {"answer": f"{app['name']} has {app['connections']} observed connection(s), {app.get('rx_bps',0)/1024:.1f} KB/s in and {app.get('tx_bps',0)/1024:.1f} KB/s out.", "evidence": af[:20]}
    return {"answer": "I could not map that question to a local network fact yet. Try asking which app is uploading, what uses a port, what changed, whether VPN/DNS is healthy, what local devices are visible, or what FluxVM VMs are doing.", "evidence": []}

