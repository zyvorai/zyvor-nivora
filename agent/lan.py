# SPDX-License-Identifier: BUSL-1.1
"""Local-network change detection: IP->MAC changes, gateway MAC changes and Wi-Fi network changes."""
from __future__ import annotations

from typing import Any


def _default_gateways(snapshot: dict[str, Any]) -> set[str]:
    return {r.get("gateway") for r in snapshot.get("routes") or [] if r.get("default") and r.get("gateway")}


def _mac_by_ip(snapshot: dict[str, Any]) -> dict[str, str]:
    return {n["ip"]: n["mac"].lower() for n in snapshot.get("neighbors") or [] if n.get("ip") and n.get("mac")}


def diff_lan(current: dict[str, Any], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Findings from comparing two consecutive snapshots."""
    if not previous:
        return []
    out: list[dict[str, Any]] = []
    prev, cur = _mac_by_ip(previous), _mac_by_ip(current)
    gateways = _default_gateways(current)
    for ip, mac in sorted(cur.items()):
        old = prev.get(ip)
        if not old or old == mac:
            continue
        gw = ip in gateways
        out.append({
            "severity": "critical" if gw else "warning", "kind": "lan",
            "title": "Gateway MAC address changed" if gw else f"MAC address changed for {ip}",
            "detail": f"{ip} moved from {old} to {mac}. This can be a device swap, DHCP reuse, or ARP spoofing.",
            "remote": ip,
        })
    old_ssid = (previous.get("wifi") or {}).get("ssid") or ""
    new_ssid = (current.get("wifi") or {}).get("ssid") or ""
    if old_ssid and new_ssid and old_ssid != new_ssid:
        out.append({"severity": "info", "kind": "lan", "title": "Wi-Fi network changed", "detail": f"{old_ssid} → {new_ssid}"})
    return out


def dns_vpn_leak(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """With a VPN active, resolvers that are only reachable outside the tunnel can leak queries."""
    if not any(v.get("active") for v in snapshot.get("vpn") or []):
        return []
    resolvers = [r for r in (snapshot.get("dns") or {}).get("resolvers") or [] if r.get("nameservers")]
    tunnel = lambda r: str(r.get("interface") or "").startswith(("utun", "ppp", "ipsec"))
    if not resolvers or any(tunnel(r) for r in resolvers):
        return []
    outside = sorted({ns for r in resolvers for ns in r["nameservers"]})
    return [{"severity": "warning", "kind": "dns", "title": "DNS may bypass the VPN",
             "detail": "A VPN is active but no resolver is bound to a tunnel interface: " + ", ".join(outside[:4]) + "."}]
