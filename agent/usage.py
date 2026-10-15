# SPDX-License-Identifier: BUSL-1.1
"""Daily per-app usage against optional budgets (`budgets.json`: {"app name substring": bytes_per_day})."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_budgets(path: str) -> dict[str, int]:
    try:
        raw = json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0}


def budget_status(usage: dict[str, int], budgets: dict[str, int]) -> list[dict[str, Any]]:
    out = []
    for needle, limit in budgets.items():
        used = sum(b for app, b in usage.items() if needle.lower() in app.lower())
        out.append({"match": needle, "limit_bytes": limit, "used_bytes": used,
                    "percent": round(100 * used / limit, 1), "exceeded": used > limit})
    return sorted(out, key=lambda x: x["percent"], reverse=True)


def budget_findings(status: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"severity": "warning", "kind": "budget", "title": f"Daily budget exceeded: {s['match']}",
             "detail": f"{s['used_bytes'] / 1048576:.0f} MB of {s['limit_bytes'] / 1048576:.0f} MB today ({s['percent']}%).",
             "app": s["match"]} for s in status if s["exceeded"]]
