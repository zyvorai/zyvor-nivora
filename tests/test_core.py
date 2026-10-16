# SPDX-License-Identifier: BUSL-1.1
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from nivora_core import (
    FluxVMProbe, HistoryStore, RuleStore, aggregate_apps, annotate_rates, answer_query, apply_rule_preview,
    build_topology, compute_health, demo_snapshot, derive_listeners, diagnose_network,
    parse_arp, parse_extension_events, parse_ifconfig, parse_lsof, parse_ndp,
    parse_netstat_routes, parse_nettop, parse_networksetup_hardware_ports, parse_scutil_dns,
    enrich_interface_hardware, timeline_events,
)

FIX = ROOT / "tests" / "fixtures"

class ParserTests(unittest.TestCase):
    def test_lsof(self):
        rows = parse_lsof((FIX / "lsof.txt").read_text())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["process"], "Slack")
        self.assertEqual(rows[1]["remote"], "13.107.6.175:443")
        self.assertEqual(rows[1]["state"], "ESTABLISHED")

    def test_nettop(self):
        rows = parse_nettop((FIX / "nettop.csv").read_text())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["pid"], 602)
        self.assertEqual(rows[0]["bytes_in"], 98566144)
        self.assertEqual(rows[0]["interface"], "utun4")

    def test_routes_dns_interfaces(self):
        routes = parse_netstat_routes((FIX / "routes.txt").read_text(), "ipv4")
        self.assertTrue(routes[0]["default"])
        self.assertEqual(routes[0]["interface"], "en0")
        dns = parse_scutil_dns((FIX / "dns.txt").read_text())
        self.assertIn("1.1.1.1", dns["servers"])
        self.assertEqual(dns["resolvers"][1]["interface"], "utun4")
        ints = parse_ifconfig((FIX / "ifconfig.txt").read_text())
        self.assertEqual([x["name"] for x in ints], ["lo0", "en0", "utun4"])
        self.assertEqual(ints[2]["kind"], "vpn")


    def test_local_network_parsers(self):
        arp = parse_arp((FIX / "arp.txt").read_text())
        ndp = parse_ndp((FIX / "ndp.txt").read_text())
        self.assertEqual(arp[0]["ip"], "192.168.1.1")
        self.assertEqual(ndp[0]["interface"], "en0")
        ports = parse_networksetup_hardware_ports((FIX / "hardwareports.txt").read_text())
        ints = parse_ifconfig((FIX / "ifconfig.txt").read_text())
        enrich_interface_hardware(ints, ports)
        self.assertEqual(next(x for x in ints if x["name"] == "en0")["kind"], "wifi")

    def test_listener_derivation(self):
        rows = parse_lsof((FIX / "lsof.txt").read_text())
        listeners = derive_listeners(rows)
        self.assertEqual(listeners[0]["port"], 5353)

    def test_extension_events_latest_wins(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "flows.jsonl"
            p.write_text("\n".join([
                json.dumps({"flow_id":"x","bundle_id":"com.test.App","remote":"1.1.1.1:443","bytes_in":1,"bytes_out":2}),
                json.dumps({"flow_id":"x","bundle_id":"com.test.App","remote":"1.1.1.1:443","bytes_in":10,"bytes_out":20}),
            ]))
            rows = parse_extension_events(str(p))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["bytes_out"], 20)
            self.assertEqual(rows[0]["source"], "networkextension")

