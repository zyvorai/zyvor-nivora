// SPDX-License-Identifier: BUSL-1.1
// Fails if the built site references a missing local file, loads anything from another origin, or lacks basics.
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || new URL('../_site', import.meta.url).pathname);
const problems = [];
const pages = ['index.html', '404.html', 'demo/index.html'];
for (const page of pages) {
  const file = path.join(root, page);
  if (!fs.existsSync(file)) { problems.push(`missing ${page}`); continue; }
  const html = fs.readFileSync(file, 'utf8');
  if (!/<title>[^<]{8,}<\/title>/.test(html)) problems.push(`${page}: title missing`);
  if (page === 'index.html') {
    for (const m of ['name="description"', 'property="og:image"', 'rel="canonical"', 'rel="icon"', 'Zyvor AI Labs Private Limited', 'BUSL-1.1'])
      if (!html.includes(m)) problems.push(`${page}: missing ${m}`);
  }
  for (const m of html.matchAll(/\b(?:src|href)="([^"#?]+)(?:[?#][^"]*)?"/g)) {
    const ref = m[1];
    if (/^(https?:|mailto:|data:)/.test(ref)) continue; // outbound links are fine; subresources are checked below
    const target = ref.startsWith('/') ? path.join(root, ref) : path.join(path.dirname(file), ref);
    const resolved = fs.existsSync(target) && fs.statSync(target).isDirectory() ? path.join(target, 'index.html') : target;
    if (!fs.existsSync(resolved)) problems.push(`${page}: broken reference ${ref}`);
  }
  // no third-party subresources (fonts, CDNs, trackers)
  for (const m of html.matchAll(/<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)="(https?:\/\/[^"]+)"/g)) {
    if (/rel="(?:canonical|alternate)"/.test(m[0])) continue;
    problems.push(`${page}: external subresource ${m[1]}`);
  }
}
for (const f of ['robots.txt', 'sitemap.xml', '.nojekyll', 'favicon.svg', 'social/og.png', 'demo/demo-snapshot.json', 'demo/demo.js'])
  if (!fs.existsSync(path.join(root, f))) problems.push(`missing ${f}`);
if (!/data-demo/.test(fs.readFileSync(path.join(root, 'demo/index.html'), 'utf8'))) problems.push('demo/index.html is not flagged data-demo');
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
console.log(`site-check: ${pages.length} pages OK`);
