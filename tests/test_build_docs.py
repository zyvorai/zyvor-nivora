# SPDX-License-Identifier: BUSL-1.1
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_docs", ROOT / "scripts" / "build-docs.py")
bd = importlib.util.module_from_spec(spec)
sys.modules["build_docs"] = bd
spec.loader.exec_module(bd)

PAGES = {"API", "INSTALL"}


def render(md, doc_dir="docs"):
    return bd.render(md, doc_dir, PAGES)


class MarkdownTests(unittest.TestCase):
    def test_html_is_escaped_everywhere(self):
        html, _, _ = render("# T <script>x</script>\n\ntext <img src=x onerror=alert(1)> `<b>` **<i>**\n\n| a<script> |\n|---|\n| <u> |\n")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<u>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_unsafe_link_schemes_are_neutralised(self):
        html, _, _ = render("[x](javascript:alert(1)) [y](data:text/html,hi) [ok](https://example.com)")
        self.assertNotIn("javascript:", html)
        self.assertNotIn("data:text", html)
        self.assertIn('href="https://example.com"', html)

    def test_headings_get_unique_ids_and_title(self):
        html, heads, title = render("# Title\n\n## Same\n\n## Same\n\n### Deep `code`\n")
        self.assertEqual(title, "Title")
        self.assertEqual([h[1] for h in heads], ["title", "same", "same-2", "deep-code"])
        self.assertIn('id="same-2"', html)

    def test_code_fences_tables_lists(self):
        html, _, _ = render("```bash\necho '<x>' && ls\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n\n1. first\n2. second\n")
        self.assertIn("&lt;x&gt;", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td>2</td>", html)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", html)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", html)

    def test_link_rewriting(self):
        self.assertEqual(bd.rewrite_link("INSTALL.md#option-1", "docs", PAGES), "install.html#option-1")
        self.assertEqual(bd.rewrite_link("docs/API.md", "", PAGES), "api.html")
        self.assertEqual(bd.rewrite_link("../README.md#privacy", "docs", PAGES), bd.REPO_BLOB + "README.md#privacy")
        self.assertEqual(bd.rewrite_link("../agent/nivora.py", "docs", PAGES), bd.REPO_BLOB + "agent/nivora.py")
        self.assertEqual(bd.rewrite_link("https://x.dev/a", "docs", PAGES), "https://x.dev/a")
        self.assertEqual(bd.rewrite_link("#frag", "docs", PAGES), "#frag")

    def test_full_build_writes_pages_search_and_sitemap(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "sitemap.xml").write_text("<urlset>\n</urlset>")
            self.assertEqual(bd.main(out), 0)
            for name in ("index.html", "api.html", "install.html", "changelog.html", "search.json"):
                self.assertTrue((out / "docs" / name).exists(), name)
            self.assertIn("/docs/api.html", (out / "sitemap.xml").read_text())
            page = (out / "docs" / "api.html").read_text()
            self.assertIn('<script src="../docs.js">', page)
            self.assertEqual(page.count("<h1"), 1)


if __name__ == "__main__":
    unittest.main()
