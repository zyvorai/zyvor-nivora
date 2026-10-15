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
})();
