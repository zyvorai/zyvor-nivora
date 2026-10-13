// SPDX-License-Identifier: BUSL-1.1
// Runs before first paint: apply the saved (or system) theme so there is no flash.
(function () {
  var t = null;
  try { t = localStorage.getItem('nivora-theme'); } catch (e) {}
  if (t !== 'light' && t !== 'dark') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
})();
