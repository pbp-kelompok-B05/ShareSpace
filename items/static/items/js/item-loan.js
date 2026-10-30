// Tombol "Ajukan Peminjaman" di detail barang membuka modal form milik loans (#loan-modal).
// Submit, validasi, dan redirect ditangani loan_action.js. Delegasi di document karena tombol
// ikut terganti saat #item-detail di-swap HTMX setelah staff mengedit barang.
(function () {
  var dialog = document.getElementById('loan-modal');
  if (!dialog) return;

  document.addEventListener('click', function (event) {
    if (!event.target.closest('[data-open-loan-dialog]')) return;
    event.preventDefault();
    if (!dialog.open) dialog.showModal();
  });
})();
