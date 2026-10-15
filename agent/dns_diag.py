# SPDX-License-Identifier: BUSL-1.1
"""Short, explainable diagnosis of the resolver configuration from parse_scutil_dns output."""
from __future__ import annotations

from typing import Any

PUBLIC = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "2606:4700:4700::1111", "2001:4860:4860::8888"}


def _private(s: str) -> bool:
    return s.startswith(("10.", "192.168.", "fd", "fe80:")) or any(s.startswith(f"172.{n}.") for n in range(16, 32))


def diagnose_resolvers(dns: dict[str, Any]) -> dict[str, Any]:
    servers = dns.get("servers") or []
    notes = []
    if not servers:
        notes.append("No nameservers configured")
    public = [s for s in servers if s in PUBLIC]
    if public:
        notes.append("Public resolver in use: " + ", ".join(public))
    if any(_private(s) for s in servers):
        notes.append("Private/internal resolver detected")
    return {"server_count": len(servers), "resolver_count": len(dns.get("resolvers") or []),
            "public": bool(public), "notes": notes}
