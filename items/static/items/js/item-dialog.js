// Dialog aksi barang di halaman detail. Isi dialog dimuat HTMX (hx-get) ke #item-dialog-body;
// dialog dibuka setelah isinya masuk dan ditutup lewat event server "closeItemDialog".
(function () {
  var dialog = document.getElementById('item-dialog');
  if (!dialog) return;
  var body = document.getElementById('item-dialog-body');
  var refocusOpener = false;

  function close() {
    if (dialog.open) dialog.close();
  }

  // Dibuka hanya setelah isi baru masuk, jadi isi lama tidak pernah tampil sekilas.
  document.addEventListener('htmx:afterSwap', function (event) {
    if (event.detail.target === body && !dialog.open) dialog.showModal();
  });

  // Dikirim server lewat HX-Trigger setelah perubahan berhasil disimpan; #item-detail lalu di-swap.
  document.addEventListener('closeItemDialog', function () {
    refocusOpener = true;
    close();
  });

  // Tombol pembuka ikut terganti saat swap, jadi fokus dikembalikan ke tombol yang baru.
  document.addEventListener('htmx:afterSettle', function () {
    if (!refocusOpener) return;
    refocusOpener = false;
    var opener = document.querySelector('#item-detail [hx-target="#item-dialog-body"]');
    if (opener) opener.focus();
  });

  // Toast ada di bawah dialog modal (top layer) dan halaman lain inert; tutup dialog saat request
  // dari dalamnya gagal (403 barang dipinjam, 429, 5xx, koneksi putus) agar pesan error terbaca.
  function closeOnError(event) {
    if (dialog.contains(event.detail.elt)) close();
  }
  document.addEventListener('htmx:responseError', closeOnError);
  document.addEventListener('htmx:sendError', closeOnError);

  dialog.addEventListener('click', function (event) {
    // Tombol × dan link Batal: tutup dialog, bukan pindah halaman.
    if (event.target.closest('[data-dialog-close]')) {
      event.preventDefault();
      close();
      return;
    }
    // Klik di backdrop: target-nya elemen dialog itu sendiri (isi dialog ada di dalam .item-dialog-body).
    if (event.target === dialog) close();
  });
})();
