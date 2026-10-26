// Navbar: buka/tutup menu mobile (hamburger) dan tutup menu akun (<details>) dengan Esc atau klik di luar.
(function () {
  var toggle = document.querySelector('[data-nav-toggle]');
  var menu = document.getElementById('site-menu');
  var userMenu = document.querySelector('[data-user-menu]');

  function setMenu(open) {
    if (!toggle || !menu) return;
    menu.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Tutup menu navigasi' : 'Buka menu navigasi');
  }

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      setMenu(toggle.getAttribute('aria-expanded') !== 'true');
    });
    // Klik link anchor di dalam menu (mis. #cara-kerja) menutup panel.
    menu.addEventListener('click', function (event) {
      if (event.target.closest('a')) setMenu(false);
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    if (userMenu && userMenu.open) {
      userMenu.open = false;
      userMenu.querySelector('summary').focus();
    } else if (toggle && toggle.getAttribute('aria-expanded') === 'true') {
      setMenu(false);
      toggle.focus();
    }
  });

  document.addEventListener('click', function (event) {
    if (userMenu && userMenu.open && !userMenu.contains(event.target)) userMenu.open = false;
  });
})();
