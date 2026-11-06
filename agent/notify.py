# SPDX-License-Identifier: BUSL-1.1
"""Optional alert delivery for findings: JSON webhook and/or syslog. Off unless configured (observe-first).

Only the finding itself is sent (severity, kind, title, detail, app, remote). Each distinct finding is delivered
once per cooldown. Stdlib only; webhook delivery runs on a daemon thread and never blocks sampling.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any
from urllib.parse import urlsplit

SEVERITY = {"info": 0, "warning": 1, "critical": 2}
_SYSLOG_LEVEL = {"info": "LOG_INFO", "warning": "LOG_WARNING", "critical": "LOG_CRIT"}


def finding_key(f: dict[str, Any]) -> tuple:
    return (f.get("kind"), f.get("title"), f.get("app"), f.get("remote"))


def validate_webhook(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("--alert-webhook must be an http(s) URL")
    return url


class Notifier:
    def __init__(self, webhook: str = "", syslog: bool = False, min_severity: str = "warning",
                 cooldown: float = 3600.0, clock=time.time, post=None, log=None):
        self.webhook = validate_webhook(webhook) if webhook else ""
        self.syslog = bool(syslog)
        if min_severity not in SEVERITY:
            raise ValueError("--alert-min-severity must be info, warning or critical")
        self.min = SEVERITY[min_severity]
        self.cooldown = max(0.0, cooldown)
        self.clock = clock
        self._post = post or self._http_post
        self._log = log or self._syslog_write
        self._sent: dict[tuple, float] = {}
        self.lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.webhook or self.syslog)

    def due(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Findings at or above the threshold not delivered within the cooldown; marks them delivered."""
        now = self.clock()
        out = []
        with self.lock:
            live = {finding_key(f) for f in findings}
            # Forget findings that went away so a recurrence alerts again.
            for k in [k for k in self._sent if k not in live]:
                del self._sent[k]
            for f in findings:
                if SEVERITY.get(f.get("severity"), 0) < self.min:
                    continue
                k = finding_key(f)
                if k in self._sent and now - self._sent[k] < self.cooldown:
                    continue
                self._sent[k] = now
                out.append(f)
        return out

    def consider(self, findings: list[dict[str, Any]], timestamp: str = "") -> int:
        if not self.enabled:
            return 0
        fresh = self.due(findings)
        for f in fresh:
            item = {k: f.get(k) for k in ("severity", "kind", "title", "detail", "app", "remote") if f.get(k) is not None}
            if self.syslog:
                self._log(f.get("severity", "info"), f"nivora {item.get('severity')}: {item.get('title')} - {item.get('detail', '')}")
            if self.webhook:
                body = json.dumps({"source": "nivora", "timestamp": timestamp, "finding": item}).encode()
                threading.Thread(target=self._safe_post, args=(body,), daemon=True).start()
        return len(fresh)

    def _safe_post(self, body: bytes) -> None:
        try:
            self._post(self.webhook, body)
        except Exception as exc:  # delivery problems must never affect sampling
            print(f"nivora: alert webhook failed: {exc}", flush=True)

    @staticmethod
    def _http_post(url: str, body: bytes) -> None:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "nivora"})
        with urllib.request.urlopen(req, timeout=5):
            pass

    @staticmethod
    def _syslog_write(severity: str, message: str) -> None:
        import syslog
        syslog.openlog("nivora", 0, syslog.LOG_USER)
        syslog.syslog(getattr(syslog, _SYSLOG_LEVEL.get(severity, "LOG_INFO")), message)
