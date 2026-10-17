// SPDX-License-Identifier: BUSL-1.1
(function () {
  var root = document.documentElement;
  var themeBtn = document.getElementById('theme');
  function syncTheme() {
    var dark = root.getAttribute('data-theme') === 'dark';
    themeBtn.setAttribute('aria-pressed', String(dark));
    themeBtn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    pick.mode = dark ? 'dark' : 'light';
    drawShot();
  }
  themeBtn.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('nivora-theme', next); } catch (e) {}
    syncTheme();
  });

  // gallery: appearance x pane -> one of the real screenshots in ux/
  var pick = { mode: root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light', pane: 'overview' };
  var NAMES = { overview: 'Overview', flows: 'Flows', applications: 'Applications', health: 'Health', capture: 'Capture', security: 'Security', timeline: 'Time Machine', insights: 'Insights', alerts: 'Alerts', settings: 'Settings' };
  var DEMO = { alerts: 'security', timeline: 'timeline' };
  var img = document.getElementById('shot'), cap = document.getElementById('shot-cap'), demoLink = document.getElementById('shot-demo');
  function drawShot() {
    if (!img) return;
    img.src = 'ux/native-' + pick.mode + '-' + pick.pane + '.png';
    img.alt = 'Nivora ' + NAMES[pick.pane] + ' pane, ' + pick.mode + ' appearance, simulated telemetry';
    if (demoLink) demoLink.href = 'demo/#' + (DEMO[pick.pane] || pick.pane);
    cap.textContent = 'Native app · ' + pick.mode + ' · ' + NAMES[pick.pane] + ' · simulated telemetry';
    document.querySelectorAll('#panes [role=radio]').forEach(function (b) { var on = b.dataset.value === pick.pane; b.setAttribute('aria-checked', String(on)); b.setAttribute('tabindex', on ? '0' : '-1'); });
    document.querySelectorAll('#modes [role=radio]').forEach(function (b) { b.setAttribute('aria-checked', String(b.dataset.value === pick.mode)); });
  }
  document.querySelectorAll('#panes [role=radio]').forEach(function (b) {
    b.addEventListener('click', function () { pick.pane = b.dataset.value; drawShot(); });
  });
  // arrow keys move through the panes (radiogroup behaviour)
  var paneBtns = Array.prototype.slice.call(document.querySelectorAll('#panes [role=radio]'));
  paneBtns.forEach(function (b, i) {
    b.setAttribute('tabindex', b.getAttribute('aria-checked') === 'true' ? '0' : '-1');
    b.addEventListener('keydown', function (e) {
      var d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      var n = paneBtns[(i + d + paneBtns.length) % paneBtns.length];
      n.focus(); n.click();
    });
  });
  document.querySelectorAll('#modes [role=radio]').forEach(function (b) {
    b.addEventListener('click', function () { pick.mode = b.dataset.value; drawShot(); });
  });

  // highlight the section in view
  if ('IntersectionObserver' in window) {
    var links = {};
    document.querySelectorAll('#sections a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && links[e.target.id]) {
          Object.keys(links).forEach(function (k) { links[k].removeAttribute('aria-current'); });
          links[e.target.id].setAttribute('aria-current', 'true');
        }
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    Object.keys(links).forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
  }
  syncTheme();

  // scroll reveal: theme.js sets html.js, CSS hides .rv only then (and never under reduced motion)
  var rv = document.querySelectorAll('.rv');
  if ('IntersectionObserver' in window) {
    var rio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); rio.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    rv.forEach(function (el) { rio.observe(el); });
  } else {
    rv.forEach(function (el) { el.classList.add('in'); });
  }

  // sticky tour: the step in the middle of the viewport swaps the pinned stage image
  var steps = Array.prototype.slice.call(document.querySelectorAll('#tour-steps .step'));
  var stageImgs = document.querySelectorAll('#tour-stage .stage-img');
  function showStep(i) {
    steps.forEach(function (s, j) { if (j === i) s.setAttribute('aria-current', 'step'); else s.removeAttribute('aria-current'); });
    stageImgs.forEach(function (im) { im.classList.toggle('on', Number(im.dataset.step) === i); });
  }
  if (steps.length && 'IntersectionObserver' in window) {
    var sio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) showStep(Number(e.target.dataset.step)); });
    }, { rootMargin: '-45% 0px -45% 0px' });
    steps.forEach(function (s) { sio.observe(s); });
    steps.forEach(function (s) { s.addEventListener('focus', function () { showStep(Number(s.dataset.step)); }); });
    // preload the next step's image for the current theme so the swap never flashes
    steps.forEach(function (s, i) {
      s.addEventListener('mouseenter', function () { warm(i + 1); });
      s.addEventListener('focus', function () { warm(i + 1); });
    });
    var warmed = {};
    var warm = function (i) {
      if (warmed[i]) return;
      warmed[i] = 1;
      stageImgs.forEach(function (im) { if (Number(im.dataset.step) === i) im.loading = 'eager'; });
    };
    warm(1);
  }

  // terminal tabs (captured CLI output; without JS the first pane is shown)
  var term = document.getElementById('term');
  if (term) {
    term.querySelectorAll('[role=tab]').forEach(function (t) {
      t.addEventListener('click', function () {
        term.querySelectorAll('[role=tab]').forEach(function (x) { x.setAttribute('aria-selected', String(x === t)); });
        term.querySelectorAll('.term-pane').forEach(function (p) { p.hidden = p.dataset.pane !== t.dataset.tab; });
      });
    });
  }

  // command palette: sections, docs (docs/search.json) and demo panes
  var dlg = document.getElementById('palette-dialog'), pin = document.getElementById('palette-input'), pres = document.getElementById('palette-results');
  var items = null, sel = 0, shown = [];
  function base() {
    var out = [];
    [['Take the tour', '#tour'], ['Highlights', '#highlights'], ['See it', '#gallery'], ['Features', '#features'], ['What\u2019s new', '#new'], ['Install and download', '#install'], ['Verified vs not', '#verified'], ['Privacy', '#privacy'], ['FAQ', '#faq']]
      .forEach(function (x) { out.push({ label: x[0], hint: 'Section', url: x[1] }); });
    document.querySelectorAll('#features .card h3, #privacy .card h3').forEach(function (h) {
      out.push({ label: h.textContent, hint: 'Feature', url: '#' + h.closest('section').id });
    });
    ['overview', 'flows', 'applications', 'health', 'security', 'insights', 'timeline', 'capture', 'investigator', 'settings']
      .forEach(function (p) { out.push({ label: 'Demo: ' + p, hint: 'Live demo', url: 'demo/#' + p }); });
    return out;
  }
  function loadItems(cb) {
    if (items) return cb();
    items = base();
    fetch('docs/search.json').then(function (r) { return r.json(); }).then(function (j) {
      j.forEach(function (e) { items.push({ label: e.heading || e.title, hint: 'Docs · ' + e.title, url: 'docs/' + e.url }); });
    }).catch(function () {}).then(cb);
  }
  function esc(t) { return t.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function draw() {
    var q = pin.value.trim().toLowerCase(), words = q ? q.split(/\s+/) : [];
    shown = items.filter(function (it) { var h = (it.label + ' ' + it.hint).toLowerCase(); return words.every(function (w) { return h.indexOf(w) >= 0; }); }).slice(0, 10);
    sel = 0;
    pres.innerHTML = shown.map(function (it, i) {
      return '<a role="option" href="' + esc(it.url) + '" aria-selected="' + (i === 0) + '"><b>' + esc(it.label) + '</b><span>' + esc(it.hint) + '</span></a>';
    }).join('') || '<p class="muted">No matches.</p>';
  }
  function mark() { Array.prototype.forEach.call(pres.children, function (a, i) { a.setAttribute('aria-selected', String(i === sel)); }); }
  function open() {
    if (!dlg || !dlg.showModal) return;
    loadItems(function () { pin.value = ''; draw(); if (!dlg.open) dlg.showModal(); pin.focus(); });
  }
  if (dlg) {
    document.getElementById('palette').addEventListener('click', open);
    document.addEventListener('keydown', function (e) {
      var typing = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '');
      if (((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); open(); }
    });
    pin.addEventListener('input', draw);
    pin.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); mark(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); mark(); }
      else if (e.key === 'Enter' && shown[sel]) { e.preventDefault(); dlg.close(); window.location.href = shown[sel].url; }
    });
    pres.addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
  }
})();
