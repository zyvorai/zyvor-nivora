# SPDX-License-Identifier: BUSL-1.1
"""Multi-Mac view. Workers push a compact summary to a coordinator; the coordinator never connects out
and there is no command channel."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any

STALE_AFTER = 120.0
MAX_HOSTS = 200


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    t = snapshot.get("traffic") or {}
    h = snapshot.get("health") or {}
    return {
        "host": (snapshot.get("host") or {}).get("name", "unknown"),
        "version": snapshot.get("version"), "timestamp": snapshot.get("timestamp"),
        "health": {"score": h.get("score"), "status": h.get("status")},
        "traffic": {"rx_bps": t.get("rx_bps", 0), "tx_bps": t.get("tx_bps", 0)},
        "counts": {k: len(snapshot.get(k) or []) for k in ("apps", "flows", "findings", "listeners")},
        "top_apps": [{"name": a.get("name"), "total_bps": a.get("total_bps", 0)} for a in (snapshot.get("apps") or [])[:3]],
        "findings": [{"severity": f.get("severity"), "title": f.get("title")} for f in (snapshot.get("findings") or [])[:5]],
    }


class FleetStore:
    def __init__(self, clock=time.time):
        self.clock, self.hosts, self.lock = clock, {}, threading.Lock()

    def accept(self, summary: Any) -> dict[str, Any]:
        if not isinstance(summary, dict) or not isinstance(summary.get("host"), str) or not summary["host"] or len(summary["host"]) > 128:
            raise ValueError("summary needs a host name")
        if len(json.dumps(summary)) > 20_000:
            raise ValueError("summary too large")
        with self.lock:
            if summary["host"] not in self.hosts and len(self.hosts) >= MAX_HOSTS:
                raise ValueError("too many hosts")
            self.hosts[summary["host"]] = {"summary": summary, "received": self.clock()}
        return {"ok": True}

    def listing(self) -> list[dict[str, Any]]:
        now = self.clock()
        with self.lock:
            rows = [{**v["summary"], "age_seconds": round(now - v["received"], 1), "stale": now - v["received"] > STALE_AFTER}
                    for v in self.hosts.values()]
        return sorted(rows, key=lambda r: ((r.get("health") or {}).get("score") or 0, r["host"]))


def push(url: str, token: str, summary: dict[str, Any], timeout: float = 5.0) -> bool:
    req = urllib.request.Request(url.rstrip("/") + "/v1/fleet/report", data=json.dumps(summary).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except (OSError, ValueError):
        return False
