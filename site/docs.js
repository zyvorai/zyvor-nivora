// SPDX-License-Identifier: BUSL-1.1
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('theme');
  function sync() {
    var dark = root.getAttribute('data-theme') === 'dark';
    btn.setAttribute('aria-pressed', String(dark));
    btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  }
  btn.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('nivora-theme', next); } catch (e) {}
    sync();
  });
  sync();

  // search over docs/search.json (titles and headings); no library
  var input = document.getElementById('docsearch'), box = document.getElementById('docresults'), index = null;
  function load(cb) {
    if (index) return cb();
    fetch('search.json').then(function (r) { return r.json(); }).then(function (j) { index = j; cb(); }).catch(function () { index = []; cb(); });
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function run() {
    var q = input.value.trim().toLowerCase();
    if (!q) { box.hidden = true; box.innerHTML = ''; return; }
    var words = q.split(/\s+/);
    var hits = index.filter(function (e) {
      var hay = (e.title + ' ' + e.heading).toLowerCase();
      return words.every(function (w) { return hay.indexOf(w) >= 0; });
    }).slice(0, 12);
    box.hidden = false;
    box.innerHTML = hits.length ? '<ul>' + hits.map(function (e) {
      return '<li><a href="' + esc(e.url) + '"><b>' + esc(e.heading || e.title) + '</b>' + (e.heading ? '<span>' + esc(e.title) + '</span>' : '') + '</a></li>';
    }).join('') + '</ul>' : '<p class="muted">No matches.</p>';
  }
  if (input) {
    input.addEventListener('input', function () { load(run); });
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== input && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); input.focus(); }
    });
  }
})();
