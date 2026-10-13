// SPDX-License-Identifier: BUSL-1.1
// The static demo shim must answer the dashboard's API like the collector does.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webDir = new URL('../web/', import.meta.url);
globalThis.window = globalThis;
globalThis.location = { href: new URL('index.html?demo', webDir).href, search: '?demo' };
globalThis.document = {
  documentElement: { hasAttribute: () => false },
  currentScript: null,
  addEventListener() {},
  createElement: () => ({ setAttribute() {}, set innerHTML(v) {} }),
  body: { prepend() {} },
};
const fileFetch = async (u) => {
  const href = String(u.href || u);
  assert(href.startsWith('file:'), `unexpected network fetch: ${href}`);
  const text = fs.readFileSync(fileURLToPath(href), 'utf8');
  return new Response(text, { status: 200 });
};
globalThis.fetch = fileFetch;
await import(new URL('demo.js', webDir));

const get = async (p, init) => globalThis.fetch(p, init);
const json = async (p, init) => (await get(p, init)).json();

// snapshot has every top-level key the real collector emits
const base = JSON.parse(fs.readFileSync(new URL('demo-snapshot.json', webDir), 'utf8'));
const snap = await json('/v1/snapshot');
for (const k of Object.keys(base)) assert(k in snap, `snapshot missing ${k}`);
assert(snap.flows.length >= 6 && snap.apps.length >= 5, 'demo should have a lively sample');
assert(snap.traffic.total_bps > 0);

// rates move over time; counters only advance
const a = (await json('/v1/series?limit=5')).map(r => r.rx_bps);
assert.equal(a.length, 5);
assert(new Set(a).size > 1, 'series should not be flat');

// filter grammar is shared with the real UI
const udp = await json('/v1/flows?filter=' + encodeURIComponent('proto:udp'));
assert(udp.length >= 1 && udp.every(f => f.protocol === 'udp'));

// exports
const csv = await (await get('/v1/export?kind=flows&format=csv')).text();
assert(csv.startsWith('process,protocol,local,remote'));
assert.equal((await get('/v1/export?kind=bundle&format=zip')).status, 400);

// rules
const rule = await json('/v1/rules', { method: 'POST', body: JSON.stringify({ action: 'block', app: 'Slack' }) });
assert.equal(rule.action, 'block');
assert((await json('/v1/rules')).length === 1);
assert((await json('/v1/rules/' + rule.id, { method: 'DELETE' })).deleted);

// captures: confirmation required, headers-only default, valid pcap
assert.equal((await get('/v1/captures', { method: 'POST', body: JSON.stringify({ iface: 'en0' }) })).status, 400);
assert.equal((await get('/v1/captures', { method: 'POST', body: JSON.stringify({ iface: 'en0; id', confirm: true }) })).status, 400);
const cap = await json('/v1/captures', { method: 'POST', body: JSON.stringify({ iface: 'en0', host: '1.2.3.4', confirm: true }) });
assert.equal(cap.snaplen, 96);
const pcap = Buffer.from(await (await get(`/v1/captures/${cap.id}/pcap`)).arrayBuffer());
assert.equal(pcap.readUInt32LE(0), 0xA1B2C3D4);
assert.equal(pcap.readUInt32LE(16), 96);

// investigator answers and says it is simulated
assert.match((await json('/v1/query', { method: 'POST', body: JSON.stringify({ question: 'Which app uploaded the most?' }) })).answer, /simulated/);
console.log('demo shim: PASS');
