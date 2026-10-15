// SPDX-License-Identifier: BUSL-1.1
// Pure helpers for the Nivora dashboard. No DOM access so they can be unit-tested in Node.

export const DEFAULT_PREFS = {
  appearance: 'auto', accent: 'blue', density: 'comfortable', reduceTransparency: false,
  refreshMs: 2000, alertMbps: 0, pinned: [], views: [],
};
export const ACCENTS = { blue: '#0071e3', cyan: '#32ade6', green: '#34c759', amber: '#ff9f0a', purple: '#af52de', graphite: '#6e6e73' };
export const SAMPLE_CAP = 60;

export function esc(v) {
  return String(v ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}
export function fmtBytes(n) {
  n = Number(n || 0);
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}
export function fmtRate(n) { return `${fmtBytes(n)}/s`; }
export function hostOf(s) {
  if (!s) return '—';
  if (s.startsWith('[')) return s.slice(1, s.indexOf(']'));
  const c = (s.match(/:/g) || []).length;
  return c === 1 ? s.split(':')[0] : s;
}
export function portOf(s) {
  if (!s) return '';
  if (s.startsWith('[') && s.includes(']:')) return s.split(']:')[1];
  const c = (s.match(/:/g) || []).length;
  return c === 1 ? s.split(':')[1] : '';
}
export function initials(s) {
  return String(s || '?').split(/\s+/).map(x => x[0]).join('').slice(0, 2).toUpperCase();
}

/** Case-insensitive match over every field of a row (app, endpoint, IP, port...). */
export function matchQuery(row, q) {
  q = String(q || '').toLowerCase().trim();
  if (!q) return true;
  return JSON.stringify(row).toLowerCase().includes(q);
}

/** Stable sort; dir is 'asc' | 'desc'. Strings compare locale-aware, everything else numerically. */
export function sortRows(rows, key, dir = 'desc') {
  const sign = dir === 'asc' ? 1 : -1;
  const val = r => (typeof key === 'function' ? key(r) : r?.[key]);
  return rows.map((r, i) => [r, i]).sort((a, b) => {
    const x = val(a[0]), y = val(b[0]);
    let c;
    if (typeof x === 'string' || typeof y === 'string') c = String(x ?? '').localeCompare(String(y ?? ''));
    else c = Number(x ?? 0) - Number(y ?? 0);
    return c ? c * sign : a[1] - b[1];
  }).map(p => p[0]);
}

/** Score → semantic status colour. Observe-first: red only when genuinely poor. */
export function scoreStatus(score) {
  score = Number(score);
  if (!Number.isFinite(score)) return 'unknown';
  if (score >= 80) return 'good';
  if (score >= 50) return 'degraded';
  return 'poor';
}

/** Smooth-free polyline path for a sparkline; returns '' when there is nothing to draw. */
export function sparklinePath(values, width = 120, height = 32, max = 0) {
  const v = (values || []).map(x => Math.max(0, Number(x) || 0));
  if (!v.length) return '';
  const data = v.length > 1 ? v : [v[0], v[0]];
  const top = Math.max(max, ...data, 1);
  return data.map((y, i) => {
    const px = (i / (data.length - 1)) * width;
    const py = height - 2 - (y / top) * (height - 4);
    return `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(' ');
}

function csvCell(v) {
  const s = String(v ?? '');
  const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s; // neutralise spreadsheet formulas
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}
export function flowsToCSV(flows) {
  const cols = ['process', 'protocol', 'local', 'remote', 'state', 'interface', 'rtt_ms', 'rx_bps', 'tx_bps', 'bytes_in', 'bytes_out'];
  return [cols.join(','), ...(flows || []).map(f => cols.map(c => csvCell(f[c])).join(','))].join('\n') + '\n';
}

/** Merge untrusted stored preferences over defaults, keeping only valid values. */
export function mergePrefs(raw) {
  const p = { ...DEFAULT_PREFS, pinned: [], views: [] };
  let o = raw;
  if (typeof o === 'string') { try { o = JSON.parse(o); } catch { o = null; } }
  if (!o || typeof o !== 'object' || Array.isArray(o)) return p;
  if (['auto', 'light', 'dark'].includes(o.appearance)) p.appearance = o.appearance;
  if (o.accent in ACCENTS) p.accent = o.accent;
  if (['comfortable', 'compact'].includes(o.density)) p.density = o.density;
  if (typeof o.reduceTransparency === 'boolean') p.reduceTransparency = o.reduceTransparency;
  if ([1000, 2000, 5000].includes(o.refreshMs)) p.refreshMs = o.refreshMs;
  const a = Number(o.alertMbps);
  if (Number.isFinite(a) && a >= 0 && a <= 100000) p.alertMbps = a;
  if (Array.isArray(o.pinned)) p.pinned = [...new Set(o.pinned.filter(x => typeof x === 'string'))].slice(0, 50);
  if (Array.isArray(o.views)) {
    p.views = o.views.filter(v => v && typeof v.name === 'string' && typeof v.query === 'string' && v.name.trim())
      .map(v => ({ name: v.name.trim().slice(0, 40), query: v.query.slice(0, 200) })).slice(0, 20);
  }
  return p;
}

/** Append a value to a capped per-key ring buffer map. */
export function pushSample(buf, key, value, cap = SAMPLE_CAP) {
  const arr = buf[key] || (buf[key] = []);
  arr.push(Number(value) || 0);
  if (arr.length > cap) arr.splice(0, arr.length - cap);
  return arr;
}

/** Highlight query matches inside already-trusted plain text; output is HTML-escaped. */
export function highlight(text, q) {
  const s = String(text ?? '');
  q = String(q || '').trim();
  if (!q) return esc(s);
  const i = s.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return esc(s);
  return `${esc(s.slice(0, i))}<mark>${esc(s.slice(i, i + q.length))}</mark>${esc(s.slice(i + q.length))}`;
}

/** Throughput alerts: apps whose live total rate exceeds the threshold (Mbit/s). */
export function rateAlerts(apps, thresholdMbps) {
  if (!(thresholdMbps > 0)) return [];
  const limit = thresholdMbps * 1e6 / 8;
  return (apps || []).filter(a => (a.total_bps || (a.rx_bps || 0) + (a.tx_bps || 0)) > limit)
    .map(a => ({ app: a.name, bps: a.total_bps || (a.rx_bps || 0) + (a.tx_bps || 0) }));
}

// ---- Flow filter grammar (mirrors agent/nivora_core.py parse_filter/match_flow) ----
const FILTER_KEYS = { app: 'app', process: 'app', host: 'host', port: 'port', proto: 'proto', protocol: 'proto', iface: 'iface', interface: 'iface', state: 'state', source: 'source' };
const RATE_UNITS = { bps: 1, kbps: 1e3, mbps: 1e6, gbps: 1e9 };

function filterTokens(query) {
  const out = []; let cur = ''; let quoted = false;
  for (const ch of String(query || '')) {
    if (ch === '"') quoted = !quoted;
    else if (/\s/.test(ch) && !quoted) { if (cur) out.push(cur); cur = ''; }
    else cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

export function parseFilter(query) {
  const terms = [];
  for (const tok of filterTokens(query)) {
    const negate = '!-'.includes(tok[0]) && tok.length > 1;
    const body = negate ? tok.slice(1) : tok;
    const rate = tok.match(/^([<>])(\d+(?:\.\d+)?)(bps|kbps|mbps|gbps)$/i);
    if (rate) { terms.push({ kind: 'rate', op: rate[1], bits: parseFloat(rate[2]) * RATE_UNITS[rate[3].toLowerCase()], negate: false }); continue; }
    const i = body.indexOf(':');
    const key = i > 0 ? body.slice(0, i).toLowerCase() : '';
    const value = i > 0 ? body.slice(i + 1) : '';
    if (key in FILTER_KEYS && value) terms.push({ kind: FILTER_KEYS[key], value: value.toLowerCase(), negate });
    else terms.push({ kind: 'text', value: (tok.startsWith('!') && tok.length > 1 ? tok.slice(1) : tok).toLowerCase(), negate: tok.startsWith('!') && tok.length > 1 });
  }
  return terms;
}

function termHit(f, t) {
  const v = t.value;
  const remote = String(f.remote ?? ''), local = String(f.local ?? '');
  switch (t.kind) {
    case 'app': return String(f.process ?? '').toLowerCase().includes(v) || String(f.bundle_id ?? '').toLowerCase().includes(v);
    case 'host': return hostOf(remote).toLowerCase().includes(v);
    case 'port': {
      const [lo, hi] = v.split('-');
      const a = parseInt(lo, 10), b = parseInt(hi ?? lo, 10);
      if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
      return [portOf(remote), portOf(local)].map(Number).some(p => p && p >= a && p <= b);
    }
    case 'proto': return String(f.protocol ?? '').toLowerCase() === v;
    case 'iface': return String(f.interface ?? '').toLowerCase() === v;
    case 'state': return String(f.state ?? '').toLowerCase() === v;
    case 'source': return String(f.source ?? '').toLowerCase() === v;
    default: return JSON.stringify(f).toLowerCase().includes(v);
  }
}

export function matchFilter(f, terms) {
  const groups = {};
  for (const t of terms) {
    if (t.kind === 'rate') {
      const bits = Number(f.total_bps || 0) * 8;
      if ((t.op === '>' && !(bits > t.bits)) || (t.op === '<' && !(bits < t.bits))) return false;
    } else if (t.negate) {
      if (termHit(f, t)) return false;
    } else (groups[t.kind] ||= []).push(t);
  }
  return Object.values(groups).every(g => g.some(t => termHit(f, t)));
}

export function filterFlows(flows, query) {
  const terms = parseFilter(query);
  return terms.length ? (flows || []).filter(f => matchFilter(f, terms)) : [...(flows || [])];
}

/** Raw filter tokens (quotes stripped) for rendering removable chips. */
export function filterChips(query) { return filterTokens(query); }
/** Rebuild a query after removing chip `index`; values containing spaces are re-quoted. */
export function dropFilterChip(query, index) {
  return filterTokens(query).filter((_, i) => i !== index)
    .map(t => { const i = t.indexOf(':'); return /\s/.test(t) ? (i > 0 ? `${t.slice(0, i + 1)}"${t.slice(i + 1)}"` : `"${t}"`) : t; })
    .join(' ');
}

/** Group flows by 'app' | 'host' | 'iface' for the summary views; sorted by live rate. */
export function groupFlows(flows, by) {
  const keyOf = { app: f => f.process || 'Unknown', host: f => hostOf(f.remote), iface: f => f.interface || '—' }[by];
  if (!keyOf) return [];
  const m = new Map();
  for (const f of flows || []) {
    const k = keyOf(f);
    const g = m.get(k) || { key: k, by, count: 0, rx_bps: 0, tx_bps: 0, bytes_in: 0, bytes_out: 0 };
    g.count++; g.rx_bps += Number(f.rx_bps || 0); g.tx_bps += Number(f.tx_bps || 0);
    g.bytes_in += Number(f.bytes_in || 0); g.bytes_out += Number(f.bytes_out || 0);
    m.set(k, g);
  }
  return [...m.values()].sort((a, b) => (b.rx_bps + b.tx_bps) - (a.rx_bps + a.tx_bps) || a.key.localeCompare(b.key));
}

/** Compare two flow lists by id: what appeared, vanished, and the biggest live-rate movers. */
export function diffFlows(before, after, topN = 8) {
  const a = new Map((before || []).map(f => [f.id, f])), b = new Map((after || []).map(f => [f.id, f]));
  const added = [...b.values()].filter(f => !a.has(f.id));
  const removed = [...a.values()].filter(f => !b.has(f.id));
  const rate = f => Number(f.total_bps || 0);
  const changed = [...b.values()].filter(f => a.has(f.id)).map(f => ({ flow: f, delta: rate(f) - rate(a.get(f.id)) }))
    .filter(x => x.delta !== 0).sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta)).slice(0, topN);
  return { added, removed, changed };
}
