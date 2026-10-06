/* Shared appearance for the shell and embedded creative tools. */
(function () {
  'use strict';
  function readTheme() {
    try { return localStorage.getItem('wx_theme') === 'light' ? 'light' : 'dark'; }
    catch (_) { return 'dark'; }
  }
  function apply(theme) {
    theme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('.theme-card').forEach(function (card, index) {
      var selected = index === (theme === 'light' ? 1 : 0);
      card.classList.toggle('is-selected', selected);
      var label = card.querySelector('div:last-child');
      if (label) label.textContent = selected ? '当前使用中' : '点击切换';
    });
  }
  window.WXTheme = { apply: apply, read: readTheme };
  apply(readTheme());
  document.addEventListener('DOMContentLoaded', function () { apply(readTheme()); });
  window.addEventListener('storage', function (event) {
    if (event.key === 'wx_theme') apply(readTheme());
  });
})();
