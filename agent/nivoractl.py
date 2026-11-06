#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""nivoractl: command line client for the local Nivora collector API. Stdlib only."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from nivora_core import VERSION
except ImportError:  # copied somewhere without its siblings
    VERSION = "unknown"

DEFAULT = os.getenv("NIVORA_URL", "http://127.0.0.1:9857")
RELEASES_API = "https://api.github.com/repos/zyvorai/zyvor-nivora/releases/latest"

# command -> (API path, help). Printed as pretty JSON.
GET_COMMANDS = {
    "interfaces": ("/v1/interfaces", "Network interfaces"),
    "routes": ("/v1/routes", "Routing table"),
    "dns": ("/v1/dns", "Resolver configuration"),
    "vpn": ("/v1/vpn", "VPN state"),
    "fluxvm": ("/v1/fluxvm", "FluxVM workloads and endpoints"),
    "findings": ("/v1/findings", "Current findings"),
    "timeline": ("/v1/timeline", "Time Machine events"),
    "rules": ("/v1/rules", "Rules"),
    "health": ("/v1/health", "Health score and components"),
    "traffic": ("/v1/traffic", "Live traffic rates"),
    "topology": ("/v1/topology", "Identity-first network map"),
    "neighbors": ("/v1/neighbors", "Local network neighbors"),
    "listeners": ("/v1/listeners", "Listening sockets"),
    "behavior": ("/v1/behavior", "Learned per-app destinations"),
    "diagnose": ("/v1/diagnose", "Network diagnosis"),
    "series": ("/v1/series", "Stored time series"),
    "usage": ("/v1/usage", "Daily per-app usage and budgets"),
    "projects": ("/v1/projects", "Flows by project folder"),
    "containers": ("/v1/containers", "Container runtime flows"),
    "port-conflicts": ("/v1/port-conflicts", "Ports bound by more than one process"),
    "trust": ("/v1/trust", "Per-app trust scores"),
    "privacy": ("/v1/privacy-report", "Privacy report card"),
    "egress": ("/v1/egress", "FluxVM sandbox egress"),
    "profiles": ("/v1/profiles", "Situation profiles"),
    "fleet": ("/v1/fleet", "Multi-Mac fleet summary"),
    "policy-export": ("/v1/policy/export", "Export rules as a policy document"),
    "rule-impact": ("/v1/rule-impact", "What each rule matches right now"),
}
SHELLS = ("zsh", "bash", "fish")


def keychain_token():
    if os.getenv("NIVORA_TOKEN"):
        return os.environ["NIVORA_TOKEN"]
    try:
        p = subprocess.run(["security", "find-generic-password", "-s", "dev.zyvor.nivora", "-a", os.getenv("USER", ""), "-w"],
                           capture_output=True, text=True, timeout=1)
        if p.returncode == 0:
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def request(base, path, token, method="GET", body=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read())


def table(rows, fields):
    rows = list(rows)
    widths = {k: max(len(label), *(len(str(r.get(k, ""))) for r in rows)) for k, label in fields}
    print("  ".join(label.ljust(widths[k]) for k, label in fields))
    print("  ".join("-" * widths[k] for k, _ in fields))
    for r in rows:
        print("  ".join(str(r.get(k, "")).ljust(widths[k]) for k, _ in fields))


APP_FIELDS = [("name", "APP"), ("connections", "CONN"), ("bytes_in", "RX"), ("bytes_out", "TX")]
FLOW_FIELDS = [("process", "APP"), ("protocol", "PROTO"), ("remote", "REMOTE"), ("interface", "IFACE"), ("state", "STATE")]


