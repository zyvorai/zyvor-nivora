#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from capture import CaptureClient, CaptureError, manual_command, synthetic_pcap, validate_request, validate_session_id, MAX_SECONDS, MAX_MB, MAX_SNAPLEN
from nivora_core import HistoryStore, MacCollector, RuleStore, answer_query, apply_rule_preview, compute_health, diagnose_network, filter_flows, timeline_events, Redactor, build_bundle, export_rows, render_export


class State:
    def __init__(self, args):
        self.args = args
        self.collector = MacCollector(fluxvm_url=args.fluxvm_url, fluxvm_token=args.fluxvm_token, demo=args.demo)
        self.history = None if args.no_history else HistoryStore(args.database)
        try:
            self.rules = RuleStore(args.rules)
        except OSError:
            # An unsigned build cannot create the App Group container; keep running with a per-user
            # rules file. The NetworkExtension only sees rules once the signed group container exists.
            fallback = os.path.expanduser("~/.local/share/nivora/rules.json")
            self.rules = RuleStore(fallback)
            args.rules = fallback
        self.capture = CaptureClient()
        self.demo_captures = {}
        self._capture_ok = (0.0, False)
        self.snapshot = None
        self.timeline = []
        self.lock = threading.Lock()
        self.stop = threading.Event()

    # ---- packet capture (opt-in, headers-only by default; see agent/capture.py) ----
    def capture_available(self):
        if self.args.demo:
            return True
        checked, ok = self._capture_ok
        if time.time() - checked > 5:
            ok = self.capture.available()
            self._capture_ok = (time.time(), ok)
        return ok

    def _capture_event(self, title, detail):
        event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()), "kind": "capture", "title": title, "detail": detail}
        with self.lock:
            self.timeline.append(event)
            self.timeline = self.timeline[-1000:]
        if self.history:
            self.history.add_events([event])

    def capture_list(self):
        if self.args.demo:
            now = time.time()
            out = []
            for c in self.demo_captures.values():
                sess = dict(c["session"])
                if sess["state"] == "running" and now - c["t0"] >= min(sess["seconds"], 3):
                    sess["state"] = "finished"
                    c["session"]["state"] = "finished"
                sess["bytes"] = len(c["pcap"])
                out.append(sess)
            return out
        return self.capture.list()

    def capture_start(self, body):
        if body.get("confirm") is not True:
            raise CaptureError("confirmation required: capture records packet headers of this traffic")
        with self.lock:
            ifaces = {i.get("name") for i in (self.snapshot or {}).get("interfaces", [])}
        req = validate_request(body, ifaces or None)
        if not self.capture_available():
            err = CaptureError("capture helper is not installed or not running. Equivalent manual command: " + manual_command(req), 501)
            raise err
        flt = " ".join(x for x in [req.get("host") and f"host {req['host']}", req["proto"] != "any" and req["proto"], req.get("port") and f"port {req['port']}"] if x) or "all traffic"
        if self.args.demo:
            sid = os.urandom(8).hex()
            session = {"id": sid, "iface": req["iface"], "filter": flt, "snaplen": req["snaplen"], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "seconds": req["seconds"], "max_bytes": req["max_mb"] * 1048576, "state": "running", "bytes": 0}
            self.demo_captures[sid] = {"session": session, "t0": time.time(), "pcap": synthetic_pcap(48, req["snaplen"])}
        else:
            session = self.capture.start(req)
        self._capture_event("Packet capture started", f"{req['iface']} · {flt} · {req['snaplen']} bytes/packet · ≤{req['seconds']} s")
        return session

    def capture_stop(self, sid):
        validate_session_id(sid)
        if self.args.demo:
            c = self.demo_captures.get(sid)
            if not c:
                raise CaptureError("no such capture", 404)
            c["session"]["state"] = "stopped"
        else:
            self.capture.stop(sid)
        self._capture_event("Packet capture stopped", sid)

    def capture_delete(self, sid):
        validate_session_id(sid)
        if self.args.demo:
            if self.demo_captures.pop(sid, None) is None:
                raise CaptureError("no such capture", 404)
        else:
            self.capture.delete(sid)
        self._capture_event("Packet capture deleted", sid)

    def capture_pcap(self, sid):
        validate_session_id(sid)
        if self.args.demo:
            c = self.demo_captures.get(sid)
            if not c:
                raise CaptureError("no such capture", 404)
            return c["pcap"]
        return self.capture.fetch(sid)

    def sample(self):
        with self.lock:
            previous = self.snapshot
            existing_timeline = list(self.timeline)
        current = self.collector.collect(previous)
        events = timeline_events(current, previous)
        behavior = {"new_destinations": [], "known_destinations": 0}
        if self.history:
            behavior = self.history.observe_behavior(current)
            for event in behavior.get("new_destinations", []):
                events.append(event)
                current.setdefault("findings", []).append({
                    "severity": "warning", "kind": "behavior", "title": event["title"],
                    "detail": event["detail"], "app": event.get("app"), "remote": event.get("remote")
                })
        current["behavior"] = behavior
        current.setdefault("capabilities", {})["capture"] = self.capture_available()
        current["rules"] = self.rules.list()
        current["rule_hits"] = apply_rule_preview(current.get("flows", []), current["rules"])
        current["recent_events"] = (existing_timeline + events)[-20:]
        current["health"] = compute_health(current)
        current["diagnosis"] = diagnose_network(current)
        with self.lock:
            self.snapshot = current
            self.timeline.extend(events)
            self.timeline = self.timeline[-1000:]
        if self.history:
            self.history.add_snapshot(current)
            self.history.add_events(events)
        return current

    def loop(self):
        while not self.stop.is_set():
            try:
                self.sample()
            except Exception as exc:
                print(f"nivora: sample failed: {exc}", flush=True)
            self.stop.wait(self.args.interval)


