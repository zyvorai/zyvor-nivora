# SPDX-License-Identifier: BUSL-1.1
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from egress import egress_report
from fleet import FleetStore, summarize
from identity import IdentityResolver, identity_findings, parse_codesign, parse_ps
from nivora_core import RuleStore, classify_remote, demo_snapshot, endpoint_host
from policy import apply_policy, export_policy, plan_policy, validate_policy
from privacy import privacy_report, tracker_category
from profiles import PROFILES, ProfileStore
from trust import trust_scores

APPLE = "Identifier=com.apple.curl\nAuthority=Software Signing\nAuthority=Apple Code Signing Certification Authority\nTeamIdentifier=not set\n"
DEV = "Identifier=com.example.app\nAuthority=Developer ID Application: Example (ABCDE12345)\nTeamIdentifier=ABCDE12345\n"
ADHOC = "Identifier=a\nSignature=adhoc\nTeamIdentifier=not set\n"


class IdentityTests(unittest.TestCase):
    def test_parse_codesign(self):
        self.assertTrue(parse_codesign(APPLE)["apple"])
        d = parse_codesign(DEV)
        self.assertEqual((d["signed"], d["team_id"], d["apple"]), (True, "ABCDE12345", False))
        self.assertTrue(parse_codesign(ADHOC)["adhoc"])
        self.assertFalse(parse_codesign("code object is not signed at all")["signed"])
        self.assertTrue(parse_codesign("", 1)["unknown"])

    def test_parse_ps_and_resolver_budget_and_cache(self):
        self.assertEqual(parse_ps("  1 /sbin/launchd\n 42 /Applications/My App.app/Contents/MacOS/My App\n"), {1: "/sbin/launchd", 42: "/Applications/My App.app/Contents/MacOS/My App"})
        calls = []
        r = IdentityResolver(lambda p: (calls.append(p) or DEV, 0), budget=1)
        flows = [{"pid": 1, "remote": "1.1.1.1:443"}, {"pid": 1}, {"pid": 2}]
        r.annotate(flows, "1 /a\n2 /b\n")
        self.assertEqual(calls, ["/a"])
        self.assertIn("identity", flows[1])
        self.assertNotIn("identity", flows[2])

    def test_findings_only_for_unsigned_internet(self):
        flows = [{"process": "bad", "path": "/tmp/bad", "remote": "8.8.8.8:443", "identity": {"signed": False}},
                 {"process": "dev", "path": "/tmp/dev", "remote": "8.8.8.8:443", "identity": {"signed": True, "adhoc": True}},
                 {"process": "lan", "path": "/tmp/lan", "remote": "192.168.1.5:80", "identity": {"signed": False}},
                 {"process": "ok", "path": "/x", "remote": "8.8.8.8:443", "identity": {"signed": True, "adhoc": False}}]
        f = identity_findings(flows, lambda r: classify_remote(endpoint_host(r)) == "internet")
        self.assertEqual({(x["app"], x["severity"]) for x in f}, {("bad", "warning"), ("dev", "info")})


