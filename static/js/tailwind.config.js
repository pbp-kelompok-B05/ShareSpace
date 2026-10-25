// Konfigurasi Tailwind Play CDN. Dimuat tepat setelah script CDN di base.html.
// Warna memakai variabel CSS dari style.css agar otomatis ikut dark mode.
// Catatan: Play CDN hanya menyediakan sampai v3.4.17 (cek pesan error di console jika versi diubah).
if (window.tailwind) tailwind.config = {
  darkMode: 'class',
  corePlugins: {
    // Reset bawaan Tailwind dan utility .container dimatikan agar style.css lama tidak rusak.
    preflight: false,
    container: false,
  },
  theme: {
    extend: {
      colors: {
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        cream: 'var(--cream)',
        line: 'var(--line)',
        surface: 'var(--surface)',
        'surface-muted': 'var(--surface-muted)',
        'on-primary': 'var(--on-primary)',
        primary: {
          DEFAULT: 'var(--green)',
          dark: 'var(--green-dark)',
        },
        accent: 'var(--lime)',
      },
      fontFamily: {
        heading: 'var(--font-heading)',
        body: 'var(--font-body)',
      },
    },
  },
};
