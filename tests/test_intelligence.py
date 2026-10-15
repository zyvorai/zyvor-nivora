# SPDX-License-Identifier: BUSL-1.1
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from anomalies import detect_anomalies, merge_findings
from containers import detect_runtime, enrich_flows_with_containers, summarize_containers
from dns_diag import diagnose_resolvers
from ports import annotate_listeners, find_conflicts


class IntelligenceTests(unittest.TestCase):
    def test_runtime_detection_no_false_positives(self):
        self.assertEqual(detect_runtime("com.docker.backend"), "docker")
        self.assertEqual(detect_runtime("OrbStack Helper"), "orbstack")
        self.assertEqual(detect_runtime("colima"), "colima")
        for name in ("Calibre", "climate", "Google Chrome", "Slack"):
            self.assertEqual(detect_runtime(name), "", name)

    def test_container_summary(self):
        flows = [
            {"process": "com.docker.backend", "pid": 1, "bytes_in": 10, "bytes_out": 5},
            {"process": "Slack", "pid": 2, "bytes_in": 99, "bytes_out": 99},
        ]
        enrich_flows_with_containers(flows)
        s = summarize_containers(flows)
        self.assertEqual(len(s), 1)
        self.assertEqual((s[0]["runtime"], s[0]["flows"], s[0]["bytes_in"]), ("docker", 1, 10))

    def test_port_conflicts(self):
        ls = [
            {"process": "node", "pid": 1, "protocol": "tcp", "port": 8080, "address": "*"},
            {"process": "python", "pid": 2, "protocol": "tcp", "port": 8080, "address": "127.0.0.1"},
            {"process": "dns", "pid": 3, "protocol": "tcp", "port": 53, "address": "*"},
            {"process": "dns", "pid": 3, "protocol": "udp", "port": 53, "address": "*"},
            {"process": "sshd", "pid": 4, "protocol": "tcp", "port": 22, "address": "*"},
            {"process": "sshd", "pid": 4, "protocol": "tcp", "port": 22, "address": "::"},
        ]
        c = find_conflicts(ls)
        self.assertEqual([(x["port"], x["severity"]) for x in c], [(8080, "warning")])
        annotate_listeners(ls)
        self.assertTrue(ls[0]["conflict"])
        self.assertFalse(ls[2]["conflict"])

    def test_shared_multicast_udp_ports_not_conflicts(self):
        ls = [{"process": "Google", "pid": 1, "protocol": "udp", "port": 5353, "address": "*"},
              {"process": "node", "pid": 2, "protocol": "udp", "port": 5353, "address": "*"},
              {"process": "a", "pid": 3, "protocol": "tcp", "port": 5353, "address": "*"},
              {"process": "b", "pid": 4, "protocol": "tcp", "port": 5353, "address": "*"}]
        c = find_conflicts(ls)
        self.assertEqual([(x["protocol"], x["port"]) for x in c], [("tcp", 5353)])
        annotate_listeners(ls)
        self.assertEqual([l["conflict"] for l in ls], [False, False, True, True])

    def test_anomalies_and_merge(self):
        snap = {"flows": [{"process": "rsync", "total_bps": 6 * 1048576, "interface": "en0"},
                          {"process": "x", "total_bps": 1, "interface": "utun4"}],
                "interfaces": [{"name": "utun4"}], "vpn": [{"active": True}]}
        f = detect_anomalies(snap)
        self.assertEqual({x["title"] for x in f}, {"High bandwidth application", "Mixed VPN and direct traffic"})
        self.assertEqual(len(merge_findings(list(f), f)), 2)
        self.assertEqual(detect_anomalies({"flows": []}), [])

    def test_dns(self):
        d = diagnose_resolvers({"servers": ["1.1.1.1", "192.168.1.1"], "resolvers": [{}]})
        self.assertTrue(d["public"])
        self.assertEqual(len(d["notes"]), 2)
        self.assertIn("No nameservers configured", diagnose_resolvers({})["notes"])


if __name__ == "__main__":
    unittest.main()
