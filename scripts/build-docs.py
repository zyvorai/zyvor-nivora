#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Build /docs/ for GitHub Pages from docs/*.md, CHANGELOG.md and SECURITY.md.

Usage: build-docs.py <built-site-dir>
Stdlib only. A deliberately small Markdown subset (ATX headings, fenced code, lists, tables, blockquotes,
rules, inline code/bold/italic/links). All text is HTML-escaped; unsafe link schemes are dropped.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_BLOB = "https://github.com/zyvorai/zyvor-nivora/blob/main/"
GROUPS = [
    ("Start", ["INSTALL", "WIDGETS"]),
    ("Reference", ["API", "ARCHITECTURE", "FLUXVM", "CAPTURE", "NETWORKEXTENSION"]),
    ("Project", ["TESTING", "UX-CONTRACT", "PRODUCT-REVIEW", "CHANGELOG", "SECURITY"]),
]


def slugify(text: str) -> str:
    s = re.sub(r"`([^`]*)`", r"\1", text).lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", s.strip()).strip("-") or "section"


def safe_url(url: str) -> str:
    url = url.strip()
    if re.match(r"^(https?:|mailto:|#|/|\.{0,2}/|[\w./-]+)", url) and not re.match(r"^\s*(javascript|data|vbscript):", url, re.I):
        return url
    return "#"


def rewrite_link(url: str, doc_dir: str, pages: set[str]) -> str:
    url = safe_url(url)
    if re.match(r"^(https?:|mailto:|#)", url):
        return url
    path, _, frag = url.partition("#")
    name = Path(path).name
    stem = name[:-3] if name.lower().endswith(".md") else None
    if stem is not None and stem.upper() in pages and (doc_dir == "docs" or path.startswith(("docs/", "./docs/"))
                                                       or "/" not in path or path.startswith("../docs/")):
        return stem.lower() + ".html" + (("#" + frag) if frag else "")
    rel = (Path(doc_dir) / path).as_posix() if doc_dir else path
    parts: list[str] = []
    for part in rel.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return REPO_BLOB + "/".join(parts) + (("#" + frag) if frag else "")


def inline(text: str, doc_dir: str, pages: set[str]) -> str:
    codes: list[str] = []

    def stash(m: re.Match) -> str:
        codes.append("<code>" + html.escape(m.group(1), quote=False) + "</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: '<a href="%s"%s>%s</a>' % (
                      html.escape(rewrite_link(html.unescape(m.group(2)), doc_dir, pages), quote=True),
                      ' rel="noopener"' if m.group(2).startswith("http") else "", m.group(1)), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def render(md: str, doc_dir: str, pages: set[str]) -> tuple[str, list[tuple[int, str, str]], str]:
    lines = md.splitlines()
    out: list[str] = []
    heads: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    title = ""
    i = 0

    def heading_id(text: str) -> str:
        base = slugify(text)
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f"{base}-{seen[base]}"

    def table_cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    while i < len(lines):
        line = lines[i]
        m = re.match(r"^```\s*([\w+-]*)\s*$", line)
        if m:
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{html.escape(m.group(1))}"' if m.group(1) else ""
            out.append(f"<pre><code{cls}>" + html.escape("\n".join(buf), quote=False) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            hid = heading_id(text)
            if level == 1 and not title:
                title = re.sub(r"`", "", text)
            heads.append((level, hid, re.sub(r"[`*]", "", text)))
            link = "" if level == 1 else f'<a class="anchor" href="#{hid}" aria-label="Link to this section">#</a>'
            out.append(f'<h{level} id="{hid}">{inline(text, doc_dir, pages)}{link}</h{level}>')
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            head = table_cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(table_cells(lines[i]))
                i += 1
            t = "<div class=\"table-wrap\"><table><thead><tr>" + "".join(f"<th>{inline(c, doc_dir, pages)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in rows:
                t += "<tr>" + "".join(f"<td>{inline(c, doc_dir, pages)}</td>" for c in r) + "</tr>"
            out.append(t + "</tbody></table></div>")
            continue
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf), doc_dir, pages) + "</p></blockquote>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            items: list[str] = []
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if mm:
                    items.append(mm.group(3))
                    i += 1
                elif lines[i].startswith("  ") and lines[i].strip() and items and not re.match(r"^\s*(```|\|)", lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x, doc_dir, pages)}</li>" for x in items) + f"</{tag}>")
            continue
        if not line.strip():
            i += 1
            continue
        buf = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|>|\s*([-*]|\d+\.)\s|\s*\|)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(buf), doc_dir, pages) + "</p>")
    return "\n".join(out), heads, title


