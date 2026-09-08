(() => {
  'use strict';
  const allowed = ['auto', 'dark', 'light'];
  let theme = 'auto';
  try { const saved = localStorage.getItem('trackerRadarTheme'); if (allowed.includes(saved)) theme = saved; } catch (_) {}
  document.documentElement.dataset.theme = theme;
  const media = matchMedia('(prefers-color-scheme: dark)');
  const updateColor = () => {
    const dark = theme === 'dark' || (theme === 'auto' && media.matches);
    document.querySelector('meta[name="theme-color"]').content = dark ? '#0b1920' : '#f5f8f8';
  };
  updateColor();
  media.addEventListener('change', updateColor);
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('theme');
    select.value = theme;
    select.addEventListener('change', () => {
      theme = allowed.includes(select.value) ? select.value : 'auto';
      document.documentElement.dataset.theme = theme;
      try { localStorage.setItem('trackerRadarTheme', theme); } catch (_) {}
      updateColor();
    });
  });
})();