class TrustPrivacyTests(unittest.TestCase):
    def test_trust_components_and_ordering(self):
        s = {"flows": [{"process": "Good", "remote": "github.com:443", "identity": {"signed": True, "team_id": "T", "adhoc": False}},
                       {"process": "Bad", "remote": "www.google-analytics.com:80", "bundle_id": "x.bad", "identity": {"signed": False}}],
             "behavior": {"new_destinations": [{"app": "Bad", "remote": "x"}]},
             "listeners": [{"process": "Bad", "exposure": "all", "port": 9000}]}
        t = trust_scores(s)
        self.assertEqual([x["app"] for x in t], ["Bad", "Good"])
        self.assertEqual(t[1]["score"], 100)
        self.assertEqual(t[0]["level"], "low")
        self.assertEqual(sum(c["max"] for c in t[0]["components"]), 100)

    def test_privacy_report(self):
        s = {"flows": [{"process": "A", "remote": "ssl.google-analytics.com:443"}, {"process": "B", "remote": "example.org:80"},
                       {"process": "C", "remote": "127.0.0.1:80"}],
             "findings": [{"title": "DNS may bypass the VPN"}, {"kind": "identity", "app": "B"}], "vpn": [{"active": True}]}
        r = privacy_report(s)
        self.assertEqual(len(r["trackers"]), 1)
        self.assertEqual([c["app"] for c in r["cleartext"]], ["B"])
        self.assertTrue(r["dns_vpn_leak"])
        self.assertEqual(r["unsigned_apps"], ["B"])
        self.assertEqual(r["score"], 100 - 8 - 10 - 15 - 5)
        self.assertEqual(tracker_category("notgoogle-analytics.com"), "")
        ip_only = privacy_report({"flows": [{"process": "A", "remote": "1.2.3.4:443"}]})
        self.assertTrue(ip_only["notes"])


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.store = RuleStore(os.path.join(self.d.name, "r.json"))

    def tearDown(self):
        self.d.cleanup()

    def test_validate(self):
        for bad in ({}, {"name": "x y", "rules": []}, {"name": "ok", "rules": "no"}, {"name": "ok", "rules": [{"action": "block"}]},
                    {"name": "ok", "rules": [{"domain": "a.com"}, {"domain": "a.com"}]}):
            with self.assertRaises(ValueError):
                validate_policy(bad)

    def test_plan_apply_idempotent_and_leased(self):
        pol = {"name": "work", "rules": [{"action": "shadow", "domain": "a.com"}, {"action": "block", "domain": "b.com"}]}
        plan = plan_policy(self.store, pol)
        self.assertEqual((len(plan["add"]), len(plan["remove"])), (2, 0))
        self.assertEqual(self.store.list(), [])  # planning does not write
        res = apply_policy(self.store, pol)
        self.assertEqual(len(res["added"]), 2)
        block = next(r for r in self.store.list() if r["action"] == "block")
        self.assertIn("expires_at", block)  # leased like a hand-added block
        again = plan_policy(self.store, pol)
        self.assertEqual((len(again["add"]), len(again["remove"]), len(again["unchanged"])), (0, 0, 2))
        shrunk = apply_policy(self.store, {"name": "work", "rules": [{"action": "shadow", "domain": "a.com"}]})
        self.assertEqual(len(shrunk["removed"]), 1)
        self.assertEqual(len(self.store.list()), 1)

    def test_other_policies_and_manual_rules_untouched(self):
        self.store.add({"action": "observe", "domain": "manual.com"})
        apply_policy(self.store, {"name": "p1", "rules": [{"action": "observe", "domain": "x.com"}]})
        apply_policy(self.store, {"name": "p2", "rules": []})
        self.assertEqual(len(self.store.list()), 2)
        self.assertEqual(len(export_policy(self.store, "e")["rules"]), 2)

    def test_permanent_block_requires_explicit_flag(self):
        apply_policy(self.store, {"name": "p", "rules": [{"action": "block", "ip": "203.0.113.9", "permanent": True}]})
        self.assertNotIn("expires_at", self.store.list()[0])


class ProfileFleetEgressTests(unittest.TestCase):
    def test_profiles(self):
        with tempfile.TemporaryDirectory() as d:
            ps = ProfileStore(os.path.join(d, "p.json"))
            self.assertEqual(ps.active(), "default")
            ps.set("travel")
            self.assertEqual(ProfileStore(os.path.join(d, "p.json")).settings()["budget_scale"], 0.5)
            with self.assertRaises(ValueError):
                ps.set("nope")
            Path(d, "p.json").write_text("garbage")
            self.assertEqual(ps.active(), "default")
        self.assertTrue(all("high_bandwidth_bps" in p for p in PROFILES.values()))

    def test_fleet(self):
        now = [1000.0]
        f = FleetStore(clock=lambda: now[0])
        f.accept(summarize(demo_snapshot()))
        with self.assertRaises(ValueError):
            f.accept({"nohost": 1})
        with self.assertRaises(ValueError):
            f.accept({"host": "x", "blob": "y" * 30000})
        now[0] += 500
        row = f.listing()[0]
        self.assertTrue(row["stale"])
        self.assertEqual(row["host"], demo_snapshot()["host"]["name"])

    def test_egress(self):
        s = demo_snapshot()
        r = egress_report(s)
        self.assertTrue(r["connected"])
        w = next(x for x in r["workloads"] if x["id"] == "macos-build-07")
        self.assertEqual(w["destinations"][0]["host"], "github.com")
        s2 = copy.deepcopy(s)
        s2["fluxvm"]["connected"] = False
        self.assertFalse(egress_report(s2)["connected"])
        self.assertEqual(json.loads(json.dumps(r)), r)


class OrphanTests(unittest.TestCase):
    def test_collector_exits_when_launcher_dies(self):
        import subprocess, time
        agent = Path(__file__).resolve().parents[1] / "agent" / "nivora.py"
        with tempfile.TemporaryDirectory() as d:
            cmd = (f"{sys.executable} -B {agent} --demo --port 0 --interval 0.3 --quiet --parent-pid $$ "
                   f"--token t --database {d}/h.sqlite --rules {d}/r.json >{d}/collector.log 2>&1 & echo $!")
            out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=10).stdout.strip()
            pid = int(out)
            deadline = time.time() + 10
            alive = True
            while time.time() < deadline and alive:
                time.sleep(0.3)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    alive = False
            ps = ""
            if alive:  # state (zombie? reparented?) is the first thing to know when this fails
                ps = subprocess.run(["ps", "-o", "pid,ppid,stat,etime,command", "-p", str(pid)],
                                    capture_output=True, text=True).stdout
                os.kill(pid, 15)
            log = Path(d, "collector.log")
            self.assertFalse(alive, "collector kept running after its launcher exited; ps:\n" + ps + "output:\n"
                             + (log.read_text(errors="replace")[-2000:] if log.exists() else "(no log)"))


if __name__ == "__main__":
    unittest.main()
