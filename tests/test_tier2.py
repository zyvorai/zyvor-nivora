# SPDX-License-Identifier: BUSL-1.1
import copy
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

import nivora_mcp
from diff import diff_snapshots, narrate_incident
from nivora_core import HistoryStore, demo_snapshot
from pathcheck import check_target, validate_target


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.a = demo_snapshot()
        self.b = copy.deepcopy(self.a)

    def test_identical_snapshots_have_no_changes(self):
        d = diff_snapshots(self.a, self.b)
        self.assertEqual((d["flows_added"], d["flows_removed"], d["listeners_added"], d["findings_new"]), ([], [], [], []))
        self.assertFalse(d["default_route_changed"])
        self.assertEqual(d["health"]["delta"], 0)

    def test_changes_are_reported(self):
        self.b["flows"].append({"id": "x", "process": "curl", "remote": "198.51.100.7:443", "total_bps": 1})
        self.b["dns"]["servers"] = ["9.9.9.9"]
        self.b["health"]["score"] = self.a["health"]["score"] - 30
        self.b["findings"].append({"kind": "lan", "title": "New device on the local network", "severity": "info", "detail": "x"})
        d = diff_snapshots(self.a, self.b)
        self.assertIn({"app": "curl", "remote": "198.51.100.7"}, d["flows_added"])
        self.assertEqual(d["health"]["delta"], -30)
        self.assertEqual(d["dns"]["added"], ["9.9.9.9"])
        self.assertEqual([f["title"] for f in d["findings_new"]], ["New device on the local network"])

    def test_incident_narrative_orders_steps(self):
        self.b["health"]["score"] -= 10
        events = [{"ts": "2026-10-15T00:10:00+00:00", "kind": "dns", "title": "DNS resolver changed", "detail": "a → b"},
                  {"ts": "2026-10-15T00:05:00+00:00", "kind": "vpn", "title": "VPN state changed", "detail": ""}]
        n = narrate_incident(self.a, self.b, events, "2026-10-15T00:00:00+00:00", "2026-10-15T00:30:00+00:00")
        self.assertIn("-10", n["headline"])
        self.assertEqual([s["kind"] for s in n["steps"]][:2], ["vpn", "dns"])


class HistoryTimeTests(unittest.TestCase):
    def test_snapshot_at_and_events_between(self):
        with tempfile.TemporaryDirectory() as d:
            h = HistoryStore(os.path.join(d, "h.sqlite"))
            for ts in ("2026-10-15T00:00:00+00:00", "2026-10-15T00:10:00+00:00"):
                h.add_snapshot({"timestamp": ts, "n": ts})
            h.add_events([{"ts": "2026-10-15T00:05:00+00:00", "kind": "x", "title": "t"}])
            self.assertEqual(h.snapshot_at("2026-10-15T00:07:00+00:00")["timestamp"], "2026-10-15T00:00:00+00:00")
            self.assertEqual(h.snapshot_at("2026-10-14T00:00:00+00:00")["timestamp"], "2026-10-15T00:00:00+00:00")
            self.assertEqual(len(h.events_between("2026-10-15T00:00:00+00:00", "2026-10-15T00:10:00+00:00")), 1)
            self.assertEqual(h.events_between("2026-10-15T01:00:00+00:00", "2026-10-15T02:00:00+00:00"), [])


class PathCheckTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_target("Example.COM.", None), ("example.com", 443))
        self.assertEqual(validate_target("::1", "8080"), ("::1", 8080))
        for bad in ("", "http://x", "a b", "x/y", "-bad.com", "a" * 300):
            with self.assertRaises(ValueError, msg=bad):
                validate_target(bad, 443)
        for port in (0, 70000, "x"):
            with self.assertRaises(ValueError):
                validate_target("localhost", port)

    def test_tcp_ok_and_refused(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        threading.Thread(target=lambda: srv.accept()[0].close(), daemon=True).start()
        ok = check_target("127.0.0.1", port, timeout=2, tls=False)
        self.assertTrue(ok["ok"])
        self.assertEqual([s["stage"] for s in ok["stages"]], ["dns", "tcp"])
        srv.close()
        bad = check_target("127.0.0.1", port, timeout=2, tls=False)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["stages"][-1]["stage"], "tcp")

    def test_tls_to_ip_target_reports_failure_instead_of_raising(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        threading.Thread(target=lambda: srv.accept()[0].close(), daemon=True).start()
        res = check_target("127.0.0.1", srv.getsockname()[1], timeout=2, tls=True)
        srv.close()
        self.assertFalse(res["ok"])
        self.assertEqual([s["stage"] for s in res["stages"]], ["dns", "tcp", "tls"])
        self.assertFalse(res["stages"][-1]["ok"])

    def test_dns_timeout_is_enforced(self):
        import time
        from unittest import mock
        with mock.patch("pathcheck.socket.getaddrinfo", lambda *a, **k: time.sleep(1.5)):
            t0 = time.monotonic()
            res = check_target("slow.example", 80, timeout=0.2, tls=False)
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertEqual(res["stages"][0]["error"], "timed out")


class McpTests(unittest.TestCase):
    def test_protocol(self):
        init = nivora_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "nivora")
        tools = nivora_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertTrue({"summary", "explain_flow", "diff", "incident", "path_check"} <= names)
        self.assertFalse(any("rule_add" in n or "block" in n for n in names))
        self.assertIsNone(nivora_mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIn("error", nivora_mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"}))
        self.assertIn("error", nivora_mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}}))

    def test_unreachable_api_is_a_tool_error_not_a_crash(self):
        old = nivora_mcp.URL
        nivora_mcp.URL = "http://127.0.0.1:1"
        try:
            r = nivora_mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "summary", "arguments": {}}})
        finally:
            nivora_mcp.URL = old
        self.assertTrue(r["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
