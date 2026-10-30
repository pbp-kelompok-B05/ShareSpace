// Dimuat sinkron di <head> sebelum CSS agar tema terpasang sebelum halaman digambar (tanpa kedipan).
(function () {
  var root = document.documentElement;
  var theme = null;
  root.classList.add('js');
  try {
    theme = window.localStorage.getItem('theme');
  } catch (e) {
    // localStorage bisa diblokir (mode privat, cookie dimatikan); jatuh ke preferensi sistem.
  }
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  root.classList.toggle('dark', theme === 'dark');
})();
