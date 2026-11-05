# SPDX-License-Identifier: BUSL-1.1
"""Optional country/ASN labels for internet destinations from a user-supplied local CSV. No network lookups.

File format (header optional, `#` comments allowed): cidr,country,asn,org
    17.0.0.0/8,US,AS714,Apple
Longest prefix wins. Without the file nothing is added.
"""
from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from nivora_core import classify_remote, endpoint_host


class GeoTable:
    def __init__(self, rows: list[tuple]):
        self.rows = sorted(rows, key=lambda r: r[0].prefixlen, reverse=True)
        self._cache: dict[str, dict[str, str]] = {}

    @classmethod
    def load(cls, path: str) -> "GeoTable":
        rows = []
        try:
            text = Path(path).expanduser().read_text()
        except OSError:
            return cls([])
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("cidr"):
                continue
            cells = [c.strip() for c in line.split(",")]
            try:
                net = ipaddress.ip_network(cells[0], strict=False)
            except ValueError:
                continue
            cells += [""] * (4 - len(cells))
            rows.append((net, cells[1].upper(), cells[2], cells[3]))
        return cls(rows)

    def lookup(self, host: str) -> dict[str, str]:
        if host in self._cache:
            return self._cache[host]
        found: dict[str, str] = {}
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None:
            for net, country, asn, org in self.rows:
                if ip.version == net.version and ip in net:
                    found = {k: v for k, v in (("country", country), ("asn", asn), ("org", org)) if v}
                    break
        if len(self._cache) < 4096:
            self._cache[host] = found
        return found

    def annotate(self, flows: list[dict[str, Any]]) -> None:
        if not self.rows:
            return
        for f in flows:
            host = endpoint_host(f.get("remote", ""))
            if classify_remote(host) == "internet":
                info = self.lookup(host)
                if info:
                    f["geo"] = info
