# SPDX-License-Identifier: BUSL-1.1
import argparse
import contextlib
import importlib.util
import io
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

import nivora_mcp
import nivoractl
from nivora_core import VERSION


class Fake(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {"/v1/snapshot": {"version": "9.9.9", "host": "h", "capabilities": {}, "apps": [1], "flows": [1, 2], "findings": []},
                "/v1/apps": [{"name": "Safari", "connections": 3, "bytes_in": 1, "bytes_out": 2}],
                "/v1/trust": [{"app": "Safari", "score": 90}]}.get(self.path.split("?")[0], {"path": self.path})
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            nivoractl.main(["--url", self.url, "--token", "t", *argv])
        return buf.getvalue()

    def test_table_json_and_pretty(self):
        self.assertIn("APP", self.run_cli("apps").splitlines()[0])
        self.assertEqual(json.loads(self.run_cli("--json", "apps"))[0]["name"], "Safari")
        self.assertEqual(self.run_cli("--json", "trust").strip(), '[{"app":"Safari","score":90}]')
        self.assertIn('"flows": 2', self.run_cli("status"))
        self.assertIn("/v1/flows?filter=app%3ASafari", self.run_cli("--json", "flows", "--filter", "app:Safari"))

    def test_every_get_command_is_a_subcommand(self):
        subs = nivoractl.subcommands(nivoractl.build_parser())
        self.assertTrue(set(nivoractl.GET_COMMANDS) <= set(subs))
        for must in ("status", "apps", "flows", "ask", "rule-add", "version", "completion", "trust", "privacy"):
            self.assertIn(must, subs)

    def test_version(self):
        info = json.loads(self.run_cli("version"))
        self.assertEqual((info["cli"], info["collector"]), (VERSION, "9.9.9"))
        args = argparse.Namespace(url=self.url, token="", check=True)
        newer = nivoractl.version_info(args, fetch=lambda: "v99.0.0")
        self.assertTrue(newer["update_available"])
        same = nivoractl.version_info(args, fetch=lambda: "v" + VERSION)
        self.assertFalse(same["update_available"])

        def boom():
            raise OSError("offline")
        self.assertIn("check_error", nivoractl.version_info(args, fetch=boom))
        self.assertGreater(nivoractl.parse_version("0.10.0"), nivoractl.parse_version("0.9.9"))

    def test_version_without_check_never_calls_github(self):
        args = argparse.Namespace(url=self.url, token="", check=False)
        self.assertNotIn("latest", nivoractl.version_info(args, fetch=lambda: self.fail("network call")))

    def test_completion_scripts(self):
        parser = nivoractl.build_parser()
        bash = nivoractl.completion_script("bash", parser)
        self.assertIn("complete -F _nivoractl nivoractl", bash)
        self.assertIn("rule-add) COMPREPLY", bash)
        zsh = nivoractl.completion_script("zsh", parser)
        self.assertTrue(zsh.startswith("#compdef nivoractl"))
        self.assertIn("--filter", zsh)
        fish = nivoractl.completion_script("fish", parser)
        self.assertIn("__fish_seen_subcommand_from flows' -l filter", fish)
        self.assertIn("complete -c nivoractl", self.run_cli("completion", "fish"))

    def test_man_page(self):
        spec = importlib.util.spec_from_file_location("build_man", ROOT / "scripts" / "build-man.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        page = mod.render()
        self.assertTrue(page.startswith(".TH NIVORACTL 1"))
        for word in ("\\-\\-json", "rule\\-add", "NIVORA_TOKEN"):
            self.assertIn(word, page)


class McpTests(unittest.TestCase):
    def call(self, method, params=None):
        return nivora_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def test_server_version_and_capabilities(self):
        r = self.call("initialize")["result"]
        self.assertEqual(r["serverInfo"]["version"], VERSION)
        self.assertTrue({"tools", "resources", "prompts"} <= set(r["capabilities"]))

    def test_new_read_only_tools(self):
        names = {t["name"] for t in self.call("tools/list")["result"]["tools"]}
        self.assertTrue({"trust", "privacy", "egress", "usage", "listeners", "fluxvm", "profiles", "timeline"} <= names)
        self.assertFalse(any(w in n for n in names for w in ("add", "delete", "block", "apply", "set")))

    def test_resources_and_prompts(self):
        uris = {r["uri"] for r in self.call("resources/list")["result"]["resources"]}
        self.assertEqual(uris, {"nivora://snapshot", "nivora://findings"})
        self.assertIn("error", self.call("resources/read", {"uri": "nivora://nope"}))
        prompts = {p["name"] for p in self.call("prompts/list")["result"]["prompts"]}
        self.assertEqual(prompts, {"incident_review", "network_checkup"})
        got = self.call("prompts/get", {"name": "incident_review", "arguments": {"from": "2026-01-01T00:00:00Z"}})["result"]
        self.assertIn("2026-01-01T00:00:00Z", got["messages"][0]["content"]["text"])
        self.assertIn("error", self.call("prompts/get", {"name": "nope"}))

    def test_resource_read_when_api_down_is_an_error_not_a_crash(self):
        old = nivora_mcp.URL
        nivora_mcp.URL = "http://127.0.0.1:1"
        try:
            self.assertEqual(self.call("resources/read", {"uri": "nivora://findings"})["error"]["code"], -32603)
        finally:
            nivora_mcp.URL = old


if __name__ == "__main__":
    unittest.main()