class Handler(BaseHTTPRequestHandler):
    server_version = "Nivora/0.1"

    def log_message(self, fmt, *args):
        if not self.server.state.args.quiet:
            super().log_message(fmt, *args)

    @property
    def state(self):
        return self.server.state

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        if origin in self.state.args.allow_origin:
            return True
        # Browsers attach Origin to module-script fetches and same-origin POSTs; accept the
        # dashboard's own loopback origin (Host must be loopback, so no cross-site access).
        host = (self.headers.get("Host") or "").lower()
        name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        return origin.lower() == f"http://{host}" and name in {"127.0.0.1", "localhost", "[::1]"}

    def _authorized(self):
        if self.path == "/healthz" or not self.path.startswith("/v1/"):
            return True
        expected = self.state.args.token
        if not expected:
            return True
        return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {expected}")

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin and origin in self.state.args.allow_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")

    def _json(self, obj, status=200):
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(body)

    def _capture_call(self, fn):
        """Runs a capture operation; maps CaptureError to an HTTP error (and returns None)."""
        try:
            return fn()
        except CaptureError as exc:
            self._json({"error": str(exc)}, exc.status)
            return None

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n > 1_000_000:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _guard(self):
        if not self._origin_ok():
            self._json({"error":"origin not allowed"}, 403)
            return False
        if not self._authorized():
            self._json({"error":"unauthorized"}, 401)
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        u = urlparse(self.path)
        path = u.path
        if path == "/healthz":
            return self._json({"status":"ok","product":"nivora"})
        if path.startswith("/v1/"):
            with self.state.lock:
                snap = self.state.snapshot
                timeline = list(self.state.timeline)
            if snap is None:
                snap = self.state.sample()
            mapping = {
                "/v1/snapshot": snap,
                "/v1/flows": filter_flows(snap.get("flows", []), parse_qs(u.query).get("filter", [""])[0][:400]),
                "/v1/apps": snap.get("apps", []),
                "/v1/interfaces": snap.get("interfaces", []),
                "/v1/routes": snap.get("routes", []),
                "/v1/dns": snap.get("dns", {}),
                "/v1/vpn": snap.get("vpn", []),
                "/v1/fluxvm": snap.get("fluxvm", {}),
                "/v1/findings": snap.get("findings", []),
                "/v1/health": snap.get("health", {}),
                "/v1/traffic": snap.get("traffic", {}),
                "/v1/topology": snap.get("topology", {}),
                "/v1/neighbors": snap.get("neighbors", []),
                "/v1/listeners": snap.get("listeners", []),
                "/v1/behavior": snap.get("behavior", {}),
                "/v1/diagnose": snap.get("diagnosis") or diagnose_network(snap),
                "/v1/rules": self.state.rules.list(),
                "/v1/timeline": (self.state.history.events(500) if self.state.history else timeline),
            }
            if path in mapping:
                return self._json(mapping[path])
            if path == "/v1/captures":
                available = self.state.capture_available()
                sessions = []
                if available:
                    try:
                        sessions = self.state.capture_list()
                    except CaptureError:
                        available = False
                return self._json({"available": available, "demo": bool(self.state.args.demo),
                                   "limits": {"max_seconds": MAX_SECONDS, "max_mb": MAX_MB, "max_snaplen": MAX_SNAPLEN},
                                   "sessions": sessions})
            m = re.match(r"^/v1/captures/([0-9a-f]{16})/pcap$", path)
            if m:
                data = self._capture_call(lambda: self.state.capture_pcap(m.group(1)))
                if data is None:
                    return
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/vnd.tcpdump.pcap")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'attachment; filename="nivora-{m.group(1)}.pcap"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/v1/export":
                return self._export(parse_qs(u.query), snap, timeline)
            if path in {"/v1/history", "/v1/series"}:
                try: limit = int(parse_qs(u.query).get("limit", [120])[0])
                except (TypeError, ValueError): limit = 120
                if not self.state.history: return self._json([])
                return self._json(self.state.history.series(limit) if path == "/v1/series" else self.state.history.history(limit))
            return self._json({"error":"not found"}, 404)
        return self._static(path)

    def _export(self, q, snap, timeline):
        kind = q.get("kind", ["flows"])[0]
        fmt = q.get("format", ["csv"])[0]
        query = q.get("filter", [""])[0][:400]
        redactor = Redactor() if q.get("redact", ["0"])[0] in {"1", "true", "yes"} else None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            if kind in {"bundle", "snapshot"} and fmt in {"zip", "json"}:
                if kind == "bundle" or fmt == "zip":
                    body, ctype, name = build_bundle(snap, timeline, query, redactor), "application/zip", f"nivora-bundle-{stamp}.zip"
                else:
                    data = redactor.walk(snap) if redactor else snap
                    body, ctype, name = json.dumps(data, indent=2).encode(), "application/json", f"nivora-snapshot-{stamp}.json"
            else:
                rows = export_rows(snap, timeline, kind, query)
                if redactor:
                    rows = redactor.walk(rows)
                body, ctype = render_export(rows, kind, fmt)
                name = f"nivora-{kind}-{stamp}.{fmt}"
        except (ValueError, KeyError) as exc:
            return self._json({"error": str(exc)}, 400)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self._guard():
            return
        path = urlparse(self.path).path
        try:
            data = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error":str(exc)}, 400)
        if path == "/v1/query":
            with self.state.lock:
                snap = self.state.snapshot
            if snap is None:
                snap = self.state.sample()
            return self._json(answer_query(snap, str(data.get("question", ""))))
        if path == "/v1/captures":
            session = self._capture_call(lambda: self.state.capture_start(data))
            if session is not None:
                self._json(session, 201)
            return
        m = re.match(r"^/v1/captures/([0-9a-f]{16})/stop$", path)
        if m:
            if self._capture_call(lambda: self.state.capture_stop(m.group(1)) or True):
                self._json({"stopped": True})
            return
        if path == "/v1/rules":
            try:
                rule = self.state.rules.add(data)
            except ValueError as exc:
                return self._json({"error":str(exc)}, 400)
            return self._json(rule, 201)
        return self._json({"error":"not found"}, 404)

    def do_DELETE(self):
        if not self._guard():
            return
        path = urlparse(self.path).path
        m = re.match(r"^/v1/captures/([0-9a-f]{16})$", path)
        if m:
            if self._capture_call(lambda: self.state.capture_delete(m.group(1)) or True):
                self._json({"deleted": True})
            return
        prefix = "/v1/rules/"
        if path.startswith(prefix):
            ok = self.state.rules.remove(path[len(prefix):])
            return self._json({"deleted":ok}, 200 if ok else 404)
        return self._json({"error":"not found"}, 404)

    def _static(self, path):
        root = Path(self.state.args.web_root).resolve()
        rel = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (root / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            if "." not in Path(rel).name:
                target = root / "index.html"
            else:
                self.send_error(404)
                return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)


