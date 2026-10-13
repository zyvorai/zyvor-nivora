// SPDX-License-Identifier: BUSL-1.1
// Pure helpers for the Nivora dashboard. No DOM access so they can be unit-tested in Node.

export const DEFAULT_PREFS = {
  appearance: 'auto', accent: 'blue', density: 'comfortable', reduceTransparency: false,
  refreshMs: 2000, alertMbps: 0, pinned: [],
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
  const p = { ...DEFAULT_PREFS, pinned: [] };
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
