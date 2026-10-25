// Toggle dark mode. Tema awal sudah dipasang oleh theme-init.js; file ini hanya mengurus interaksi.
(function () {
  var ShareSpace = (window.ShareSpace = window.ShareSpace || {});
  var root = document.documentElement;
  var STORAGE_KEY = 'theme';
  var META_COLORS = { light: '#f6f7f1', dark: '#0f1a16' };

  function current() {
    return root.classList.contains('dark') ? 'dark' : 'light';
  }

  function stored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function sync() {
    var isDark = current() === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(isDark));
    });
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', META_COLORS[current()]);
  }

  function apply(theme, persist) {
    root.classList.toggle('dark', theme === 'dark');
    if (persist) {
      try {
        window.localStorage.setItem(STORAGE_KEY, theme);
      } catch (e) {
        // Gagal menyimpan tidak fatal: tema tetap berlaku sampai halaman dimuat ulang.
      }
    }
    sync();
  }

  ShareSpace.theme = {
    get: current,
    set: function (theme) { apply(theme, true); },
    toggle: function () { apply(current() === 'dark' ? 'light' : 'dark', true); },
  };

  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-theme-toggle]')) ShareSpace.theme.toggle();
  });

  // Ikuti perubahan tema sistem selama pengguna belum memilih sendiri.
  if (window.matchMedia) {
    var query = window.matchMedia('(prefers-color-scheme: dark)');
    var onChange = function (event) {
      if (!stored()) apply(event.matches ? 'dark' : 'light', false);
    };
    if (query.addEventListener) query.addEventListener('change', onChange);
  }

  sync();
})();