def build_parser():
    p = argparse.ArgumentParser(prog="nivoractl", description="Nivora local CLI")
    p.add_argument("--url", default=DEFAULT, help="collector base URL (env NIVORA_URL)")
    p.add_argument("--token", default=None, help="bearer token (env NIVORA_TOKEN, else the Keychain)")
    p.add_argument("--json", action="store_true", help="print compact JSON, including for apps and flows")
    p.add_argument("--watch", type=float, metavar="SECONDS", default=0, help="repeat the command every SECONDS")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    sub.add_parser("status", help="Host, capabilities and counts")
    sub.add_parser("apps", help="Applications with connections and bytes")
    sub.add_parser("flows", help="Live flows").add_argument("--filter", default="", help="e.g. app:Safari port:443 proto:tcp >1mbps")
    for name, (_path, text) in GET_COMMANDS.items():
        sub.add_parser(name, help=text)
    a = sub.add_parser("ask", help="Ask the local investigator")
    a.add_argument("question", nargs="+")
    a = sub.add_parser("rule-add", help="Add a rule (blocks lease for 1 hour by default)")
    a.add_argument("--action", choices=["observe", "allow", "block", "shadow"], default="observe")
    a.add_argument("--app")
    a.add_argument("--domain")
    a.add_argument("--ip")
    a.add_argument("--port", type=int)
    a.add_argument("--expires-at")
    a.add_argument("--duration", type=int, help="block lease seconds (default 3600)")
    a.add_argument("--permanent", action="store_true")
    a = sub.add_parser("rule-delete", help="Delete a rule")
    a.add_argument("id")
    a = sub.add_parser("explain", help="Why this flow? Evidence for one flow id")
    a.add_argument("flow_id")
    for c, text in (("diff", "Compare two points in time"), ("incident", "Narrative of what changed")):
        a = sub.add_parser(c, help=text)
        a.add_argument("--from", dest="since")
        a.add_argument("--to", dest="until")
    a = sub.add_parser("profile", help="Switch situation profile")
    a.add_argument("name")
    for c, text in (("policy-plan", "Dry-run a policy file"), ("policy-apply", "Apply a policy file")):
        a = sub.add_parser(c, help=text)
        a.add_argument("file", help='policy JSON file: {"name": ..., "rules": [...]}')
    a = sub.add_parser("path-check", help="DNS, TCP and TLS reachability check")
    a.add_argument("host")
    a.add_argument("--port", type=int, default=443)
    a = sub.add_parser("version", help="CLI and collector versions")
    a.add_argument("--check", action="store_true", help="also ask GitHub for the latest release (the only call off this Mac)")
    a = sub.add_parser("completion", help="Print a shell completion script")
    a.add_argument("shell", choices=SHELLS)
    return p


