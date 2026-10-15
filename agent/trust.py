# SPDX-License-Identifier: BUSL-1.1
"""Explainable per-app trust score (0-100). Every point is attributed to a visible component."""
from __future__ import annotations

from typing import Any

from privacy import tracker_category
from nivora_core import endpoint_host, endpoint_port

CLEARTEXT_PORTS = {21, 23, 80, 110, 143}


def _signing(flows: list[dict[str, Any]]) -> tuple[int, str]:
    ids = [f.get("identity") for f in flows if f.get("identity")]
    if not ids:
        return 20, "Signing identity not verified (collector could not read it)."
    if any(i.get("apple") for i in ids):
        return 40, "Signed by Apple."
    if any(i.get("signed") and not i.get("adhoc") and i.get("team_id") for i in ids):
        team = next(i["team_id"] for i in ids if i.get("team_id"))
        return 40, f"Signed by developer team {team}."
    if any(i.get("signed") and not i.get("adhoc") for i in ids):
        return 32, "Signed, but without a team identifier."
    if any(i.get("adhoc") for i in ids):
        return 25, "Ad-hoc signed (typical of local builds)."
    return 5, "Unsigned binary."


def trust_scores(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    flows = snapshot.get("flows") or []
    new = (snapshot.get("behavior") or {}).get("new_destinations") or []
    listeners = snapshot.get("listeners") or []
    by_app: dict[str, list[dict[str, Any]]] = {}
    for f in flows:
        by_app.setdefault(f.get("process") or "Unknown", []).append(f)
    out = []
    for app, fl in by_app.items():
        comps = []
        pts, why = _signing(fl)
        comps.append({"name": "Code signing", "points": pts, "max": 40, "detail": why})
        n_new = sum(1 for d in new if d.get("app") in {app, fl[0].get("bundle_id")})
        pts = 25 if n_new == 0 else 15 if n_new <= 2 else 5
        comps.append({"name": "Destination novelty", "points": pts, "max": 25,
                      "detail": "No new destinations since baseline." if not n_new else f"{n_new} new destination(s) since baseline."})
        trackers = sorted({endpoint_host(f.get("remote", "")) for f in fl if tracker_category(endpoint_host(f.get("remote", "")))})
        comps.append({"name": "Trackers", "points": max(0, 15 - 5 * len(trackers)), "max": 15,
                      "detail": "No known tracker hosts." if not trackers else "Contacts " + ", ".join(trackers[:3]) + "."})
        clear = sorted({endpoint_port(f.get("remote", "")) for f in fl if endpoint_port(f.get("remote", "")) in CLEARTEXT_PORTS})
        comps.append({"name": "Cleartext protocols", "points": 10 if not clear else 0, "max": 10,
                      "detail": "No cleartext protocol ports." if not clear else "Uses cleartext port(s) " + ", ".join(map(str, clear)) + "."})
        exposed = [l for l in listeners if l.get("process") == app and l.get("exposure") == "all"]
        comps.append({"name": "Listening exposure", "points": 10 if not exposed else 0, "max": 10,
                      "detail": "Not listening on all interfaces." if not exposed else f"Listening on all interfaces (port {exposed[0].get('port')})."})
        score = sum(c["points"] for c in comps)
        out.append({"app": app, "score": score, "level": "high" if score >= 80 else "medium" if score >= 55 else "low",
                    "flows": len(fl), "components": comps})
    return sorted(out, key=lambda x: x["score"])