def parser():
    p = argparse.ArgumentParser(description="Nivora macOS network intelligence collector")
    p.add_argument("--once", action="store_true")
    p.add_argument("--demo", action="store_true", help="use deterministic simulated Mac telemetry")
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9857)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--token", default=os.getenv("NIVORA_TOKEN", ""))
    p.add_argument("--allow-origin", action="append", default=[])
    p.add_argument("--database", default="~/.local/share/nivora/history.sqlite")
    p.add_argument("--rules", default="~/Library/Group Containers/group.dev.zyvor.nivora/rules.json")
    p.add_argument("--no-history", action="store_true")
    p.add_argument("--fluxvm-url", default=os.getenv("FLUXVM_SERVER", "http://127.0.0.1:7788"))
    p.add_argument("--fluxvm-token", default=os.getenv("FLUXVM_TOKEN", ""))
    p.add_argument("--web-root", default=str(Path(__file__).resolve().parent.parent / "web"))
    p.add_argument("--quiet", action="store_true")
    return p


def main():
    args = parser().parse_args()
    state = State(args)
    first = state.sample()
    if args.once:
        print(json.dumps(first, indent=2))
        return 0
    if not args.token:
        args.token = secrets.token_urlsafe(24)
    if args.bind not in {"127.0.0.1", "::1", "localhost"} and not args.token:
        raise SystemExit("refusing non-loopback bind without token")
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.state = state
    thread = threading.Thread(target=state.loop, name="nivora-sampler", daemon=True)
    thread.start()
    print(f"Nivora listening at http://{args.bind}:{args.port}")
    print(f"Open: http://{args.bind}:{args.port}/#token={args.token}")
    print(f"NIVORA_TOKEN={args.token}")
    print("The URL fragment stays in the browser and is removed after the page reads it.")

    def stop(*_):
        state.stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        state.stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
