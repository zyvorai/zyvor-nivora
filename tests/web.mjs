// SPDX-License-Identifier: BUSL-1.1
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import * as L from '../web/lib.js';

const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const css=fs.readFileSync(new URL('../web/styles.css',import.meta.url),'utf8');
const js=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8');
const lib=fs.readFileSync(new URL('../web/lib.js',import.meta.url),'utf8');

// --- markup / wiring contract
for(const label of ['Overview','Health','Network Map','Applications','Flows','DNS','Interfaces','Routes','VPN','Local Network','FluxVM','Security','Time Machine','Investigator','Settings']){
  assert(html.includes(label), `missing nav label ${label}`);
}
for(const id of ['paletteDialog','helpDialog','sheet','toasts','exportBtn','exportDialog','exportForm','sidebarBtn','alertBadge']){
  assert(html.includes(`id="${id}"`), `missing #${id}`);
}
assert(css.includes('backdrop-filter'), 'glass UI contract missing');
assert(css.includes('prefers-reduced-motion'), 'reduced-motion rule missing');
for(const needle of ["'/v1/snapshot'","'/v1/query'","'/v1/series?limit=80'","networkMap","'/v1/rules'"]){
  assert(js.includes(needle), `app.js missing ${needle}`);
}
assert(!/\balert\(/.test(js), 'alert() must be replaced by toasts');
assert(!js.includes('localStorage.setItem(\'nivora-token'), 'token must never be persisted');
assert(!/token/i.test(lib.match(/DEFAULT_PREFS[\s\S]*?};/)[0]), 'prefs must not hold the token');
for(const tok of ['--text:#1d1d1f','--blue:#0071e3','--green:#34c759','--orange:#ff9f0a','--purple:#af52de','--red:#ff3b30','--bg:#000000','--text:#f5f5f7','--ease-apple']){
  assert(css.includes(tok), `Netra token missing: ${tok}`);
}
assert(Object.keys(L.ACCENTS).join()==='blue,cyan,green,amber,purple,graphite','accent set must match Netra accents');
new vm.SourceTextModule(js,{context:vm.createContext({console})});

// --- lib.js unit tests
assert.equal(L.fmtBytes(0),'0 B'); assert.equal(L.fmtBytes(1536),'1.5 KB'); assert.equal(L.fmtRate(1048576),'1.0 MB/s');
assert.equal(L.hostOf('1.2.3.4:443'),'1.2.3.4'); assert.equal(L.portOf('1.2.3.4:443'),'443');
assert.equal(L.hostOf('[2001:db8::1]:443'),'2001:db8::1'); assert.equal(L.portOf('[2001:db8::1]:443'),'443');
assert.equal(L.hostOf(''),'—'); assert.equal(L.portOf('2001:db8::1'),'');
assert.equal(L.esc('<a href="x">&\'</a>'),'&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
assert.equal(L.initials('Google Chrome Helper'),'GC');

const apps=[{name:'Safari',rx_bps:5,pid:1},{name:'Slack',rx_bps:9,pid:2},{name:'Mail',rx_bps:9,pid:3}];
assert.deepEqual(L.sortRows(apps,'rx_bps','desc').map(a=>a.name),['Slack','Mail','Safari'], 'desc sort must be stable');
assert.deepEqual(L.sortRows(apps,'name','asc').map(a=>a.name),['Mail','Safari','Slack']);
assert.equal(apps[0].name,'Safari','sortRows must not mutate');
assert(L.matchQuery({process:'Slack',remote:'10.0.0.5:443'},'443'));
assert(L.matchQuery({process:'Slack'},'  slack '));
assert(!L.matchQuery({process:'Slack'},'zoom'));

assert.equal(L.scoreStatus(95),'good'); assert.equal(L.scoreStatus(60),'degraded'); assert.equal(L.scoreStatus(10),'poor'); assert.equal(L.scoreStatus(undefined),'unknown');
assert.equal(L.sparklinePath([],10,10),''); assert(L.sparklinePath([5],10,10).startsWith('M0.0,')); assert.equal(L.sparklinePath([1,2,3],10,10).split('L').length,3);

const csv=L.flowsToCSV([{process:'=cmd|calc',remote:'a,"b"',protocol:'tcp'}]);
const rows=csv.trim().split('\n');
assert.equal(rows.length,2); assert(rows[1].startsWith("'=cmd|calc,"),'formula injection must be neutralised'); assert(rows[1].includes('"a,""b"""'));

assert.deepEqual(L.mergePrefs('{not json'),L.DEFAULT_PREFS);
assert.deepEqual(L.mergePrefs(null),L.DEFAULT_PREFS);
const m=L.mergePrefs({appearance:'neon',accent:'green',refreshMs:1,alertMbps:-4,pinned:['a','a',5,'b'],density:'compact'});
assert.equal(m.appearance,'auto'); assert.equal(m.accent,'green'); assert.equal(m.refreshMs,2000); assert.equal(m.alertMbps,0); assert.deepEqual(m.pinned,['a','b']); assert.equal(m.density,'compact');
assert.deepEqual(L.DEFAULT_PREFS.pinned,[],'defaults must not be mutated');

const buf={}; for(let i=0;i<100;i++)L.pushSample(buf,'x',i);
assert.equal(buf.x.length,L.SAMPLE_CAP); assert.equal(buf.x.at(-1),99);

assert.equal(L.highlight('Slack Helper','lack'),'S<mark>lack</mark> Helper');
assert.equal(L.highlight('<b>','b'),'&lt;<mark>b</mark>&gt;');

assert.deepEqual(L.rateAlerts([{name:'A',total_bps:2e6},{name:'B',total_bps:10}],8),[{app:'A',bps:2e6}]);
assert.deepEqual(L.rateAlerts([{name:'A',total_bps:2e6}],0),[]);

console.log('web contract + lib unit tests: PASS');

// --- shared filter vectors (also run by tests/test_filter.py and native XCTest)
{
  const vec = JSON.parse(fs.readFileSync(new URL('./fixtures/filter-vectors.json', import.meta.url), 'utf8'));
  for (const c of vec.cases) {
    const got = L.filterFlows(vec.flows, c.q).map(f => f.id);
    assert.deepEqual(got, c.expect, `filter vector ${JSON.stringify(c.q)}`);
  }
}

// --- saved views: validated, capped, never carry the token
{
  const p = L.mergePrefs({ views: [{ name: ' A ', query: 'port:443' }, { name: '', query: 'x' }, { name: 5, query: 'y' }, ...Array.from({ length: 30 }, (_, i) => ({ name: `v${i}`, query: 'q' }))] });
  assert.equal(p.views[0].name, 'A');
  assert(p.views.length <= 20);
  assert.equal(L.dropFilterChip('app:"Google Chrome" port:443', 0), 'port:443');
  assert.equal(L.dropFilterChip('app:"Google Chrome" port:443', 1), 'app:"Google Chrome"');
}
