// SPDX-License-Identifier: BUSL-1.1
// Fails if the built site references a missing local file, loads anything from another origin, or lacks basics.
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || new URL('../_site', import.meta.url).pathname);
const problems = [];
const pages = ['index.html', '404.html', 'demo/index.html', 'docs/index.html'];
for (const f of fs.existsSync(path.join(root, 'docs')) ? fs.readdirSync(path.join(root, 'docs')) : []) {
  if (f.endsWith('.html') && f !== 'index.html') pages.push('docs/' + f);
}
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
for (const f of ['docs.js', 'docs/search.json', 'feed.xml', 'robots.txt', 'sitemap.xml', '.nojekyll', 'favicon.svg', 'social/og.png', 'demo/demo-snapshot.json', 'demo/demo.js'])
  if (!fs.existsSync(path.join(root, f))) problems.push(`missing ${f}`);
// release-aware content: the page must carry the package.json version and no leftover placeholders
const pkg = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const home = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
if (/\{\{[A-Z]+\}\}|<!--(?:DOWNLOAD|WHATSNEW)-->/.test(home)) problems.push('index.html: unreplaced placeholder');
if (!home.includes(`Nivora ${pkg.version}`) && !home.includes(`v${pkg.version}`)) problems.push(`index.html: version ${pkg.version} not shown`);
if (/__NIVORA_[A-Z_]+__/.test(home)) problems.push('index.html: a Nivora payment link placeholder is still in the page');
for (const which of ['signed', 'developer']) {
  const buy = home.match(new RegExp(`<a[^>]*\\bid="buy-${which}"[^>]*\\bhref="([^"]*)"`));
  if (!buy || !/^https:\/\/[^ ]+$/.test(buy[1])) problems.push(`index.html: buy-${which} link missing or not https`);
}
if (!/about US\$2\.99/.test(home) || !/299/.test(home)) problems.push('index.html: the price (₹299, about US$2.99) is not shown');
for (const id of ['terminal', 'verified', 'gallery', 'install']) if (!home.includes(`id="${id}"`)) problems.push(`index.html: missing section #${id}`);
// feature marketing: tour, bands, hero shot, theme-paired images that exist, honest labels
for (const id of ['tour', 'tour-steps', 'tour-stage', 'highlights', 'b-apps', 'b-flows', 'b-health', 'b-tm', 'b-exports', 'b-fluxvm']) if (!home.includes(`id="${id}"`)) problems.push(`index.html: missing #${id}`);
if (!/<nav[^>]*id="sections"[\s\S]*?href="#tour"[\s\S]*?href="#highlights"[\s\S]*?<\/nav>/.test(home)) problems.push('index.html: #sections nav lacks #tour/#highlights');
if (!/<ol class="steps"[\s\S]*?<\/ol>/.test(home) || (home.match(/class="step"[^>]*tabindex="0"/g) || []).length < 4) problems.push('index.html: tour steps missing or not focusable');
for (const m of home.matchAll(/<img\b[^>]*\bsrc="(ux\/native-(?:light|dark)-[a-z]+\.png)"/g)) {
  if (!fs.existsSync(path.join(root, m[1]))) problems.push(`index.html: image missing ${m[1]}`);
}
if ((home.match(/class="only-light/g) || []).length !== (home.match(/class="only-dark/g) || []).length) problems.push('index.html: light/dark image pairs are unbalanced');
if (!/simulated telemetry/i.test(home) || !/developer build only[\s\S]{0,120}compile-verified/i.test(home)) problems.push('index.html: demo / developer-build labels missing');
// note: ux/native-*-security.png is really the Health capture (files are mislabelled); the Capture pane (-capture.png) must not be marketed
const marketing = home.slice(home.indexOf('class="shotband"'), home.indexOf('id="gallery"'));
if (/native-(?:light|dark)-capture\.png/.test(marketing)) problems.push('index.html: the developer-build Capture pane is shown in the marketing sections');
// the picker is labelled by what each capture shows (-security is Health, -health is Interfaces, -capture is Local Network)
const paneLabels = Object.fromEntries([...home.matchAll(/<button[^>]*data-value="([a-z]+)">([^<]+)<\/button>/g)].map((m) => [m[1], m[2]]));
if (/Security|Capture/.test(Object.values(paneLabels).join(' ')) || paneLabels.security !== 'Health' || paneLabels.health !== 'Interfaces' || paneLabels.capture !== 'Local Network') problems.push('index.html: gallery pane labels do not match the capture contents');
if (!/\.js \.rv/.test(fs.readFileSync(path.join(root, 'site.css'), 'utf8'))) problems.push('site.css: reveal must be gated by html.js');
if (!fs.readFileSync(path.join(root, 'theme.js'), 'utf8').includes("classList.add('js')")) problems.push('theme.js: does not set html.js');
const sha = home.match(/id="sha">([^<]*)</);
if (sha && !/^[0-9a-f]{64}$/.test(sha[1])) problems.push('index.html: sha256 is not 64 hex characters');
const feedXml = fs.readFileSync(path.join(root, 'feed.xml'), 'utf8');
if (!/<feed[^>]+Atom/.test(feedXml) || !feedXml.includes('</feed>') || !/<entry>/.test(feedXml)) problems.push('feed.xml: not a valid Atom feed');
for (const m of home.matchAll(/<img\b[^>]*>/g)) {
  if (!/\balt="/.test(m[0]) || !/\bwidth="/.test(m[0]) || !/\bheight="/.test(m[0])) problems.push(`index.html: img without alt/width/height: ${m[0].slice(0, 80)}`);
}
for (const m of home.matchAll(/\bhref="#([^"]+)"/g)) {
  if (!home.includes(`id="${m[1]}"`)) problems.push(`index.html: anchor #${m[1]} has no target`);
}
if (!/data-demo/.test(fs.readFileSync(path.join(root, 'demo/index.html'), 'utf8'))) problems.push('demo/index.html is not flagged data-demo');
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
console.log(`site-check: ${pages.length} pages OK`);
