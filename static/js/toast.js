// Toast global: Django messages (dirender server), ShareSpace.toast() dari JS, event HTMX "showToast",
// dan pesan otomatis untuk respons error HTMX. Teks selalu lewat textContent (aman dari XSS).
(function () {
  var ShareSpace = (window.ShareSpace = window.ShareSpace || {});
  var LEVELS = { success: '✓', info: 'i', warning: '!', error: '✕' };
  // Sukses/info hilang sendiri; peringatan dan error tetap sampai ditutup agar sempat dibaca.
  var AUTO_DISMISS_MS = { success: 5000, info: 5000, warning: 0, error: 0 };
  var MAX_TOASTS = 4;
  var ERROR_MESSAGES = {
    403: 'Kamu tidak punya akses untuk melakukan aksi ini.',
    404: 'Data yang diminta tidak ditemukan.',
    429: 'Terlalu banyak permintaan. Coba lagi sebentar lagi.',
  };

  function region() {
    return document.getElementById('toast-region');
  }

  function dismiss(toast) {
    if (!toast || toast.classList.contains('is-leaving')) return;
    clearTimeout(toast._timer);
    toast.classList.add('is-leaving');
    // Hapus lewat timeout, bukan transitionend, agar tetap jalan saat transisi dimatikan (reduced motion).
    setTimeout(function () { toast.remove(); }, 200);
  }

  function schedule(toast, level) {
    var delay = AUTO_DISMISS_MS[level] || 0;
    if (!delay) return;
    var start = function () { toast._timer = setTimeout(function () { dismiss(toast); }, delay); };
    var stop = function () { clearTimeout(toast._timer); };
    // Jeda saat disorot atau difokus keyboard.
    toast.addEventListener('mouseenter', stop);
    toast.addEventListener('mouseleave', start);
    toast.addEventListener('focusin', stop);
    toast.addEventListener('focusout', start);
    start();
  }

  function levelOf(toast) {
    for (var level in LEVELS) {
      if (toast.classList.contains('toast-' + level)) return level;
    }
    return 'info';
  }

  function init(scope) {
    (scope || document).querySelectorAll('[data-toast]:not([data-toast-ready])').forEach(function (toast) {
      toast.setAttribute('data-toast-ready', '');
      schedule(toast, levelOf(toast));
    });
  }

  function trim() {
    var toasts = region().querySelectorAll('[data-toast]:not(.is-leaving)');
    for (var i = 0; i < toasts.length - MAX_TOASTS; i++) dismiss(toasts[i]);
  }

  ShareSpace.toast = function (message, level) {
    var target = region();
    if (!target || !message) return null;
    level = LEVELS[level] ? level : 'info';

    var existing = target.querySelectorAll('[data-toast]:not(.is-leaving) .toast-text');
    for (var i = 0; i < existing.length; i++) {
      if (existing[i].textContent === String(message)) return null;
    }

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + level;
    toast.setAttribute('data-toast', '');

    var icon = document.createElement('span');
    icon.className = 'toast-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = LEVELS[level];

    var text = document.createElement('p');
    text.className = 'toast-text';
    text.textContent = String(message);

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('data-toast-close', '');
    close.setAttribute('aria-label', 'Tutup notifikasi');
    close.textContent = '×';

    toast.append(icon, text, close);
    target.appendChild(toast);
    init(target);
    trim();
    return toast;
  };

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-toast-close]');
    if (button) dismiss(button.closest('[data-toast]'));
  });

  // Server bisa memicu toast lewat header: HX-Trigger: {"showToast": {"message": "...", "level": "success"}}
  // atau bentuk singkat: HX-Trigger: {"showToast": "Pesan"}.
  document.addEventListener('showToast', function (event) {
    var detail = event.detail || {};
    ShareSpace.toast(detail.message || detail.value, detail.level);
  });

  // HTMX tidak men-swap respons 4xx/5xx secara default; beri tahu pengguna lewat toast.
  document.addEventListener('htmx:responseError', function (event) {
    var xhr = event.detail.xhr;
    var trigger = xhr.getResponseHeader('HX-Trigger') || '';
    if (trigger.indexOf('showToast') !== -1) return; // server sudah mengirim pesan spesifik
    var message = ERROR_MESSAGES[xhr.status] ||
      (xhr.status >= 500 ? 'Terjadi kesalahan di server. Coba lagi nanti.' : 'Permintaan gagal diproses (' + xhr.status + ').');
    ShareSpace.toast(message, 'error');
  });

  document.addEventListener('htmx:sendError', function () {
    ShareSpace.toast('Gagal terhubung ke server. Periksa koneksi internetmu.', 'error');
  });

  // Toast yang masuk lewat swap HTMX (mis. hx-swap-oob) ikut diinisialisasi.
  document.addEventListener('htmx:load', function (event) { init(event.target); });

  // Live region hanya mengumumkan perubahan, bukan isi awal. Toast dari server dilepas lalu
  // dipasang lagi sesaat setelah load agar ikut dibacakan pembaca layar.
  var target = region();
  if (target) {
    var initial = Array.prototype.slice.call(target.querySelectorAll('[data-toast]'));
    initial.forEach(function (toast) { toast.remove(); });
    setTimeout(function () {
      initial.forEach(function (toast) { target.appendChild(toast); });
      init(target);
    }, 150);
  }
})();