PAGE = """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="color-scheme" content="light dark" />
<title>{title} · Nivora docs</title>
<meta name="description" content="{desc}" />
<link rel="icon" href="../favicon.svg" type="image/svg+xml" />
<link rel="canonical" href="https://zyvorai.github.io/zyvor-nivora/docs/{slug}.html" />
<meta property="og:title" content="{title} · Nivora docs" />
<meta property="og:description" content="{desc}" />
<meta property="og:image" content="https://zyvorai.github.io/zyvor-nivora/social/og.png" />
<script src="../theme.js"></script>
<link rel="stylesheet" href="../site.css" />
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="bar">
  <a class="brand" href="../" aria-label="Zyvor Nivora home"><img class="logo" src="../favicon.svg" width="30" height="30" alt="" /><span>Nivora</span></a>
  <nav aria-label="Sections" id="sections"><a href="../#gallery">See it</a><a href="../#features">Features</a><a href="./" aria-current="true">Docs</a><a href="../#install">Install</a></nav>
  <div class="bar-actions">
    <button id="theme" class="icon" type="button" aria-label="Switch to dark mode" aria-pressed="false">
      <svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
      <svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    </button>
    <a class="btn small" href="https://github.com/zyvorai/zyvor-nivora">GitHub</a>
    <a class="btn small primary" href="../demo/">Live demo</a>
  </div>
</header>
<div class="docs">
  <aside class="docs-nav" aria-label="Documentation">
    <label class="sr" for="docsearch">Search the docs</label>
    <input id="docsearch" type="search" placeholder="Search docs" autocomplete="off" />
    <div id="docresults" hidden></div>
    {nav}
  </aside>
  <main id="main" class="prose">
{body}
    <p class="edit"><a href="{edit}">Edit this page on GitHub</a></p>
  </main>
  <aside class="docs-toc" aria-label="On this page">{toc}</aside>
</div>
<footer><p><b>Zyvor Nivora</b> · © 2026 Zyvor AI Labs Private Limited · BUSL-1.1 · <a href="../">Home</a> · <a href="../feed.xml">Feed</a></p></footer>
<script src="../docs.js"></script>
</body>
</html>
"""


def collect() -> list[dict]:
    files: dict[str, Path] = {p.stem.upper(): p for p in sorted((ROOT / "docs").glob("*.md"))}
    for extra in ("CHANGELOG", "SECURITY"):
        if (ROOT / f"{extra}.md").exists():
            files[extra] = ROOT / f"{extra}.md"
    order = [n for _, names in GROUPS for n in names if n in files]
    order += [n for n in files if n not in order]
    return [{"key": n, "path": files[n], "slug": n.lower(), "dir": "docs" if files[n].parent.name == "docs" else ""} for n in order]


def first_paragraph(md: str) -> str:
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if b and not b.startswith(("#", "```", "|", "-", ">", "1.")):
            return re.sub(r"\s+", " ", re.sub(r"[`*\[\]]", "", b))[:180]
    return "Nivora documentation."


def main(out: Path) -> int:
    pages_meta = collect()
    keys = {p["key"] for p in pages_meta}
    dest = out / "docs"
    dest.mkdir(parents=True, exist_ok=True)
    rendered = []
    for p in pages_meta:
        md = p["path"].read_text()
        body, heads, title = render(md, p["dir"], keys)
        rendered.append({**p, "body": body, "heads": heads, "title": title or p["key"].title(), "desc": first_paragraph(md), "md": md})
    group_of = {n: g for g, names in GROUPS for n in names}

    def nav(current: str) -> str:
        buckets: dict[str, list[str]] = {}
        for r in rendered:
            g = group_of.get(r["key"], "More")
            cur = ' aria-current="page"' if r["key"] == current else ""
            buckets.setdefault(g, []).append(f'<li><a href="{r["slug"]}.html"{cur}>{html.escape(r["title"])}</a></li>')
        order = [g for g, _ in GROUPS] + ["More"]
        return "".join(f"<h2 class=\"nav-h\">{g}</h2><ul>{''.join(buckets[g])}</ul>" for g in order if g in buckets)

    search = []
    for r in rendered:
        toc_items = [(lvl, hid, txt) for lvl, hid, txt in r["heads"] if lvl in (2, 3)]
        toc = ("<h2 class=\"nav-h\">On this page</h2><ul>" + "".join(
            f'<li class="l{lvl}"><a href="#{hid}">{html.escape(txt)}</a></li>' for lvl, hid, txt in toc_items) + "</ul>") if toc_items else ""
        edit = REPO_BLOB + (f"docs/{r['path'].name}" if r["dir"] else r["path"].name)
        page = PAGE.format(title=html.escape(r["title"]), desc=html.escape(r["desc"], quote=True), slug=r["slug"], nav=nav(r["key"]),
                           body=r["body"], toc=toc, edit=html.escape(edit))
        (dest / f"{r['slug']}.html").write_text(page)
        search.append({"title": r["title"], "heading": "", "url": f"{r['slug']}.html"})
        for lvl, hid, txt in r["heads"]:
            if lvl in (2, 3):
                search.append({"title": r["title"], "heading": txt, "url": f"{r['slug']}.html#{hid}"})
    cards = "".join(f'<li><a href="{r["slug"]}.html"><b>{html.escape(r["title"])}</b></a><span>{html.escape(r["desc"])}</span></li>' for r in rendered)
    index_body = ('<h1 id="docs">Nivora documentation</h1><p>Install it, call the API, understand the architecture. '
                  'Everything here is built from the Markdown in the repository.</p><ul class="doc-cards">' + cards + "</ul>")
    (dest / "index.html").write_text(PAGE.format(title="Documentation", desc="Nivora installation, API, architecture and project docs.", slug="index",
                                                 nav=nav(""), body=index_body, toc="", edit=html.escape(REPO_BLOB + "docs/")).replace("/docs/index.html", "/docs/"))
    (dest / "search.json").write_text(json.dumps(search, separators=(",", ":")))
    sm = out / "sitemap.xml"
    if sm.exists():
        extra = "".join(f"  <url><loc>https://zyvorai.github.io/zyvor-nivora/docs/{r['slug']}.html</loc></url>\n" for r in rendered)
        extra = "  <url><loc>https://zyvorai.github.io/zyvor-nivora/docs/</loc></url>\n" + extra
        sm.write_text(sm.read_text().replace("</urlset>", extra + "</urlset>", 1))
    print(f"docs: {len(rendered)} pages, {len(search)} search entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
