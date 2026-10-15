# SPDX-License-Identifier: BUSL-1.1
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from lan import diff_lan, dns_vpn_leak
from metrics import render_metrics
from nivora_core import HistoryStore, demo_snapshot
from projects import attribute_projects, parse_lsof_cwd, project_root, summarize_projects
from usage import budget_findings, budget_status, load_budgets


def snap(neigh, ssid="Home", gw="192.168.1.1"):
    return {"neighbors": [{"ip": ip, "mac": mac, "interface": "en0", "state": "reachable"} for ip, mac in neigh],
            "routes": [{"default": True, "gateway": gw, "family": "ipv4", "interface": "en0"}], "wifi": {"ssid": ssid}}


class LanTests(unittest.TestCase):
    def test_gateway_mac_change_is_critical(self):
        f = diff_lan(snap([("192.168.1.1", "aa:aa:aa:aa:aa:01")]), snap([("192.168.1.1", "aa:aa:aa:aa:aa:02")]))
        self.assertEqual([(x["title"], x["severity"]) for x in f], [("Gateway MAC address changed", "critical")])

    def test_non_gateway_mac_change_and_ssid(self):
        f = diff_lan(snap([("192.168.1.9", "AA:aa:aa:aa:aa:09")], "Cafe"), snap([("192.168.1.9", "aa:aa:aa:aa:aa:10")], "Home"))
        self.assertEqual({x["title"] for x in f}, {"MAC address changed for 192.168.1.9", "Wi-Fi network changed"})

    def test_no_change_and_no_previous(self):
        s = snap([("192.168.1.9", "aa:aa:aa:aa:aa:09")])
        self.assertEqual(diff_lan(s, s), [])
        self.assertEqual(diff_lan(s, None), [])

    def test_dns_vpn_leak(self):
        base = {"vpn": [{"active": True}], "dns": {"resolvers": [{"nameservers": ["192.168.1.1"], "interface": "en0"}]}}
        self.assertEqual(len(dns_vpn_leak(base)), 1)
        base["dns"]["resolvers"].append({"nameservers": ["10.0.0.1"], "interface": "utun4"})
        self.assertEqual(dns_vpn_leak(base), [])
        self.assertEqual(dns_vpn_leak({"vpn": [], "dns": base["dns"]}), [])


class PersistenceTests(unittest.TestCase):
    def test_new_device_after_baseline_only(self):
        with tempfile.TemporaryDirectory() as d:
            h = HistoryStore(os.path.join(d, "h.sqlite"))
            s = {"timestamp": "2026-10-15T00:00:00+00:00", "neighbors": [{"ip": "192.168.1.2", "mac": "aa:bb:cc:dd:ee:01", "interface": "en0"}]}
            self.assertEqual(h.observe_devices(s), [])
            s["neighbors"].append({"ip": "192.168.1.3", "mac": "aa:bb:cc:dd:ee:02", "interface": "en0"})
            s["neighbors"].append({"ip": "224.0.0.251", "mac": "01:00:5e:00:00:fb", "interface": "en0"})
            f = h.observe_devices(s)
            self.assertEqual([x["title"] for x in f], ["New device on the local network"])
            self.assertEqual(h.observe_devices(s), [])

    def test_usage_accumulates_and_budgets(self):
        with tempfile.TemporaryDirectory() as d:
            h = HistoryStore(os.path.join(d, "h.sqlite"))
            s = {"timestamp": "2026-10-15T00:00:00+00:00", "apps": [{"name": "Chrome", "rx_bps": 1000, "tx_bps": 500}]}
            h.observe_usage(s, 10)
            totals = h.observe_usage(s, 10)
            self.assertEqual(totals, {"Chrome": 30000})
            st = budget_status(totals, {"chrome": 20000, "slack": 10})
            self.assertTrue(st[0]["exceeded"] and st[0]["match"] == "chrome")
            self.assertEqual([f["title"] for f in budget_findings(st)], ["Daily budget exceeded: chrome"])
            p = Path(d) / "b.json"
            p.write_text(json.dumps({"a": 5, "b": "x", "c": -1, "d": True}))
            self.assertEqual(load_budgets(str(p)), {"a": 5})
            self.assertEqual(load_budgets(str(Path(d) / "missing.json")), {})


class ProjectTests(unittest.TestCase):
    def test_parse_and_attribute(self):
        self.assertEqual(parse_lsof_cwd("p10\nn/Users/u/code/app/src\np11\nn/\n"), {10: "/Users/u/code/app/src", 11: "/"})
        with tempfile.TemporaryDirectory() as home:
            home = os.path.realpath(home)
            proj = os.path.join(home, "code", "app")
            os.makedirs(os.path.join(proj, "src"))
            os.makedirs(os.path.join(proj, ".git"))
            self.assertEqual(project_root(os.path.join(proj, "src"), home), proj)
            self.assertEqual(project_root(home, home), "")
            self.assertEqual(project_root("/usr/bin", home), "")
            flows = [{"pid": 10, "process": "node", "total_bps": 5.0}, {"pid": 99, "process": "x"}]
            attribute_projects(flows, {10: os.path.join(proj, "src")}, home)
            self.assertEqual(flows[0]["project"], proj)
            self.assertNotIn("project", flows[1])
            self.assertEqual(summarize_projects(flows)[0]["name"], "app")


class MetricsTests(unittest.TestCase):
    def test_render(self):
        s = demo_snapshot()
        s["port_conflicts"] = []
        out = render_metrics(s)
        self.assertIn("# TYPE nivora_health_score gauge", out)
        self.assertIn('nivora_traffic_bytes_per_second{direction="rx"}', out)
        self.assertTrue(out.endswith("\n"))
        s["apps"] = [{"name": 'Evil"\nApp\\', "rx_bps": 1, "tx_bps": 1}]
        out = render_metrics(s)
        self.assertNotIn('Evil"\n', out)
        self.assertIn('app="Evil\\"App\\\\"', out)


if __name__ == "__main__":
    unittest.main()