class ModelTests(unittest.TestCase):
    def test_demo_aggregates(self):
        s = demo_snapshot()
        self.assertGreaterEqual(len(s["apps"]), 4)
        self.assertTrue(any(a["name"] == "Slack" for a in s["apps"]))
        self.assertTrue(s["fluxvm"]["connected"])

    def test_query(self):
        s = demo_snapshot()
        result = answer_query(s, "which app uploaded the most?")
        self.assertIn("largest outbound sender", result["answer"])
        result = answer_query(s, "is my VPN active?")
        self.assertIn("VPN active", result["answer"])
        result = answer_query(s, "what uses port 443?")
        self.assertIn("flow(s)", result["answer"])

    def test_rules(self):
        s = demo_snapshot()
        with tempfile.TemporaryDirectory() as td:
            store = RuleStore(str(Path(td) / "rules.json"))
            rule = store.add({"domain":"github.com","action":"block"})
            self.assertIn("expires_at", rule)
            hits = apply_rule_preview(s["flows"], store.list())
            self.assertTrue(any(h["rule_id"] == rule["id"] for h in hits))
            self.assertTrue(store.remove(rule["id"]))

    def test_timeline_detects_route_change(self):
        a = demo_snapshot(); b = demo_snapshot()
        b["routes"][0]["gateway"] = "192.168.1.254"
        events = timeline_events(b, a)
        self.assertTrue(any(e["kind"] == "route" for e in events))


    def test_rates_health_topology_and_diagnosis(self):
        a = demo_snapshot(); b = demo_snapshot()
        a["timestamp"] = "2026-10-13T00:00:00+00:00"; b["timestamp"] = "2026-10-13T00:00:02+00:00"
        b["flows"][0]["bytes_in"] = a["flows"][0]["bytes_in"] + 2000
        annotate_rates(b["flows"], a, b["timestamp"])
        self.assertEqual(b["flows"][0]["rx_bps"], 1000.0)
        b["apps"] = aggregate_apps(b["flows"]); b["health"] = compute_health(b); b["topology"] = build_topology(b)
        self.assertGreaterEqual(b["health"]["score"], 1)
        self.assertTrue(b["topology"]["nodes"])
        self.assertIn("summary", diagnose_network(b))

    def test_behavior_baseline_persists(self):
        with tempfile.TemporaryDirectory() as td:
            h = HistoryStore(str(Path(td) / "history.sqlite"))
            s = demo_snapshot(); first = h.observe_behavior(s)
            self.assertEqual(first["new_destinations"], [])
            s2 = demo_snapshot(); s2["flows"].append({"id":"new","process":"Slack","pid":602,"bundle_id":"com.tinyspeck.slackmacgap","protocol":"tcp","local":"","remote":"new.example:443","bytes_in":0,"bytes_out":0})
            second = h.observe_behavior(s2)
            self.assertTrue(any(x["remote"] == "new.example" for x in second["new_destinations"]))


    def test_fluxvm_envelope_and_status_are_normalised(self):
        """FluxVM answers with {"items": [...]} and `status`; the snapshot must carry plain lists with `state`
        (a dict here once made the native app report "Collector unavailable" on every Mac running FluxVM)."""
        from nivora_core import fluxvm_workloads
        class Probe(FluxVMProbe):
            def _get(self, path):
                return {
                    "/healthz": {"ok": True},
                    "/v1/vms": {"items": [{"id": "vm-1", "name": "warm", "backend": "vz", "status": "stopped", "pid": None}]},
                    "/v1/sandboxes": {"items": [{"id": "sb-1", "state": "running"}]},
                }.get(path)
        data = Probe().collect()
        self.assertIsInstance(data["vms"], list)
        self.assertEqual(data["vms"][0]["id"], "vm-1")
        self.assertEqual(data["vms"][0]["state"], "stopped")
        self.assertEqual(data["sandboxes"], [{"id": "sb-1", "state": "running"}])
        # bare lists stay as they are, an existing `state` is never overwritten, garbage becomes an empty list
        self.assertEqual(fluxvm_workloads([{"id": "a", "state": "running", "status": "x"}]), [{"id": "a", "state": "running", "status": "x"}])
        for junk in (None, "oops", 7, {"items": "nope"}, {"other": []}, [1, "x", None]):
            self.assertEqual(fluxvm_workloads(junk), [], junk)

    def test_egress_workloads_accept_the_items_envelope(self):
        from egress import _workloads
        found = _workloads({"vms": {"items": [{"id": "vm-1", "state": "running", "backend": "vz"}]}, "sandboxes": []})
        self.assertEqual([w["id"] for w in found], ["vm-1"])
        self.assertEqual(found[0]["kind"], "vm")

    def test_fluxvm_probe_fast_absent_and_rich_present(self):
        class Probe(FluxVMProbe):
            def __init__(self, replies):
                super().__init__()
                self.replies = replies
                self.calls = []
            def _get(self, path):
                self.calls.append(path)
                return self.replies.get(path)

        absent = Probe({})
        data = absent.collect()
        self.assertFalse(data["connected"])
        self.assertEqual(absent.calls, ["/healthz"])

        present = Probe({
            "/healthz": {"ok": True},
            "/v1/vms": [{"id": "macos-ci"}],
            "/v1/network/health": {"ok": True},
            "/v1/network/endpoints": [{"id": 1}],
            "/v1/network/hubble/flows?limit=200": [{"src": "macos-ci"}],
        })
        data = present.collect()
        self.assertTrue(data["connected"])
        self.assertEqual(len(data["network_endpoints"]), 1)
        self.assertEqual(len(data["hubble_flows"]), 1)
        self.assertIn("/v1/network/observe", present.calls)

    def test_history(self):
        with tempfile.TemporaryDirectory() as td:
            h = HistoryStore(str(Path(td) / "history.sqlite"))
            s = demo_snapshot(); h.add_snapshot(s)
            h.add_events([{"ts":s["timestamp"],"kind":"test","title":"ok","detail":""}])
            self.assertEqual(len(h.history()), 1)
            self.assertEqual(h.events()[0]["kind"], "test")

if __name__ == "__main__": unittest.main()
