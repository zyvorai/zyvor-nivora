// SPDX-License-Identifier: BUSL-1.1
// Static, in-browser demo: answers the dashboard's /v1/* calls from simulated telemetry so the real UI
// runs on GitHub Pages (or `?demo`) with no collector. Nothing is read from your Mac and nothing leaves the page.
// The base snapshot (web/demo-snapshot.json) is produced by `agent/nivora.py --demo --once`.
(() => {
  const on = document.documentElement.hasAttribute('data-demo') || /[?&]demo(\b|=)/.test(location.search);
  if (!on) return;
  const realFetch = window.fetch.bind(window);
  const T0 = Date.now() / 1000;
  const here = new URL('.', document.currentScript ? document.currentScript.src : location.href);
  let basePromise = null;
  const base = () => basePromise ||= realFetch(new URL('demo-snapshot.json', here)).then(r => r.json());

  // ---- simulated flows: same shape as the collector, rates breathe, counters advance ----
  const SEED = [
    ['f1', 'Google Chrome', 510, 'com.google.Chrome', 'tcp', '192.168.1.42:53001', '142.250.183.14:443', 'en0', 31.2, 1.8e6, 9e4, 734003200, 31457280],
    ['f2', 'Slack', 602, 'com.tinyspeck.slackmacgap', 'tcp', '192.168.1.42:53102', '13.107.6.175:443', 'utun4', 181, 1.25e5, 1.8e4, 98566144, 12582912],
    ['f3', 'Xcode', 711, 'com.apple.dt.Xcode', 'tcp', '192.168.1.42:53200', 'github.com:443', 'en0', 36, 2.45e5, 5.3e5, 67108864, 83886080],
    ['f4', 'fluxvm-vz-runner', 889, 'dev.zyvor.fluxvm', 'tcp', '10.0.2.15:40544', 'github.com:443', 'vmnet8', 42, 9.2e4, 2.2e4, 52428800, 10485760],
    ['f5', 'Safari', 420, 'com.apple.Safari', 'tcp', '192.168.1.42:53310', '17.253.144.10:443', 'en0', 24, 6.4e5, 4.2e4, 210000000, 8400000],
    ['f6', 'Mail', 455, 'com.apple.mail', 'tcp', '192.168.1.42:53311', '17.57.144.52:993', 'en0', 48, 3.1e4, 6e3, 9000000, 1200000],
    ['f7', 'Dropbox', 690, 'com.getdropbox.dropbox', 'tcp', '192.168.1.42:53390', '162.125.1.18:443', 'en0', 55, 1.1e5, 3.4e5, 41000000, 160000000],
    ['f8', 'mDNSResponder', 118, '', 'udp', '192.168.1.42:5353', '224.0.0.251:5353', 'en0', 0, 1.2e3, 9e2, 220000, 140000],
  ];
  const first = new Date().toISOString();
  const flowsAt = (t) => SEED.map(([id, process, pid, bundle_id, protocol, local, remote, iface, rtt, rx, tx, bin, bout], i) => {
    const k = Math.max(0.05, 1 + 0.55 * Math.sin(t / 9 + i * 1.7) + 0.2 * Math.sin(t / 3.1 + i));
    const rx_bps = Math.round(rx * k), tx_bps = Math.round(tx * k), age = t - T0;
    return { id, process, pid, bundle_id, protocol, local, remote, state: protocol === 'tcp' ? 'ESTABLISHED' : '', interface: iface,
      rtt_ms: rtt, source: 'demo', rx_bps, tx_bps, total_bps: rx_bps + tx_bps,
      bytes_in: Math.round(bin + rx * age), bytes_out: Math.round(bout + tx * age), first_seen: first, last_seen: new Date(t * 1000).toISOString() };
  });
  const aggregate = (flows) => {
    const m = new Map();
    for (const f of flows) {
      const a = m.get(f.process) || { name: f.process, pid: f.pid, bundle_id: f.bundle_id, connections: 0, bytes_in: 0, bytes_out: 0, rx_bps: 0, tx_bps: 0, total_bps: 0, domains: [], interfaces: [] };
      a.connections++; a.bytes_in += f.bytes_in; a.bytes_out += f.bytes_out; a.rx_bps += f.rx_bps; a.tx_bps += f.tx_bps; a.total_bps += f.total_bps;
      const host = f.remote.replace(/:\d+$/, '');
      if (!a.domains.includes(host)) a.domains.push(host);
      if (!a.interfaces.includes(f.interface)) a.interfaces.push(f.interface);
      m.set(f.process, a);
    }
    return [...m.values()].sort((x, y) => y.total_bps - x.total_bps);
  };
  const traffic = (flows) => {
    const rx = flows.reduce((s, f) => s + f.rx_bps, 0), tx = flows.reduce((s, f) => s + f.tx_bps, 0);
    return { rx_bps: rx, tx_bps: tx, total_bps: rx + tx, active_flows: flows.length, internet_flows: flows.length, vpn_flows: flows.filter(f => f.interface.startsWith('utun')).length, top_interface: 'en0' };
  };
  const snapshot = async (t = Date.now() / 1000) => {
    const b = JSON.parse(JSON.stringify(await base()));
    const flows = flowsAt(t);
    b.timestamp = new Date(t * 1000).toISOString();
    b.flows = flows; b.apps = aggregate(flows); b.traffic = traffic(flows);
    b.rules = rules; b.rule_hits = [];
    b.capabilities = { ...(b.capabilities || {}), capture: true };
    return b;
  };

  // ---- in-memory state ----
  const PROFILES = [
    { name: 'default', label: 'Default', about: 'Standard thresholds.' },
    { name: 'coding', label: 'Coding', about: 'Builds, pulls and container traffic are expected; only very high rates are flagged.' },
    { name: 'presenting', label: 'Presenting', about: 'Hides informational findings.' },
    { name: 'travel', label: 'Travel / hotspot', about: 'Lower rate threshold and half the daily budgets.' },
  ];
  let demoProfile = 'default';
  const rules = [];
  const captures = new Map();
  const hexId = () => [...crypto.getRandomValues(new Uint8Array(8))].map(x => x.toString(16).padStart(2, '0')).join('');
  const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });
  const err = (msg, status = 400) => json({ error: msg }, status);

  const pcap = (snaplen = 96, count = 48) => {
    const hdr = new Uint8Array(24), v = new DataView(hdr.buffer);
    v.setUint32(0, 0xA1B2C3D4, true); v.setUint16(4, 2, true); v.setUint16(6, 4, true); v.setUint32(16, snaplen, true); v.setUint32(20, 1, true);
    const parts = [hdr], now = Math.floor(Date.now() / 1000);
    for (let i = 0; i < count; i++) {
      const frame = new Uint8Array(54), f = new DataView(frame.buffer);
      frame.set([0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0x01, 0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x08, 0x00]);
      f.setUint8(14, 0x45); f.setUint16(16, 40); f.setUint16(18, 0x1000 + i); f.setUint8(22, 64); f.setUint8(23, 6);
      frame.set([192, 168, 1, 42], 26); frame.set([142, 250, 183, 14], 30);
      f.setUint16(34, 53001); f.setUint16(36, 443); f.setUint32(38, 1000 + i * 100); f.setUint32(42, 5000 + i * 50); f.setUint8(46, 0x50); f.setUint8(47, 0x18); f.setUint16(48, 65535);
      const rec = new Uint8Array(16), r = new DataView(rec.buffer);
      r.setUint32(0, now + Math.floor(i / 20), true); r.setUint32(4, (i % 20) * 50000, true); r.setUint32(8, frame.length, true); r.setUint32(12, frame.length, true);
      parts.push(rec, frame);
    }
    return new Blob(parts, { type: 'application/vnd.tcpdump.pcap' });
  };

  const csvCell = (v) => { const s = String(v ?? ''); const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s; return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe; };
  const COLS = { flows: ['process', 'protocol', 'local', 'remote', 'state', 'interface', 'rtt_ms', 'rx_bps', 'tx_bps', 'bytes_in', 'bytes_out'],
    apps: ['name', 'pid', 'bundle_id', 'connections', 'rx_bps', 'tx_bps', 'bytes_in', 'bytes_out', 'domains'], timeline: ['ts', 'kind', 'title', 'detail'] };

  const answer = (q, apps) => {
    const s = q.toLowerCase(), top = (k) => [...apps].sort((a, b) => b[k] - a[k])[0];
    if (/upload|sent|sending/.test(s)) return `${top('tx_bps').name} is uploading the most right now (simulated).`;
    if (/download|received|bandwidth|fastest/.test(s)) return `${top('rx_bps').name} is downloading the most right now (simulated).`;
    if (/443|port/.test(s)) return 'Port 443 is used by Google Chrome, Slack, Xcode, Safari and Dropbox in this simulated sample.';
    if (/vpn/.test(s)) return 'Zyvor WireGuard is active (simulated). Slack traffic leaves through utun4.';
    if (/dns/.test(s)) return 'Resolvers 1.1.1.1 and 2606:4700:4700::1111 are active (simulated).';
    if (/slow|latency|rtt/.test(s)) return 'Slack has the highest round-trip time (about 181 ms) because it goes through the VPN tunnel (simulated).';
    if (/suspic|unusual|risk/.test(s)) return 'One simulated finding: AirPlayXPCHelper listens on all interfaces (port 7000). Nothing else stands out.';
    return 'This is simulated telemetry. Try: "Which app uploaded the most?", "What uses port 443?" or "Is my VPN active?"';
  };

  async function route(url, init = {}) {
    const u = new URL(url, location.href), path = u.pathname.replace(/^.*?(\/v1\/)/, '/v1/'), q = u.searchParams;
    const method = (init.method || 'GET').toUpperCase();
    const body = init.body ? JSON.parse(init.body) : {};
    if (path === '/v1/snapshot') return json(await snapshot());
    if (path === '/v1/flows') {
      const { filterFlows } = await import(new URL('lib.js', here));
      return json(filterFlows((await snapshot()).flows, q.get('filter') || ''));
    }
    if (path === '/v1/series' || path === '/v1/history') {
      const n = Math.min(300, Number(q.get('limit')) || 80), t = Date.now() / 1000, rows = [];
      for (let i = n - 1; i >= 0; i--) {
        const fl = flowsAt(t - i * 2), tr = traffic(fl);
        rows.push({ timestamp: new Date((t - i * 2) * 1000).toISOString(), rx_bps: tr.rx_bps, tx_bps: tr.tx_bps, health: 98, flows: fl.length, apps: aggregate(fl).length });
      }
      return json(rows);
    }
    if (path === '/v1/timeline') {
      const ago = (m) => new Date(Date.now() - m * 60e3).toISOString();
      return json([
        { ts: ago(190), kind: 'interface', title: 'Interface en0 appeared', detail: 'active' },
        { ts: ago(142), kind: 'dns', title: 'DNS resolver changed', detail: "('192.168.1.1',) → ('1.1.1.1', '2606:4700:4700::1111')" },
        { ts: ago(97), kind: 'vpn', title: 'VPN state changed', detail: 'Active: Zyvor WireGuard' },
        { ts: ago(64), kind: 'listener', title: 'New listening service on port 7000', detail: 'AirPlayXPCHelper · TCP · all' },
        { ts: ago(23), kind: 'traffic', title: 'Traffic rate spiked', detail: '0.4 → 3.1 MB/s' },
        { ts: new Date(T0 * 1000).toISOString(), kind: 'startup', title: 'Nivora started observing', detail: 'Simulated telemetry.' },
      ]);
    }
    if (path === '/v1/query' && method === 'POST') return json({ answer: answer(String(body.question || ''), aggregate(flowsAt(Date.now() / 1000))) });
    if (path === '/v1/rules') {
      if (method === 'POST') {
        const action = ['observe', 'allow', 'block', 'shadow'].includes(body.action) ? body.action : 'observe';
        const rule = { id: hexId(), action, app: body.app || null, domain: body.domain || null, ip: body.ip || null, port: body.port || null,
          expires_at: action === 'block' ? new Date(Date.now() + 3600e3).toISOString() : null, created_at: new Date().toISOString() };
        rules.push(rule); return json(rule, 201);
      }
      return json(rules);
    }
    const rm = path.match(/^\/v1\/rules\/([0-9a-f]+)$/);
    if (rm && method === 'DELETE') { const i = rules.findIndex(r => r.id === rm[1]); if (i < 0) return err('not found', 404); rules.splice(i, 1); return json({ deleted: true }); }

    if (path === '/v1/captures' && method === 'GET') {
      const now = Date.now();
      const sessions = [...captures.values()].map(c => { if (c.state === 'running' && now - c.t0 > Math.min(c.seconds, 3) * 1000) c.state = 'finished'; return { id: c.id, iface: c.iface, filter: c.filter, snaplen: c.snaplen, started: c.started, seconds: c.seconds, max_bytes: 16777216, state: c.state, bytes: 4096 + c.snaplen * 48 }; });
      return json({ available: true, demo: true, limits: { max_seconds: 300, max_mb: 64, max_snaplen: 256 }, sessions });
    }
    if (path === '/v1/captures' && method === 'POST') {
      if (body.confirm !== true) return err('confirmation required: capture records packet headers of this traffic');
      if (!/^[a-z]{1,12}[0-9]{1,4}$/.test(String(body.iface || ''))) return err('interface name is not valid');
      const id = hexId(), snaplen = Math.min(256, Math.max(54, Number(body.snaplen) || 96));
      const filter = [body.host && `host ${body.host}`, body.proto && body.proto !== 'any' && body.proto, body.port && `port ${body.port}`].filter(Boolean).join(' ') || 'all traffic';
      const c = { id, iface: body.iface, filter, snaplen, seconds: Math.min(300, Number(body.seconds) || 60), started: new Date().toISOString(), state: 'running', t0: Date.now() };
      captures.set(id, c); return json(c, 201);
    }
    const cm = path.match(/^\/v1\/captures\/([0-9a-f]{16})(\/(pcap|stop))?$/);
    if (cm) {
      const c = captures.get(cm[1]); if (!c) return err('no such capture', 404);
      if (cm[3] === 'pcap') return new Response(pcap(c.snaplen), { headers: { 'Content-Type': 'application/vnd.tcpdump.pcap', 'Content-Disposition': `attachment; filename="nivora-${c.id}.pcap"` } });
      if (cm[3] === 'stop') { c.state = 'stopped'; return json({ stopped: true }); }
      if (method === 'DELETE') { captures.delete(c.id); return json({ deleted: true }); }
    }
    if (path === '/v1/export') {
      const kind = q.get('kind') || 'flows', fmt = q.get('format') || 'csv', snap = await snapshot();
      if (kind === 'bundle' || fmt === 'zip') return err('the .zip bundle is available with a real collector, not in the static demo');
      let rows = kind === 'apps' ? snap.apps : kind === 'timeline' ? await (await route('/v1/timeline')).json() : snap.flows;
      if (kind === 'flows' && q.get('filter')) { const { filterFlows } = await import(new URL('lib.js', here)); rows = filterFlows(rows, q.get('filter')); }
      if (kind === 'snapshot') return new Response(JSON.stringify(snap, null, 2), { headers: { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="nivora-snapshot.json"' } });
      const name = `nivora-${kind}.${fmt}`, hdr = (type) => ({ 'Content-Type': type, 'Content-Disposition': `attachment; filename="${name}"` });
      if (fmt === 'json') return new Response(JSON.stringify(rows, null, 2), { headers: hdr('application/json') });
      if (fmt === 'ndjson') return new Response(rows.map(r => JSON.stringify(r)).join('\n') + '\n', { headers: hdr('application/x-ndjson') });
      const cols = COLS[kind] || COLS.flows;
      return new Response([cols.join(','), ...rows.map(r => cols.map(c => csvCell(Array.isArray(r[c]) ? r[c].join('; ') : r[c])).join(','))].join('\n') + '\n', { headers: hdr('text/csv') });
    }

    // ---- additions since 0.5: all simulated, none of it reads or probes anything ----
    const xm = path.match(/^\/v1\/flows\/([^/]+)\/explain$/);
    if (xm) {
      const flows = flowsAt(Date.now() / 1000), f = flows.find(x => x.id === decodeURIComponent(xm[1]));
      if (!f) return err('no such flow', 404);
      const host = f.remote.replace(/:\d+$/, ''), port = Number(f.remote.split(':').pop()) || 0;
      const total = flows.reduce((n, x) => n + x.total_bps, 0) || 1, share = Math.round(1000 * f.total_bps / total) / 10;
      const reasons = [`${f.process} (pid ${f.pid}) opened a ${f.protocol} connection to ${host}:${port}.`,
        `It leaves via ${f.interface}${f.interface.startsWith('utun') ? ', a tunnel interface.' : '.'}`];
      if (share >= 1) reasons.push(`It accounts for ${share}% of current traffic.`);
      const hit = rules.filter(r => (r.app && f.process.toLowerCase().includes(String(r.app).toLowerCase())) || (r.domain && host.endsWith(r.domain)) || (r.ip && r.ip === host));
      hit.forEach(r => reasons.push(`Rule ${r.id} (${r.action}) matches this flow.`));
      return json({ simulated: true, flow: f, app: f.process, destination: { host, port }, path: { interface: f.interface, vpn_active: f.interface.startsWith('utun') ? ['Zyvor WireGuard'] : [] },
        traffic_share_percent: share, new_destination: false, rules: hit.map(r => ({ rule_id: r.id, action: r.action, flow_id: f.id })), findings: [], reasons });
    }
    if (path === '/v1/profiles') {
      if (method === 'POST') {
        if (!PROFILES.some(p => p.name === body.name)) return err('unknown profile');
        demoProfile = body.name; return json({ active: demoProfile });
      }
      return json({ active: demoProfile, profiles: PROFILES });
    }
    if (path === '/v1/fleet') {
      return json([
        { host: 'zyvor-mac-studio', simulated: true, health: { score: 97, status: 'healthy' }, traffic: { rx_bps: 2.1e6, tx_bps: 4e5 }, counts: { apps: 8, flows: 8, findings: 1, listeners: 6 }, age_seconds: 4, stale: false },
        { host: 'build-mini-02', simulated: true, health: { score: 84, status: 'good' }, traffic: { rx_bps: 9e5, tx_bps: 3.2e6 }, counts: { apps: 5, flows: 11, findings: 2, listeners: 9 }, age_seconds: 9, stale: false },
      ]);
    }
    if (path === '/v1/path-check' && method === 'POST') {
      const host = String(body.host || '').trim().toLowerCase();
      if (!/^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$/.test(host)) return err('host must be a hostname or IP address');
      const port = Number(body.port) || 443;
      if (!(port >= 1 && port <= 65535)) return err('port must be 1..65535');
      const stages = [{ stage: 'dns', ok: true, ms: 14.2, addresses: ['203.0.113.10'] }, { stage: 'tcp', ok: true, ms: 21.7, address: '203.0.113.10' },
        { stage: 'tls', ok: true, ms: 38.4, version: 'TLSv1.3', days_left: 61 }];
      return json({ simulated: true, host, port, ok: true, stages, summary: 'Simulated result (no connection was made): dns 14.2 ms, tcp 21.7 ms, tls 38.4 ms.' });
    }
    if (path === '/v1/diff' || path === '/v1/incident') {
      const t = Date.now() / 1000, a = aggregate(flowsAt(t - 1800)), b = aggregate(flowsAt(t));
      const was = new Map(a.map(x => [x.name, x.total_bps]));
      const movers = b.map(x => ({ app: x.name, before_bps: Math.round(was.get(x.name) || 0), after_bps: Math.round(x.total_bps), delta_bps: Math.round(x.total_bps - (was.get(x.name) || 0)) }))
        .sort((m, n) => Math.abs(n.delta_bps) - Math.abs(m.delta_bps)).slice(0, 5);
      const diff = { simulated: true, from: new Date((t - 1800) * 1000).toISOString(), to: new Date(t * 1000).toISOString(),
        health: { before: 96, after: 97, delta: 1 }, flows_added: [{ app: 'Dropbox', remote: '162.125.1.18' }], flows_removed: [], app_movers: movers,
        listeners_added: [], listeners_removed: [], dns: { added: [], removed: [] }, default_route_changed: false, devices_added: [], devices_removed: [], findings_new: [] };
      if (path === '/v1/diff') return json(diff);
      return json({ simulated: true, window: { from: diff.from, to: diff.to }, headline: 'Simulated: health stayed at 97; 1 flow group appeared, 0 ended, 2 events recorded.',
        steps: [{ ts: diff.from, kind: 'vpn', text: 'VPN state changed: Active: Zyvor WireGuard' }, { ts: diff.to, kind: 'traffic', text: `${movers[0].app} moved ${(movers[0].delta_bps / 1048576).toFixed(2)} MB/s over the window.` }], diff });
    }
    if (path === '/v1/policy' && method === 'POST') {
      const pol = body.policy || {};
      if (!pol.name || !Array.isArray(pol.rules)) return err('policy needs a name and rules');
      return json({ simulated: true, dry_run: true, name: pol.name, add: pol.rules.map(r => ({ ...r, note: `policy:${pol.name}` })), remove: [], unchanged: [] });
    }
    if (path === '/v1/rule-impact') {
      const flows = flowsAt(Date.now() / 1000);
      return json(rules.map(r => {
        const m = flows.filter(f => (!r.app || f.process.toLowerCase().includes(String(r.app).toLowerCase())) && (!r.domain || f.remote.includes(r.domain)) && (!r.ip || f.remote.startsWith(r.ip)));
        return { rule_id: r.id, action: r.action, enforced: false, would_block: ['block', 'shadow'].includes(r.action), flows: m.length, apps: [...new Set(m.map(f => f.process))], bytes: m.reduce((n, f) => n + f.bytes_in + f.bytes_out, 0), bps: m.reduce((n, f) => n + f.total_bps, 0) };
      }));
    }
    for (const key of ['trust', 'privacy', 'egress']) {
      if (path === '/v1/' + (key === 'privacy' ? 'privacy-report' : key)) return json((await snapshot())[key] ?? (key === 'trust' ? [] : {}));
    }
    return err('not found', 404);
  }

  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    return /\/v1\//.test(url) ? route(url, init || {}) : realFetch(input, init);
  };

  // ---- banner: this is simulated ----
  const banner = document.createElement('div');
  banner.className = 'demo-banner';
  banner.setAttribute('role', 'status');
  banner.innerHTML = '<b>Live demo</b> · simulated telemetry, nothing leaves this page · <a href="https://github.com/zyvorai/zyvor-nivora">Get Nivora</a>';
  document.addEventListener('DOMContentLoaded', () => document.body.prepend(banner));
})();
