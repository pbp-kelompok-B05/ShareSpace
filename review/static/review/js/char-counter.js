// Penghitung karakter untuk <textarea data-char-counter maxlength="..." data-min-length="...">.
// Tanpa JS, validasi panjang tetap dilakukan server; skrip ini hanya memberi umpan balik langsung.
(function () {
  function setup(field) {
    if (field.dataset.charCounterReady) return;
    field.dataset.charCounterReady = 'true';

    var max = parseInt(field.getAttribute('maxlength'), 10) || 0;
    var min = parseInt(field.dataset.minLength, 10) || 0;

    var counter = document.createElement('p');
    counter.className = 'form-help review-char-count';
    counter.id = field.id + '_counter';
    field.insertAdjacentElement('afterend', counter);

    // Dibacakan pembaca layar saat textarea difokus, tanpa diumumkan tiap ketikan.
    var describedBy = field.getAttribute('aria-describedby');
    field.setAttribute('aria-describedby', (describedBy ? describedBy + ' ' : '') + counter.id);

    function update() {
      // Server menghitung minimum setelah spasi di tepi dibuang, jadi samakan di sini.
      var meaningful = field.value.trim().length;
      var text = field.value.length + (max ? ' / ' + max : '') + ' karakter';
      var short = min > 0 && meaningful < min;
      if (short) text += ' · kurang ' + (min - meaningful) + ' lagi';
      counter.textContent = text;
      counter.classList.toggle('is-short', short);
    }

    field.addEventListener('input', update);
    update();
  }

  document.querySelectorAll('textarea[data-char-counter]').forEach(setup);
})();
