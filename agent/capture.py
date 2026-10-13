#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Client for the privileged Nivora capture helper, plus a synthetic pcap writer for demo mode.

The helper (native/CaptureHelper) is the authority: it re-validates everything. This module validates
first so bad input never reaches the socket and the UI gets precise errors. Packet capture is opt-in per
session, headers-only by default (snaplen 96), and time/size capped.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import struct
import time
from typing import Any

DEFAULT_SOCKET = "/var/run/dev.zyvor.nivora.capture.sock"
MIN_SNAPLEN, DEFAULT_SNAPLEN, MAX_SNAPLEN = 54, 96, 256
DEFAULT_SECONDS, MAX_SECONDS = 60, 300
DEFAULT_MB, MAX_MB = 16, 64
PROTOCOLS = {"tcp", "udp", "icmp", "any"}
_IFACE = re.compile(r"^[a-z]{1,12}[0-9]{1,4}$")
_SESSION_ID = re.compile(r"^[0-9a-f]{16}$")


class CaptureError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def validate_request(body: dict[str, Any], known_interfaces: set[str] | None = None) -> dict[str, Any]:
    """Mirror of CaptureValidator.plan (Swift): returns the normalised request or raises CaptureError."""
    iface = str(body.get("iface", ""))
    if not _IFACE.match(iface) or not 2 <= len(iface) <= 16:
        raise CaptureError("interface name is not valid")
    if known_interfaces is not None and iface not in known_interfaces:
        raise CaptureError(f"unknown interface {iface}")
    out: dict[str, Any] = {"op": "start", "iface": iface}
    host = body.get("host")
    if host not in (None, ""):
        try:
            ipaddress.ip_address(str(host))
        except ValueError:
            raise CaptureError("host must be a literal IP address") from None
        out["host"] = str(host)
    proto = str(body.get("proto") or "any").lower()
    if proto not in PROTOCOLS:
        raise CaptureError("protocol must be tcp, udp, icmp or any")
    out["proto"] = proto
    if body.get("port") not in (None, ""):
        try:
            port = int(body["port"])
        except (TypeError, ValueError):
            raise CaptureError("port out of range") from None
        if not 1 <= port <= 65535:
            raise CaptureError("port out of range")
        if proto == "icmp":
            raise CaptureError("ports apply to tcp/udp only")
        out["port"] = port

    def bounded(key: str, default: int, lo: int, hi: int, label: str) -> int:
        try:
            value = int(body.get(key, default) if body.get(key) is not None else default)
        except (TypeError, ValueError):
            raise CaptureError(f"{label} must be {lo}-{hi}") from None
        if not lo <= value <= hi:
            raise CaptureError(f"{label} must be {lo}-{hi}")
        return value

    out["snaplen"] = bounded("snaplen", DEFAULT_SNAPLEN, MIN_SNAPLEN, MAX_SNAPLEN, "snaplen")
    out["seconds"] = bounded("seconds", DEFAULT_SECONDS, 1, MAX_SECONDS, "duration")
    out["max_mb"] = bounded("max_mb", DEFAULT_MB, 1, MAX_MB, "size cap")
    return out


def validate_session_id(value: str) -> str:
    if not _SESSION_ID.match(value or ""):
        raise CaptureError("invalid capture id")
    return value


def manual_command(req: dict[str, Any]) -> str:
    """The equivalent command a user could run themselves when the helper is not installed."""
    parts = ["sudo", "tcpdump", "-n", "-p", "-i", req["iface"], "-s", str(req["snaplen"]), "-G", str(req["seconds"]), "-W", "1", "-w", "nivora.pcap"]
    expr = []
    if req.get("host"):
        expr += ["host", req["host"]]
    if req.get("proto") and req["proto"] != "any":
        expr += (["and"] if expr else []) + [req["proto"]]
    if req.get("port"):
        expr += (["and"] if expr else []) + ["port", str(req["port"])]
    return " ".join(parts + expr)


class CaptureClient:
    def __init__(self, path: str | None = None, timeout: float = 3.0):
        self.path = path or os.environ.get("NIVORA_CAPTURE_SOCKET", DEFAULT_SOCKET)
        self.timeout = timeout

    def _connect(self) -> socket.socket:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.path)
        except OSError as exc:
            s.close()
            raise CaptureError("capture helper is not installed or not running", 501) from exc
        return s

    @staticmethod
    def _readline(s: socket.socket) -> tuple[bytes, bytes]:
        buf = b""
        while b"\n" not in buf and len(buf) < 1_000_000:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        line, _, rest = buf.partition(b"\n")
        return line, rest

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        s = self._connect()
        try:
            s.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            line, _ = self._readline(s)
        finally:
            s.close()
        try:
            reply = json.loads(line or b"{}")
        except json.JSONDecodeError as exc:
            raise CaptureError("capture helper returned an invalid reply", 502) from exc
        if not reply.get("ok"):
            raise CaptureError(str(reply.get("error", "capture helper error")))
        return reply

    def available(self) -> bool:
        try:
            return bool(self.call({"op": "status"}).get("tcpdump"))
        except CaptureError:
            return False

    def start(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.call(request)["session"]

    def list(self) -> list[dict[str, Any]]:
        return self.call({"op": "list"}).get("sessions", [])

    def stop(self, sid: str) -> None:
        self.call({"op": "stop", "id": validate_session_id(sid)})

    def delete(self, sid: str) -> None:
        self.call({"op": "delete", "id": validate_session_id(sid)})

    def fetch(self, sid: str, limit: int = 80 * 1024 * 1024) -> bytes:
        s = self._connect()
        try:
            s.sendall(json.dumps({"op": "fetch", "id": validate_session_id(sid)}).encode() + b"\n")
            line, rest = self._readline(s)
            header = json.loads(line or b"{}")
            if not header.get("ok"):
                raise CaptureError(str(header.get("error", "no such capture")), 404)
            size = int(header.get("size", 0))
            if size < 0 or size > limit:
                raise CaptureError("capture too large to download", 413)
            data = bytearray(rest)
            while len(data) < size:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
            return bytes(data[:size])
        finally:
            s.close()


def synthetic_pcap(count: int = 24, snaplen: int = DEFAULT_SNAPLEN, now: float | None = None) -> bytes:
    """A valid little-endian pcap (Ethernet/IPv4/TCP headers only) for demo mode and tests."""
    now = time.time() if now is None else now
    out = bytearray(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, snaplen, 1))
    for i in range(count):
        tcp = struct.pack("!HHIIBBHHH", 53001, 443, 1000 + i * 100, 5000 + i * 50, 5 << 4, 0x18, 65535, 0, 0)
        total = 20 + len(tcp)
        ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0x1000 + i, 0, 64, 6, 0, bytes([192, 168, 1, 42]), bytes([142, 250, 183, 14]))
        eth = bytes.fromhex("aabbccddee01") + bytes.fromhex("001122334455") + b"\x08\x00"
        frame = (eth + ip + tcp)[:snaplen]
        ts = now + i * 0.05
        out += struct.pack("<IIII", int(ts), int((ts % 1) * 1e6), len(frame), len(eth + ip + tcp))
        out += frame
    return bytes(out)
