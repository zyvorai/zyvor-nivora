#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Capture real CLI output for the landing page's terminal tabs and the README maturity table.

Usage: build-site-terminal.py <built-site-dir>
Starts the collector on simulated telemetry (--demo) on a free loopback port, runs nivoractl against it, and
replaces <!--TERMINAL--> and <!--MATURITY--> in index.html. Output is trimmed, never edited. Stdlib only.
"""
from __future__ import annotations

import html
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 16


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def capture() -> list[tuple[str, str]]:
    port, token = free_port(), "site-build"
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen([sys.executable, "-B", str(ROOT / "agent" / "nivora.py"), "--demo", "--quiet", "--port", str(port), "--token", token,
                                 "--database", f"{tmp}/h.sqlite", "--rules", f"{tmp}/r.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5)
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                return []
            base = ["--url", f"http://127.0.0.1:{port}", "--token", token]

            def ctl(*args: str) -> str:
                r = subprocess.run([sys.executable, "-B", str(ROOT / "agent" / "nivoractl.py"), *base, *args], capture_output=True, text=True, timeout=20)
                lines = (r.stdout or r.stderr).rstrip().splitlines()
                more = len(lines) - MAX_LINES
                return "\n".join(lines[:MAX_LINES] + ([f"… {more} more line(s)"] if more > 0 else []))

            req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/flows", headers={"Authorization": f"Bearer {token}"})
            flow_id = json.load(urllib.request.urlopen(req, timeout=5))[0]["id"]
            policy = Path(tmp) / "work.json"
            policy.write_text(json.dumps({"name": "work", "rules": [{"action": "shadow", "domain": "example.com"}]}))
            return [
                ("health", "$ nivoractl health\n" + ctl("health")),
                ("trust", "$ nivoractl trust\n" + ctl("trust")),
                ("explain", f"$ nivoractl explain {flow_id}\n" + ctl("explain", flow_id)),
                ("policy", "$ nivoractl policy-plan work.json\n" + ctl("policy-plan", str(policy))),
            ]
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def terminal_html(tabs: list[tuple[str, str]]) -> str:
    if not tabs:
        return ""
    buttons = "".join(f'<button type="button" role="tab" aria-selected="{str(i == 0).lower()}" data-tab="{k}">{k}</button>' for i, (k, _) in enumerate(tabs))
    panes = "".join(f'<pre class="term-pane" data-pane="{k}"{"" if i == 0 else " hidden"}><code>{html.escape(v)}</code></pre>' for i, (k, v) in enumerate(tabs))
    return ('<section id="terminal"><h2>The CLI, on simulated data</h2>'
            '<p class="sub">This output was captured when the site was built, from <code>nivoractl</code> against <code>--demo</code>. Nothing here is hand-written.</p>'
            f'<div class="term" id="term"><div class="term-tabs" role="tablist">{buttons}</div>{panes}</div></section>')


def maturity_html() -> str:
    text = (ROOT / "README.md").read_text()
    m = re.search(r"## Maturity\n\n(\|.*\n)+", text)
    if not m:
        return ""
    rows = [r for r in m.group(0).splitlines() if r.startswith("|")][2:]
    out = ""
    for r in rows:
        area, _, status = [c.strip() for c in r.strip("|").partition("|")]
        esc = lambda t: re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", html.escape(t, quote=False))
        unverified = bool(re.search(r"not exercised|untested|compile-verified|unsigned|not notarised", status, re.I))
        out += f'<tr><td><b>{esc(area)}</b></td><td class="{"no" if unverified else "yes"}">{esc(status)}</td></tr>'
    return ('<section id="verified"><h2>What is verified, and what is not</h2>'
            '<p class="sub">Copied from the repository README at build time, so the site never claims more than the repo does.</p>'
            f'<div class="table-wrap"><table><thead><tr><th>Area</th><th>Status</th></tr></thead><tbody>{out}</tbody></table></div></section>')


def main(out: Path) -> int:
    page = out / "index.html"
    s = page.read_text()
    s = s.replace("<!--TERMINAL-->", terminal_html(capture())).replace("<!--MATURITY-->", maturity_html())
    page.write_text(s)
    print("terminal + maturity filled" if "id=\"terminal\"" in s else "terminal capture unavailable (section omitted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