def subcommands(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def long_options(sp):
    return [o for a in sp._actions for o in a.option_strings if o.startswith("--") and o != "--help"]


def completion_script(shell, parser):
    cmds = subcommands(parser)
    names = list(cmds)
    opts = {n: long_options(sp) for n, sp in cmds.items() if long_options(sp)}
    if shell == "bash":
        cases = "".join(f"    {n}) COMPREPLY=($(compgen -W \"{' '.join(o)}\" -- \"$cur\")) ;;\n" for n, o in opts.items())
        return ("_nivoractl() {\n  local cur=${COMP_WORDS[COMP_CWORD]}\n"
                f"  if [ \"$COMP_CWORD\" -eq 1 ]; then COMPREPLY=($(compgen -W \"{' '.join(names)}\" -- \"$cur\")); return; fi\n"
                f"  case ${{COMP_WORDS[1]}} in\n{cases}  esac\n}}\ncomplete -F _nivoractl nivoractl\n")
    if shell == "zsh":
        described = " ".join(f"'{n}'" for n in names)
        cases = "".join(f"    {n}) compadd -- {' '.join(o)} ;;\n" for n, o in opts.items())
        return ("#compdef nivoractl\n_nivoractl() {\n"
                f"  local -a cmds; cmds=({described})\n"
                "  if (( CURRENT == 2 )); then _describe 'command' cmds; return; fi\n"
                f"  case $words[2] in\n{cases}  esac\n}}\ncompdef _nivoractl nivoractl\n")
    lines = [f"complete -c nivoractl -f -n __fish_use_subcommand -a '{n}'" for n in names]
    for n, o in opts.items():
        lines += [f"complete -c nivoractl -n '__fish_seen_subcommand_from {n}' -l {x[2:]}" for x in o]
    return "\n".join(lines) + "\n"


def parse_version(text):
    parts = []
    for piece in str(text).lstrip("vV").split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def fetch_latest_release():
    req = urllib.request.Request(RELEASES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "nivoractl"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read()).get("tag_name", "")


def version_info(args, fetch=fetch_latest_release):
    info = {"cli": VERSION, "collector": None}
    try:
        info["collector"] = request(args.url, "/v1/snapshot", args.token).get("version")
    except (urllib.error.URLError, OSError, ValueError):
        pass
    if args.check:
        try:
            latest = fetch()
            info["latest"] = latest.lstrip("v")
            info["update_available"] = parse_version(latest) > parse_version(VERSION)
        except (urllib.error.URLError, OSError, ValueError) as e:
            info["latest"] = None
            info["check_error"] = str(getattr(e, "reason", e))
    return info


def execute(args):
    """Returns (data, table_fields); table_fields is set when a table is the default rendering."""
    url, token = args.url, args.token
    cmd = args.cmd
    if cmd == "status":
        s = request(url, "/v1/snapshot", token)
        return {"host": s["host"], "capabilities": s["capabilities"], "apps": len(s["apps"]),
                "flows": len(s["flows"]), "findings": len(s["findings"])}, None
    if cmd == "apps":
        return request(url, "/v1/apps", token), APP_FIELDS
    if cmd == "flows":
        query = "?" + urllib.parse.urlencode({"filter": args.filter}) if args.filter else ""
        return request(url, "/v1/flows" + query, token), FLOW_FIELDS
    if cmd in GET_COMMANDS:
        return request(url, GET_COMMANDS[cmd][0], token), None
    if cmd == "explain":
        return request(url, "/v1/flows/" + urllib.parse.quote(args.flow_id, safe="") + "/explain", token), None
    if cmd in ("diff", "incident"):
        q = urllib.parse.urlencode({k: v for k, v in (("from", args.since), ("to", args.until)) if v})
        return request(url, "/v1/" + cmd + ("?" + q if q else ""), token), None
    if cmd == "profile":
        return request(url, "/v1/profiles", token, "POST", {"name": args.name}), None
    if cmd in ("policy-plan", "policy-apply"):
        with open(args.file) as fh:
            policy = json.load(fh)
        return request(url, "/v1/policy", token, "POST", {"policy": policy, "dry_run": cmd == "policy-plan"}), None
    if cmd == "path-check":
        return request(url, "/v1/path-check", token, "POST", {"host": args.host, "port": args.port}), None
    if cmd == "ask":
        return request(url, "/v1/query", token, "POST", {"question": " ".join(args.question)}), None
    if cmd == "rule-add":
        body = {k: getattr(args, k) for k in ("action", "app", "domain", "ip", "port", "expires_at") if getattr(args, k, None) is not None}
        if args.duration:
            body["duration_seconds"] = args.duration
        if args.permanent:
            body["permanent"] = True
        return request(url, "/v1/rules", token, "POST", body), None
    if cmd == "rule-delete":
        return request(url, "/v1/rules/" + args.id, token, "DELETE"), None
    if cmd == "version":
        return version_info(args), None
    raise SystemExit(f"unknown command {cmd}")


def render(data, fields, as_json):
    if as_json:
        print(json.dumps(data, separators=(",", ":")))
    elif fields:
        table(data, fields)
    else:
        print(json.dumps(data, indent=2))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "completion":
        sys.stdout.write(completion_script(args.shell, parser))
        return
    if args.token is None:
        args.token = keychain_token()
    try:
        while True:
            data, fields = execute(args)
            if args.watch > 0 and sys.stdout.isatty():
                sys.stdout.write("\033[H\033[2J")
            render(data, fields, args.json)
            if args.watch <= 0:
                return
            sys.stdout.flush()
            time.sleep(max(0.5, args.watch))
    except KeyboardInterrupt:
        return
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Nivora API: HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Nivora API unavailable: {e.reason}")


if __name__ == "__main__":
    main()
