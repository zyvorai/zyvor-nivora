#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Read-only MCP server (stdio, JSON-RPC 2.0) over the local Nivora API. Stdlib only.

Configure with NIVORA_URL (default http://127.0.0.1:9857) and NIVORA_TOKEN. No tool changes rules or state;
`path_check` only opens a DNS/TCP/TLS connection to the destination you name.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    from nivora_core import VERSION
except ImportError:  # copied somewhere without its siblings
    VERSION = "unknown"

PROTOCOL = "2024-11-05"
URL = os.getenv("NIVORA_URL", "http://127.0.0.1:9857").rstrip("/")
TOKEN = os.getenv("NIVORA_TOKEN", "")


def _api(path: str, body: dict[str, Any] | None = None) -> Any:
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(URL + path, data=data, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _summary() -> Any:
    s = _api("/v1/snapshot")
    return {"host": s.get("host"), "health": s.get("health"), "traffic": s.get("traffic"),
            "counts": {k: len(s.get(k) or []) for k in ("apps", "flows", "findings", "listeners", "neighbors")},
            "top_apps": (s.get("apps") or [])[:5], "findings": (s.get("findings") or [])[:10]}


def _qs(**kw: Any) -> str:
    q = {k: v for k, v in kw.items() if v}
    return "?" + urllib.parse.urlencode(q) if q else ""


def _schema(props: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props or {}, "required": required or []}


STR = {"type": "string"}
TOOLS: dict[str, tuple[str, dict[str, Any], Any]] = {
    "summary": ("Health, traffic, counts, top apps and current findings.", _schema(), lambda a: _summary()),
    "flows": ("Live flows, optionally filtered (e.g. 'app:Safari port:443 >1mbps').", _schema({"filter": STR}),
              lambda a: _api("/v1/flows" + _qs(filter=a.get("filter")))[:100]),
    "findings": ("Current findings with severity.", _schema(), lambda a: _api("/v1/findings")),
    "explain_flow": ("Evidence and reasons for one flow id.", _schema({"flow_id": STR}, ["flow_id"]),
                     lambda a: _api("/v1/flows/" + urllib.parse.quote(str(a["flow_id"]), safe="") + "/explain")),
    "ask": ("Ask the deterministic investigator a question about the network.", _schema({"question": STR}, ["question"]),
            lambda a: _api("/v1/query", {"question": str(a["question"])})),
    "diff": ("Compare two points in time (ISO 8601). Defaults to the last 30 minutes.", _schema({"from": STR, "to": STR}),
             lambda a: _api("/v1/diff" + _qs(**{"from": a.get("from"), "to": a.get("to")}))),
    "incident": ("Narrative of what changed in a time window (ISO 8601).", _schema({"from": STR, "to": STR}),
                 lambda a: _api("/v1/incident" + _qs(**{"from": a.get("from"), "to": a.get("to")}))),
    "port_conflicts": ("Ports bound by more than one process.", _schema(), lambda a: _api("/v1/port-conflicts")),
    "rule_impact": ("What each rule (including shadow rules) matches right now.", _schema(), lambda a: _api("/v1/rule-impact")),
    "trust": ("Explainable 0-100 trust score per app.", _schema(), lambda a: _api("/v1/trust")),
    "privacy": ("Privacy report card: trackers, cleartext, DNS-over-VPN leak, unsigned apps.", _schema(), lambda a: _api("/v1/privacy-report")),
    "egress": ("Per-sandbox/VM destinations seen through FluxVM.", _schema(), lambda a: _api("/v1/egress")),
    "usage": ("Today's per-app usage against any budgets.", _schema(), lambda a: _api("/v1/usage")),
    "listeners": ("Listening sockets with owning process.", _schema(), lambda a: _api("/v1/listeners")),
    "fluxvm": ("FluxVM workloads, endpoints and Hubble flows.", _schema(), lambda a: _api("/v1/fluxvm")),
    "profiles": ("Situation profiles and which one is active (read only).", _schema(), lambda a: _api("/v1/profiles")),
    "timeline": ("Time Machine events: interface, DNS, route, VPN, listener and LAN changes.", _schema(), lambda a: _api("/v1/timeline")),
    "path_check": ("DNS, TCP and TLS reachability check for one host/port.", _schema({"host": STR, "port": {"type": "integer"}}, ["host"]),
                   lambda a: _api("/v1/path-check", {"host": a.get("host"), "port": a.get("port")})),
}


RESOURCES = {
    "nivora://snapshot": ("Current summary", "Health, traffic, counts, top apps and findings.", _summary),
    "nivora://findings": ("Current findings", "Findings with severity.", lambda: _api("/v1/findings")),
}
PROMPTS = {
    "incident_review": ("Review what changed on this Mac's network in a time window.",
                        [{"name": "from", "description": "ISO 8601 start (default: 30 minutes ago)", "required": False},
                         {"name": "to", "description": "ISO 8601 end (default: now)", "required": False}],
                        lambda a: "Use the nivora `incident` tool" + (f" with from={a['from']!r}" if a.get("from") else "")
                        + (f" and to={a['to']!r}" if a.get("to") else "")
                        + ", then `diff` for detail. Explain what changed, the most likely cause and what to check next. "
                          "Use only the data the tools return; say when something cannot be determined."),
    "network_checkup": ("A short health, trust and privacy check-up.", [],
                        lambda a: "Call the nivora `summary`, `trust` and `privacy` tools. Report the health score, any critical or warning "
                                  "findings, the lowest-trust apps and privacy issues, in a few bullets, most important first."),
}


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification
        return None

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code: int, text: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": text}}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL, "capabilities": {"tools": {}, "resources": {}, "prompts": {}}, "serverInfo": {"name": "nivora", "version": VERSION}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in TOOLS.items()]})
    if method == "resources/list":
        return ok({"resources": [{"uri": u, "name": n, "description": d, "mimeType": "application/json"} for u, (n, d, _) in RESOURCES.items()]})
    if method == "resources/read":
        uri = (msg.get("params") or {}).get("uri")
        res = RESOURCES.get(uri)
        if not res:
            return err(-32602, f"unknown resource {uri!r}")
        try:
            return ok({"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(res[2](), indent=2)}]})
        except (urllib.error.URLError, OSError, ValueError) as e:
            return err(-32603, f"Nivora API unavailable: {e}")
    if method == "prompts/list":
        return ok({"prompts": [{"name": n, "description": d, "arguments": a} for n, (d, a, _) in PROMPTS.items()]})
    if method == "prompts/get":
        params = msg.get("params") or {}
        prompt = PROMPTS.get(params.get("name"))
        if not prompt:
            return err(-32602, f"unknown prompt {params.get('name')!r}")
        text = prompt[2](params.get("arguments") or {})
        return ok({"description": prompt[0], "messages": [{"role": "user", "content": {"type": "text", "text": text}}]})
    if method == "tools/call":
        params = msg.get("params") or {}
        tool = TOOLS.get(params.get("name"))
        if not tool:
            return err(-32602, f"unknown tool {params.get('name')!r}")
        try:
            out = tool[2](params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(out, indent=2)}]})
        except urllib.error.HTTPError as e:
            return ok({"isError": True, "content": [{"type": "text", "text": f"Nivora API HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"}]})
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            return ok({"isError": True, "content": [{"type": "text", "text": f"Nivora API unavailable or bad request: {e}"}]})
    return err(-32601, f"method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
