# SPDX-License-Identifier: BUSL-1.1
"""Local privacy report card from the current snapshot. Hostname-based checks need hostnames in flow data."""
from __future__ import annotations

from typing import Any

from nivora_core import endpoint_host, endpoint_port

# Small bundled list; suffix match on the destination hostname. Extend `extra` via budgets-style local files later.
TRACKERS = {
    "doubleclick.net": "advertising", "googlesyndication.com": "advertising", "adnxs.com": "advertising",
    "criteo.com": "advertising", "taboola.com": "advertising", "outbrain.com": "advertising",
    "google-analytics.com": "analytics", "googletagmanager.com": "analytics", "scorecardresearch.com": "analytics",
    "mixpanel.com": "analytics", "segment.io": "analytics", "segment.com": "analytics", "amplitude.com": "analytics",
    "hotjar.com": "analytics", "app-measurement.com": "analytics", "branch.io": "attribution",
    "appsflyer.com": "attribution", "adjust.com": "attribution", "connect.facebook.net": "social",
}
CLEARTEXT = {21: "FTP", 23: "Telnet", 80: "HTTP", 110: "POP3", 143: "IMAP"}


def tracker_category(host: str) -> str:
    host = (host or "").lower().rstrip(".")
    for suffix, cat in TRACKERS.items():
        if host == suffix or host.endswith("." + suffix):
            return cat
    return ""


def _is_hostname(host: str) -> bool:
    return bool(host) and any(c.isalpha() for c in host) and ":" not in host


def privacy_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    flows = snapshot.get("flows") or []
    trackers: dict[tuple[str, str], dict[str, Any]] = {}
    clear: dict[tuple[str, str, int], dict[str, Any]] = {}
    named = 0
    for f in flows:
        host, port = endpoint_host(f.get("remote", "")), endpoint_port(f.get("remote", ""))
        app = f.get("process") or "Unknown"
        if _is_hostname(host):
            named += 1
            cat = tracker_category(host)
            if cat:
                trackers[(app, host)] = {"app": app, "host": host, "category": cat}
        if port in CLEARTEXT and host and not host.startswith(("127.", "::1")):
            clear[(app, host, port)] = {"app": app, "host": host, "port": port, "protocol": CLEARTEXT[port]}
    findings = snapshot.get("findings") or []
    leak = any(x.get("title") == "DNS may bypass the VPN" for x in findings)
    unsigned = sorted({x.get("app") for x in findings if x.get("kind") == "identity" and x.get("app")})
    notes = []
    if flows and named == 0:
        notes.append("No hostnames in flow data, so tracker checks could not run. The NetworkExtension provides hostnames.")
    score = max(0, 100 - 8 * len(trackers) - 10 * len(clear) - (15 if leak else 0) - 5 * len(unsigned))
    return {
        "score": score,
        "trackers": sorted(trackers.values(), key=lambda x: (x["app"], x["host"])),
        "cleartext": sorted(clear.values(), key=lambda x: (x["app"], x["host"], x["port"])),
        "dns_vpn_leak": leak,
        "unsigned_apps": unsigned,
        "vpn_active": any(v.get("active") for v in snapshot.get("vpn") or []),
        "flows": len(flows), "flows_with_hostnames": named, "notes": notes,
    }
