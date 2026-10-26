// Link dengan data-confirm-dialog="<id>" membuka <dialog> konfirmasi di halaman yang sama.
// Tanpa JS (atau browser tanpa <dialog>), link tetap menuju halaman konfirmasi biasa.
(function () {
  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-confirm-dialog]');
    if (trigger) {
      var dialog = document.getElementById(trigger.dataset.confirmDialog);
      if (!dialog || typeof dialog.showModal !== 'function') return;
      event.preventDefault();
      dialog.showModal();
      return;
    }

    var close = event.target.closest('[data-dialog-close]');
    if (close) {
      var parent = close.closest('dialog');
      if (parent) parent.close();
    }
  });

  // Klik di luar kotak dialog (backdrop) menutupnya; Esc sudah ditangani browser.
  document.querySelectorAll('dialog.review-dialog').forEach(function (dialog) {
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });
  });
})();
