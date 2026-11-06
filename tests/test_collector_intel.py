# SPDX-License-Identifier: BUSL-1.1
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

import privacy
from geo import GeoTable
from nivora_core import HistoryStore, endpoint_host, endpoint_port
from notify import Notifier, validate_webhook


def finding(title="X", sev="warning", **kw):
    return {"severity": sev, "kind": "k", "title": title, "detail": "d", **kw}


class NotifyTests(unittest.TestCase):
    def make(self, **kw):
        t = [1000.0]
        posts, logs = [], []
        n = Notifier(webhook=kw.pop("webhook", "http://127.0.0.1:9/h"), syslog=kw.pop("syslog", True),
                     clock=lambda: t[0], post=lambda u, b: posts.append(b), log=lambda s, m: logs.append((s, m)), **kw)
        return n, t, posts, logs

    def test_disabled_by_default(self):
        self.assertFalse(Notifier().enabled)
        self.assertEqual(Notifier().consider([finding()]), 0)

    def test_threshold_dedupe_cooldown_and_recurrence(self):
        n, t, _posts, logs = self.make(cooldown=100)
        f = [finding("A"), finding("B", sev="info")]
        self.assertEqual(n.consider(f), 1)          # info is below the default threshold
        self.assertEqual(n.consider(f), 0)          # same finding within cooldown
        t[0] += 101
        self.assertEqual(n.consider(f), 1)          # cooldown elapsed
        self.assertEqual(n.consider([]), 0)         # finding went away...
        self.assertEqual(n.consider(f), 1)          # ...so a recurrence alerts at once
        self.assertEqual(len(logs), 3)

    def test_payload_has_only_the_finding(self):
        n, _t, posts, _l = self.make(syslog=False)
        # webhook posts run on a thread; call the filter directly to keep the test deterministic
        due = n.due([finding("A", app="Safari", extra_secret="x")])
        self.assertEqual(len(due), 1)
        n._safe_post(b"{}")
        self.assertEqual(posts, [b"{}"])

    def test_validation(self):
        for bad in ("ftp://x", "not a url", ""):
            with self.assertRaises(ValueError):
                validate_webhook(bad)
        with self.assertRaises(ValueError):
            Notifier(min_severity="loud")
        self.assertEqual(validate_webhook("https://h/x"), "https://h/x")


class RetentionTests(unittest.TestCase):
    def test_event_cap_and_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            h = HistoryStore(os.path.join(td, "h.sqlite"), {"events": 3})
            self.assertEqual(h.retention["snapshot_days"], 30)
            h.add_events([{"ts": f"2026-01-01T00:00:0{i}Z", "kind": "x"} for i in range(6)])
            import sqlite3
            self.assertEqual(sqlite3.connect(h.path).execute("SELECT COUNT(*) FROM events").fetchone()[0], 3)
            self.assertEqual(HistoryStore(os.path.join(td, "d.sqlite")).retention["events"], 5000)


class TrackerFileTests(unittest.TestCase):
    def tearDown(self):
        privacy.EXTRA.clear()

    def test_extra_trackers(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "trackers.txt")
            Path(p).write_text("# mine\nads.example.com advertising\nplain.example.org  # comment\n")
            self.assertEqual(privacy.load_extra_trackers(p), 2)
            self.assertEqual(privacy.tracker_category("x.ads.example.com"), "advertising")
            self.assertEqual(privacy.tracker_category("plain.example.org"), "custom")
            self.assertEqual(privacy.tracker_category("doubleclick.net"), "advertising")
            self.assertEqual(privacy.load_extra_trackers(os.path.join(td, "missing")), 0)
            self.assertEqual(privacy.tracker_category("ads.example.com"), "")


class GeoTests(unittest.TestCase):
    def test_longest_prefix_and_annotation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "geo.csv"
            p.write_text("cidr,country,asn,org\n17.0.0.0/8,us,AS714,Apple\n17.253.0.0/16,DE,AS714,Apple EU\nbad,x\n2606:4700::/32,US,AS13335,Cloudflare\n")
            g = GeoTable.load(str(p))
            self.assertEqual(g.lookup("17.253.1.1")["country"], "DE")
            self.assertEqual(g.lookup("17.1.1.1")["country"], "US")
            self.assertEqual(g.lookup("2606:4700::1")["asn"], "AS13335")
            self.assertEqual(g.lookup("8.8.8.8"), {})
            flows = [{"remote": "17.1.1.1:443"}, {"remote": "192.168.1.5:22"}, {"remote": "[2606:4700::1]:443"}]
            g.annotate(flows)
            self.assertEqual(flows[0]["geo"]["org"], "Apple")
            self.assertNotIn("geo", flows[1])
            self.assertEqual(flows[2]["geo"]["org"], "Cloudflare")
            self.assertEqual(GeoTable.load(str(Path(td) / "none.csv")).rows, [])


class IPv6EndpointTests(unittest.TestCase):
    def test_bracketed_ipv6(self):
        self.assertEqual((endpoint_host("[2606:4700::1111]:443"), endpoint_port("[2606:4700::1111]:443")), ("2606:4700::1111", 443))
        self.assertEqual((endpoint_host("[::1]:8080"), endpoint_port("[::1]:8080")), ("::1", 8080))
        self.assertEqual((endpoint_host("1.2.3.4:53"), endpoint_port("1.2.3.4:53")), ("1.2.3.4", 53))
        self.assertEqual(endpoint_port("fe80::1"), 0)  # bare IPv6 with no port stays portless, never mis-split


if __name__ == "__main__":
    unittest.main()
