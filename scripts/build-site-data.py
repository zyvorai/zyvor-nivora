#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Fill the release-aware parts of the built site from package.json, CHANGELOG.md and SHA256SUMS.txt.

Usage: build-site-data.py <built-site-dir>
Replaces {{VERSION}}, {{DATE}}, {{COMMIT}} and the <!--DOWNLOAD--> / <!--WHATSNEW--> markers in index.html and
writes feed.xml. A checksum is shown only if SHA256SUMS.txt (from the release) lists Nivora-<version>.dmg;
otherwise the download block links to the release page and shows no hash. Stdlib only, no network.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/zyvorai/zyvor-nivora"
SITE = "https://zyvorai.github.io/zyvor-nivora/"


def inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)


def parse_changelog(text: str) -> list[dict]:
    releases: list[dict] = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"##\s+(\d+\.\d+\.\d+)\s*[—-]\s*(\d{4}-\d{2}-\d{2})", line)
        if m:
            cur = {"version": m.group(1), "date": m.group(2), "items": []}
            releases.append(cur)
        elif line.startswith("## "):
            cur = None
        elif cur is not None and line.startswith("- "):
            cur["items"].append(line[2:].strip())
        elif cur is not None and line.startswith("  ") and cur["items"]:
            cur["items"][-1] += " " + line.strip()
    return releases


def checksum_for(version: str, sums: str) -> str:
    for line in sums.splitlines():
        m = re.match(r"([0-9a-f]{64})\s+\*?(\S+)$", line.strip())
        if m and m.group(2) == f"Nivora-{version}.dmg":
            return m.group(1)
    return ""


def download_block(version: str, sha: str) -> str:
    url = f"{REPO}/releases/download/v{version}/Nivora-{version}.dmg"
    if not sha:
        return (f'<p><a class="btn primary" href="{REPO}/releases/tag/v{version}">Nivora {version} on GitHub Releases</a></p>'
                '<p class="sub">Checksums are listed on the release page.</p>')
    return (f'<div class="download card"><div><h3>Nivora {version} for Mac</h3>'
            f'<p>Apple silicon · macOS 14 or later · unsigned, not notarised (see the notice above).</p></div>'
            f'<p><a class="btn primary" href="{url}">Download Nivora-{version}.dmg</a></p>'
            f'<p class="sub">SHA-256</p><pre class="sha"><code id="sha">{sha}</code></pre>'
            f'<p class="sub">Verify: <code>echo "{sha}  Nivora-{version}.dmg" | shasum -a 256 -c</code></p></div>')


def whats_new(releases: list[dict], version: str) -> str:
    rel = next((r for r in releases if r["version"] == version), releases[0] if releases else None)
    if not rel:
        return ""
    items = "".join(f"<li>{inline(i)}</li>" for i in rel["items"][:8])
    return (f'<section id="new" class="whatsnew"><h2>New in {rel["version"]}</h2>'
            f'<p class="sub">{rel["date"]} · <a href="{REPO}/blob/main/CHANGELOG.md">full changelog</a> · <a href="feed.xml">feed</a></p>'
            f'<ul class="new-list">{items}</ul></section>')


def feed(releases: list[dict]) -> str:
    updated = (releases[0]["date"] if releases else "1970-01-01") + "T00:00:00Z"
    entries = []
    for r in releases[:20]:
        body = "<ul>" + "".join(f"<li>{inline(i)}</li>" for i in r["items"]) + "</ul>"
        entries.append(
            f'  <entry><title>Nivora {r["version"]}</title><id>tag:zyvorai.github.io,2026:nivora-{r["version"]}</id>'
            f'<updated>{r["date"]}T00:00:00Z</updated><link href="{REPO}/releases/tag/v{r["version"]}"/>'
            f'<content type="html">{html.escape(body)}</content></entry>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
            f'  <title>Nivora releases</title><id>{SITE}</id><updated>{updated}</updated>\n'
            f'  <link rel="self" href="{SITE}feed.xml"/><link href="{SITE}"/>\n' + "\n".join(entries) + "\n</feed>\n")


def main(out: Path) -> int:
    version = json.loads((ROOT / "package.json").read_text())["version"]
    releases = parse_changelog((ROOT / "CHANGELOG.md").read_text())
    sums_path = Path(os.environ.get("SHA256SUMS", ROOT / "SHA256SUMS.txt"))
    sha = checksum_for(version, sums_path.read_text()) if sums_path.exists() else ""
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        commit = ""
    date = dt.datetime.fromtimestamp(int(os.environ.get("SOURCE_DATE_EPOCH", dt.datetime.now(dt.timezone.utc).timestamp())), dt.timezone.utc).strftime("%Y-%m-%d")
    page = out / "index.html"
    s = page.read_text()
    s = s.replace("<!--DOWNLOAD-->", download_block(version, sha)).replace("<!--WHATSNEW-->", whats_new(releases, version))
    s = s.replace("{{VERSION}}", version).replace("{{DATE}}", date).replace("{{COMMIT}}", commit or "unknown")
    if re.search(r"\{\{[A-Z]+\}\}|<!--(?:DOWNLOAD|WHATSNEW)-->", s):
        print("unreplaced placeholder in index.html", file=sys.stderr)
        return 1
    page.write_text(s)
    (out / "feed.xml").write_text(feed(releases))
    print(f"site data: v{version}, checksum {'listed' if sha else 'not available'}, {len(releases)} release(s) in feed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
