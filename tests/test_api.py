# SPDX-License-Identifier: BUSL-1.1
import argparse
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from nivora import Handler, State

class APITests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        args = argparse.Namespace(
            fluxvm_url="http://127.0.0.1:1", fluxvm_token="", demo=True,
            no_history=False, database=str(Path(self.td.name)/"history.sqlite"),
            rules=str(Path(self.td.name)/"rules.json"), interval=60.0,
            allow_origin=["http://example.test"], token="secret", quiet=True,
            web_root=str(ROOT/"web"), bind="127.0.0.1", port=0,
        )
        self.state = State(args); self.state.sample()
        self.server = ThreadingHTTPServer(("127.0.0.1",0), Handler); self.server.state=self.state
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.td.cleanup()

    def req(self,path,method="GET",body=None,token=True):
        headers={"Origin":"http://example.test"}
        if token: headers["Authorization"]="Bearer secret"
        data=None
        if body is not None:
            data=json.dumps(body).encode();headers["Content-Type"]="application/json"
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=data,headers=headers,method=method),timeout=2)

    def test_snapshot_and_cors(self):
        with self.req("/v1/snapshot") as r:
            data=json.loads(r.read()); self.assertEqual(data["host"]["os"],"macOS")
            self.assertEqual(r.headers.get("Access-Control-Allow-Origin"),"http://example.test")

    def test_flows_filter_param(self):
        with self.req("/v1/flows") as r: allf=json.loads(r.read())
        proto=allf[0]["protocol"]
        with self.req("/v1/flows?filter=proto%3A"+proto) as r: only=json.loads(r.read())
        self.assertTrue(only and all(f["protocol"]==proto for f in only))
        with self.req("/v1/flows?filter=app%3Anope-does-not-exist") as r: self.assertEqual(json.loads(r.read()),[])

    def test_export_formats_filter_and_redaction(self):
        import io, zipfile
        with self.req("/v1/export?kind=flows&format=csv") as r:
            self.assertIn("attachment", r.headers["Content-Disposition"])
            rows=r.read().decode().strip().split("\n")
        self.assertTrue(rows[0].startswith("process,protocol"))
        with self.req("/v1/export?kind=flows&format=ndjson&filter=app%3Anope-nothing") as r:
            self.assertEqual(r.read(),b"")
        with self.req("/v1/export?kind=snapshot&format=json&redact=1") as r:
            snap=json.loads(r.read())
        self.assertTrue(snap["host"]["name"].startswith("host-"))
        self.assertNotRegex(json.dumps(snap), r"\b192\.168\.\d+\.\d+\b")
        with self.req("/v1/export?kind=bundle&format=zip") as r:
            names=zipfile.ZipFile(io.BytesIO(r.read())).namelist()
        self.assertEqual(sorted(names),["README.txt","flows.csv","snapshot.json","timeline.ndjson"])
        with self.assertRaises(urllib.error.HTTPError) as c: self.req("/v1/export?kind=flows&format=xml")
        self.assertEqual(c.exception.code,400)

    def test_capture_demo_flow_and_guards(self):
        def post(path, body):
            return self.req(path, "POST", body)
        with self.req("/v1/captures") as r:
            info = json.loads(r.read())
        self.assertTrue(info["available"] and info["demo"])
        with self.assertRaises(urllib.error.HTTPError) as c:          # no explicit confirmation
            post("/v1/captures", {"iface": "en0"})
        self.assertEqual(c.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as c:          # injection attempt
            post("/v1/captures", {"iface": "en0; id", "confirm": True})
        self.assertEqual(c.exception.code, 400)
        with post("/v1/captures", {"iface": "en0", "host": "142.250.183.14", "proto": "tcp", "port": 443, "seconds": 5, "confirm": True}) as r:
            sess = json.loads(r.read())
        self.assertEqual(sess["snaplen"], 96)
        with self.req(f"/v1/captures/{sess['id']}/pcap") as r:
            self.assertEqual(r.headers["Content-Type"], "application/vnd.tcpdump.pcap")
            self.assertEqual(r.read()[:4], b"\xd4\xc3\xb2\xa1")
        with self.req(f"/v1/captures/{sess['id']}", "DELETE") as r:
            self.assertTrue(json.loads(r.read())["deleted"])
        with self.req("/v1/timeline") as r:
            kinds = [e["kind"] for e in json.loads(r.read())]
        self.assertIn("capture", kinds)

    def test_demo_mode_never_writes_history(self):
        self.assertIsNone(self.state.history)
        self.assertFalse((Path(self.td.name)/"history.sqlite").exists())
        with self.req("/v1/timeline") as r:
            titles=[e["title"] for e in json.loads(r.read())]
        self.assertIn("DNS resolver changed", titles)       # seeded simulated history, in memory only

    def test_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError) as c: self.req("/v1/snapshot",token=False)
        self.assertEqual(c.exception.code,401)

    def test_query_and_rules(self):
        with self.req("/v1/query","POST",{"question":"VPN?"}) as r:
            self.assertIn("VPN active",json.loads(r.read())["answer"])
        with self.req("/v1/rules","POST",{"domain":"github.com","action":"block"}) as r:
            rule=json.loads(r.read());self.assertEqual(r.status,201)
        with self.req("/v1/rules") as r: self.assertEqual(len(json.loads(r.read())),1)
        with self.req("/v1/rules/"+rule["id"],"DELETE") as r: self.assertTrue(json.loads(r.read())["deleted"])


    def test_intelligence_endpoints(self):
        for path in ["/v1/health","/v1/traffic","/v1/topology","/v1/neighbors","/v1/listeners","/v1/behavior","/v1/diagnose","/v1/series?limit=5"]:
            with self.req(path) as r:
                self.assertEqual(r.status, 200, path)
                json.loads(r.read())

    def test_bad_history_limit_does_not_crash(self):
        with self.req("/v1/series?limit=nope") as r:
            self.assertEqual(r.status, 200)

    def test_static_page_is_public(self):
        with urllib.request.urlopen(self.base+"/",timeout=2) as r:
            self.assertIn(b"Nivora",r.read())

    def test_same_origin_loopback_allowed_but_foreign_origin_rejected(self):
        host=self.base.split("//")[1]
        def get(path,origin):
            rq=urllib.request.Request(self.base+path,headers={"Origin":origin})
            return urllib.request.urlopen(rq,timeout=2)
        with get("/app.js","http://"+host) as r: self.assertEqual(r.status,200)
        with self.assertRaises(urllib.error.HTTPError) as c: get("/app.js","http://evil.test")
        self.assertEqual(c.exception.code,403)

    def test_unwritable_rules_dir_falls_back(self):
        import os
        from unittest import mock
        real = os.path.expanduser
        args = argparse.Namespace(**{**vars(self.state.args), "rules": "/dev/null/blocked/rules.json",
                                     "database": str(Path(self.td.name)/"h2.sqlite")})
        with mock.patch("nivora.os.path.expanduser", side_effect=lambda p: str(Path(self.td.name)/"fb.json") if p.startswith("~/.local") else real(p)):
            st = State(args)
        self.assertTrue(str(st.rules.path).endswith("fb.json"))

    def test_dashboard_modules_are_served(self):
        for name in ("app.js","lib.js"):
            with urllib.request.urlopen(self.base+"/"+name,timeout=2) as r:
                self.assertIn("javascript",r.headers.get("Content-Type",""))
                self.assertIn("script-src 'self'",r.headers.get("Content-Security-Policy",""))
                self.assertGreater(len(r.read()),100)

if __name__ == "__main__": unittest.main()
