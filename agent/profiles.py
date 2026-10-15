# SPDX-License-Identifier: BUSL-1.1
"""Situation profiles: coarse alert posture changes. Profiles never relax blocking rules or leases."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "default": {"label": "Default", "high_bandwidth_bps": 5 * 1024 * 1024, "budget_scale": 1.0, "hide_info": False,
                "about": "Standard thresholds."},
    "coding": {"label": "Coding", "high_bandwidth_bps": 20 * 1024 * 1024, "budget_scale": 1.0, "hide_info": False,
               "about": "Builds, pulls and container traffic are expected; only very high rates are flagged."},
    "presenting": {"label": "Presenting", "high_bandwidth_bps": 20 * 1024 * 1024, "budget_scale": 1.0, "hide_info": True,
                   "about": "Hides informational findings so nothing distracting appears on screen."},
    "travel": {"label": "Travel / hotspot", "high_bandwidth_bps": 1024 * 1024, "budget_scale": 0.5, "hide_info": False,
               "about": "Lower rate threshold and half the daily budgets to protect a metered connection."},
}


class ProfileStore:
    def __init__(self, path: str):
        self.path = Path(os.path.expanduser(path))

    def active(self) -> str:
        try:
            name = json.loads(self.path.read_text()).get("active", "default")
        except (OSError, ValueError, AttributeError):
            return "default"
        return name if name in PROFILES else "default"

    def set(self, name: str) -> str:
        if name not in PROFILES:
            raise ValueError("unknown profile; choose one of " + ", ".join(PROFILES))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"active": name}) + "\n")
        os.replace(tmp, self.path)
        return name

    def settings(self) -> dict[str, Any]:
        return {"name": self.active(), **PROFILES[self.active()]}

    def listing(self) -> dict[str, Any]:
        return {"active": self.active(), "profiles": [{"name": n, **p} for n, p in PROFILES.items()]}
