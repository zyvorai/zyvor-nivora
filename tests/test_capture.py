# SPDX-License-Identifier: BUSL-1.1
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from capture import CaptureClient, CaptureError, manual_command, synthetic_pcap, validate_request, validate_session_id  # noqa: E402


class ValidatorTests(unittest.TestCase):
    def test_defaults_are_headers_only_and_bounded(self):
        r = validate_request({"iface": "en0"})
        self.assertEqual((r["snaplen"], r["seconds"], r["max_mb"], r["proto"]), (96, 60, 16, "any"))

    def test_rejects_injection_and_out_of_range(self):
        bad = [
            {"iface": "en0; rm -rf /"}, {"iface": "../en0"}, {"iface": ""}, {"iface": "EN0"},
            {"iface": "en0", "host": "example.com"}, {"iface": "en0", "host": "1.2.3.4 or port 22"},
            {"iface": "en0", "proto": "ip proto 47"}, {"iface": "en0", "port": 70000},
            {"iface": "en0", "proto": "icmp", "port": 53}, {"iface": "en0", "snaplen": 65535},
            {"iface": "en0", "seconds": 3600}, {"iface": "en0", "max_mb": 4096}, {"iface": "en0", "port": "abc"},
        ]
        for body in bad:
            with self.assertRaises(CaptureError, msg=str(body)):
                validate_request(body)

    def test_unknown_interface_is_rejected_when_inventory_known(self):
        with self.assertRaises(CaptureError):
            validate_request({"iface": "en9"}, {"en0", "lo0"})
        self.assertEqual(validate_request({"iface": "en0"}, {"en0"})["iface"], "en0")

    def test_session_ids(self):
        validate_session_id("0123456789abcdef")
        for bad in ["", "../etc/passwd", "0123456789ABCDEF", "short"]:
            with self.assertRaises(CaptureError):
                validate_session_id(bad)

    def test_manual_command_matches_request(self):
        cmd = manual_command(validate_request({"iface": "en0", "host": "1.2.3.4", "proto": "tcp", "port": 443}))
        self.assertIn("-s 96", cmd)
        self.assertTrue(cmd.endswith("host 1.2.3.4 and tcp and port 443"))


class FakeHelper:
    """Speaks the helper protocol on a unix socket so the client is tested without root or tcpdump."""

    def __init__(self, path):
        self.path = path
        self.pcap = synthetic_pcap(3)
        self.requests = []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)
        self.srv.listen(4)
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            line = b""
            while not line.endswith(b"\n"):
                chunk = c.recv(4096)
                if not chunk:
                    break
                line += chunk
            req = json.loads(line)
            self.requests.append(req)
            op = req["op"]
            if op == "status":
                reply = {"ok": True, "tcpdump": True}
            elif op == "start":
                reply = {"ok": True, "session": {"id": "0123456789abcdef", "iface": req["iface"], "state": "running", "bytes": 0}}
            elif op == "list":
                reply = {"ok": True, "sessions": [{"id": "0123456789abcdef", "state": "finished", "bytes": len(self.pcap)}]}
            elif op == "fetch":
                c.sendall(json.dumps({"ok": True, "size": len(self.pcap)}).encode() + b"\n" + self.pcap)
                c.close()
                continue
            else:
                reply = {"ok": True}
            c.sendall(json.dumps(reply).encode() + b"\n")
            c.close()

    def close(self):
        self.srv.close()


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(dir="/tmp")  # keep the AF_UNIX path short
        self.path = os.path.join(self.td.name, "c.sock")
        self.helper = FakeHelper(self.path)
        self.client = CaptureClient(self.path)

    def tearDown(self):
        self.helper.close()
        self.td.cleanup()

    def test_roundtrip(self):
        self.assertTrue(self.client.available())
        s = self.client.start(validate_request({"iface": "en0", "host": "1.2.3.4"}))
        self.assertEqual(s["id"], "0123456789abcdef")
        self.assertEqual(self.client.list()[0]["state"], "finished")
        data = self.client.fetch("0123456789abcdef")
        self.assertEqual(data[:4], struct.pack("<I", 0xA1B2C3D4))
        self.client.stop("0123456789abcdef")
        self.client.delete("0123456789abcdef")
        sent = [r["op"] for r in self.helper.requests]
        self.assertEqual(sent, ["status", "start", "list", "fetch", "stop", "delete"])

    def test_missing_helper_degrades(self):
        c = CaptureClient(os.path.join(self.td.name, "absent.sock"))
        self.assertFalse(c.available())
        with self.assertRaises(CaptureError) as ctx:
            c.list()
        self.assertEqual(ctx.exception.status, 501)


class PcapTests(unittest.TestCase):
    def test_synthetic_pcap_is_well_formed(self):
        data = synthetic_pcap(5, snaplen=96, now=1_700_000_000)
        magic, vmaj, vmin, _, _, snap, link = struct.unpack("<IHHiIII", data[:24])
        self.assertEqual((magic, vmaj, vmin, snap, link), (0xA1B2C3D4, 2, 4, 96, 1))
        off, n = 24, 0
        while off < len(data):
            _, _, caplen, origlen = struct.unpack("<IIII", data[off:off + 16])
            self.assertLessEqual(caplen, 96)
            self.assertGreaterEqual(origlen, caplen)
            off += 16 + caplen
            n += 1
        self.assertEqual((n, off), (5, len(data)))


if __name__ == "__main__":
    unittest.main()
