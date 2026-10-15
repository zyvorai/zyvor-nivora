# SPDX-License-Identifier: BUSL-1.1
"""On-demand reachability check for one destination: DNS, TCP connect, TLS handshake. Only runs when asked."""
from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def validate_target(host: Any, port: Any) -> tuple[str, int]:
    host = str(host or "").strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOST_RE.match(host):
            raise ValueError("host must be a hostname or IP address")
    try:
        port = int(port if port not in (None, "") else 443)
    except (TypeError, ValueError):
        raise ValueError("port must be 1..65535")
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    return host, port


def _ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


def check_target(host: str, port: int = 443, timeout: float = 3.0, tls: bool | None = None) -> dict[str, Any]:
    host, port = validate_target(host, port)
    use_tls = port in {443, 853, 8443} if tls is None else tls
    stages: list[dict[str, Any]] = []
    result = {"host": host, "port": port, "stages": stages, "ok": False, "summary": ""}

    t0 = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            infos = ex.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM).result(timeout=timeout)
        addrs = list(dict.fromkeys(i[4][0] for i in infos))
        stages.append({"stage": "dns", "ok": True, "ms": _ms(t0), "addresses": addrs[:6]})
    except (OSError, FutureTimeout) as exc:
        stages.append({"stage": "dns", "ok": False, "ms": _ms(t0), "error": "timed out" if isinstance(exc, FutureTimeout) else str(exc)})
        result["summary"] = "Name resolution failed: check the resolver (see /v1/dns) and VPN split-DNS."
        return result

    t0 = time.monotonic()
    sock = None
    try:
        sock = socket.create_connection((addrs[0], port), timeout=timeout)
        stages.append({"stage": "tcp", "ok": True, "ms": _ms(t0), "address": addrs[0]})
    except OSError as exc:
        stages.append({"stage": "tcp", "ok": False, "ms": _ms(t0), "address": addrs[0], "error": str(exc)})
        result["summary"] = f"Resolved to {addrs[0]} but the TCP connection failed: blocked, filtered or down."
        return result

    if use_tls:
        t0 = time.monotonic()
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(sock, server_hostname=None if _is_ip(host) else host) as tls_sock:
                cert = tls_sock.getpeercert() or {}
                stage = {"stage": "tls", "ok": True, "ms": _ms(t0), "version": tls_sock.version()}
                if cert.get("notAfter"):
                    stage["not_after"] = cert["notAfter"]
                    stage["days_left"] = int((ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) // 86400)
                stages.append(stage)
        except (OSError, ssl.SSLError) as exc:
            stages.append({"stage": "tls", "ok": False, "ms": _ms(t0), "error": str(exc)})
            result["summary"] = "TCP works but the TLS handshake failed: certificate, interception or protocol problem."
            return result
    else:
        sock.close()
    result["ok"] = True
    result["summary"] = "Reachable: " + ", ".join(f"{s['stage']} {s['ms']} ms" for s in stages) + "."
    return result


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
