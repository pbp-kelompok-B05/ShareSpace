// "Barang saya": pilih semua, jumlah terpilih, dialog konfirmasi hapus, dan optimistic UI.
// Isi #my-item-list diganti HTMX setelah filter/aksi, jadi listener dipasang di document (delegasi).
(function () {
  var list = document.getElementById('my-item-list');
  if (!list) return;
  var dialog = document.getElementById('my-items-confirm');
  var pending = null; // detail event htmx:confirm yang menunggu jawaban dialog

  function selectable() {
    return list.querySelectorAll('input[name="items"][form="bulk-form"]:not(:disabled)');
  }

  function selected() {
    return list.querySelectorAll('input[name="items"][form="bulk-form"]:checked');
  }

  function refresh() {
    var total = selectable().length;
    var count = selected().length;
    var selectAll = document.getElementById('my-items-select-all');
    if (selectAll) {
      selectAll.checked = total > 0 && count === total;
      selectAll.indeterminate = count > 0 && count < total;
      selectAll.disabled = total === 0;
    }
    var label = list.querySelector('[data-selected-count]');
    if (label) {
      label.hidden = false;
      label.textContent = count ? count + ' barang dipilih' : 'Belum ada yang dipilih';
    }
    // Tanpa JS tombol tetap aktif (server menolak pilihan kosong); dengan JS dinonaktifkan sampai ada pilihan.
    var submit = list.querySelector('[data-bulk-submit]');
    if (submit) submit.disabled = count === 0;
    list.querySelectorAll('[data-item-row]').forEach(function (row) {
      row.classList.toggle('is-selected', !!row.querySelector('input[name="items"]:checked'));
    });
  }

  document.addEventListener('change', function (event) {
    var target = event.target;
    if (!list.contains(target)) return;
    if (target.id === 'my-items-select-all') {
      selectable().forEach(function (box) { box.checked = target.checked; });
    }
    if (target.id === 'my-items-select-all' || target.name === 'items') refresh();
  });

  document.addEventListener('htmx:afterSettle', function (event) {
    if (event.detail.target === list) refresh();
  });

  // Ganti confirm() bawaan browser (hx-confirm) dengan <dialog> yang ikut tema dan dark mode.
  if (dialog) {
    var text = document.getElementById('my-items-confirm-text');

    document.addEventListener('htmx:confirm', function (event) {
      var elt = event.detail.elt;
      if (!event.detail.question || !list.contains(elt)) return;
      event.preventDefault();
      text.textContent = elt.id === 'bulk-form'
        ? 'Hapus ' + selected().length + ' barang terpilih?'
        : event.detail.question;
      pending = event.detail;
      dialog.showModal();
    });

    dialog.addEventListener('click', function (event) {
      if (event.target.closest('[data-confirm-ok]')) {
        var request = pending;
        pending = null;
        dialog.close();
        if (request) request.issueRequest(true); // true: lewati confirm() bawaan
        return;
      }
      // Tombol ×/Batal, atau klik di backdrop (target-nya elemen dialog itu sendiri).
      if (event.target.closest('[data-confirm-cancel]') || event.target === dialog) {
        pending = null;
        dialog.close();
      }
    });
  }

  // Optimistic UI: baris langsung disembunyikan saat aksi dikirim; dikembalikan jika request gagal.
  function rowsFor(elt) {
    if (elt.id === 'bulk-form') {
      return Array.prototype.map.call(selected(), function (box) { return box.closest('[data-item-row]'); });
    }
    var row = elt.closest('[data-item-row]');
    return row ? [row] : [];
  }

  document.addEventListener('htmx:beforeRequest', function (event) {
    var elt = event.detail.elt;
    if (!list.contains(elt) || event.detail.requestConfig.verb !== 'post') return;
    var rows = rowsFor(elt);
    rows.forEach(function (row) { row.classList.add('is-pending'); });
    elt._pendingRows = rows;
  });

  function rollback(event) {
    var elt = event.detail.elt;
    if (!elt || !elt._pendingRows) return;
    elt._pendingRows.forEach(function (row) { row.classList.remove('is-pending'); });
    elt._pendingRows = null;
  }
  document.addEventListener('htmx:responseError', rollback);
  document.addEventListener('htmx:sendError', rollback);

  refresh();
})();
