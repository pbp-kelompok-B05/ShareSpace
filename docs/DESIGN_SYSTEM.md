# Design System ShareSpace

Panduan singkat memakai base template dan komponen bersama. Tujuannya: semua modul terlihat konsisten, otomatis mendukung dark mode, responsif, dan aksesibel tanpa tiap anggota menulis ulang CSS/JS.

Penanggung jawab: Matthew (Modul 2 + base template). Pertanyaan atau usulan komponen baru: kabari di grup sebelum menambah CSS global.

## Aturan utama

1. **Extend `base.html`** di setiap halaman. Jangan menulis `<html>`, `<head>`, navbar, atau footer sendiri.
2. **Pakai token warna**, jangan hex hardcoded. Token otomatis berganti saat dark mode.
3. **Pakai komponen bersama** (button, card, badge, form field, empty state, pagination, toast) sebelum membuat yang baru.
4. **Tanpa `<script>` inline.** Taruh JS modul di `static/js/` (atau `static/<app>/js/`) lalu muat lewat `{% block extra_js %}`.
5. **Jangan pakai `|safe`** pada data dari pengguna. Django sudah meng-escape otomatis.
6. **Tolak akses dengan `raise PermissionDenied("pesan jelas")`**, bukan `HttpResponseForbidden()`, agar halaman 403 bersama dan toast HTMX dipakai.

## Struktur base template

```django
{% extends "base.html" %}
{% load static %}

{% block title %}Katalog — ShareSpace{% endblock %}

{% block extra_head %}
<link rel="stylesheet" href="{% static 'items/css/katalog.css' %}">  {# opsional #}
{% endblock %}

{% block content %}
<section class="container py-10">...</section>
{% endblock %}

{% block extra_js %}
<script defer src="{% static 'items/js/katalog.js' %}"></script>
{% endblock %}
```

| Block | Isi |
|---|---|
| `title` | Judul tab: `Nama halaman — ShareSpace` |
| `extra_head` | CSS tambahan modul |
| `messages` | Toast Django messages (sudah otomatis; override **hanya** jika halaman merender messages sendiri) |
| `content` | Isi halaman, dirender di dalam `<main id="konten">` |
| `extra_js` | Script modul (pakai `defer`) |

Sudah dimuat global oleh `base.html`: `style.css`, Tailwind Play CDN v3.4.17, HTMX 2.0.11, `theme.js`, `nav.js`, `toast.js`, dan header CSRF untuk HTMX.

File terkait:

- `templates/partials/header.html`: navbar global
- `templates/partials/footer.html`: footer
- `templates/partials/messages.html`, `pagination.html`, `form_field.html`, `empty_state.html`: komponen
- `templates/403.html`, `templates/404.html`: halaman error bersama
- `static/css/style.css`: token + komponen (bagian "Design system global" ke bawah)
- `static/js/`: `theme-init.js`, `theme.js`, `nav.js`, `toast.js`, `tailwind.config.js`

## Token warna

| Variabel CSS | Class Tailwind | Dipakai untuk |
|---|---|---|
| `--ink` | `text-ink` | Teks utama |
| `--muted` | `text-muted` | Teks sekunder, meta |
| `--cream` | `bg-cream` | Latar halaman, latar input |
| `--surface` | `bg-surface` | Latar card, panel, dropdown |
| `--surface-muted` | `bg-surface-muted` | Latar section selang-seling, hover |
| `--line` | `border-line` | Garis pemisah dekoratif |
| `--green` | `text-primary`, `bg-primary` | Warna utama, link aktif |
| `--green-dark` | `bg-primary-dark` | Hover tombol utama |
| `--on-primary` | `text-on-primary` | Teks di atas latar `primary` |
| `--lime` | `text-accent`, `bg-accent` | Aksen |
| `--danger`, `--danger-bg` | — | Error, aksi hapus |
| `--success-bg`, `--warning`, `--warning-bg` | — | Badge/alert status |
| `--input-border` | — | Border input (kontras ≥ 3:1) |
| `--focus` | — | Cincin fokus keyboard |

**Penting:** di dark mode `--green` menjadi hijau terang. Teks di atas latar hijau **wajib** `text-on-primary` (atau pakai `.button-primary`), bukan `text-white`.

## Tailwind

- Konfigurasi ada di `static/js/tailwind.config.js` (bukan inline). `preflight` dan `container` **dimatikan** agar CSS lama tidak rusak; pakai class `.container` dari `style.css` untuk lebar konten.
- Utility layout bebas dipakai: `grid`, `flex`, `gap-4`, `md:grid-cols-3`, `py-10`, dll.
- Warna token tidak mendukung modifier opacity (`bg-primary/50` **tidak** berfungsi) karena berbasis `var()`.
- Varian `dark:` tersedia (`dark:bg-surface`), tetapi biasanya tidak perlu karena token sudah berganti sendiri.
- Play CDN menampilkan warning "should not be used in production" di console; ini diketahui dan sesuai keputusan kelompok.

## Komponen

### Button

```html
<a class="button button-primary" href="...">Simpan</a>
<button type="button" class="button button-secondary">Batal</button>
<button type="button" class="button button-ghost">Lihat detail</button>
<button type="submit" class="button button-danger">Hapus</button>
<button type="button" class="button button-primary button-sm">Kecil</button>
<button type="button" class="button button-secondary" disabled>Nonaktif</button>
```

Ikon di dalam tombol diberi `aria-hidden="true"`. Tombol yang hanya berisi ikon wajib punya `aria-label`.

### Card

```html
<article class="card card-interactive">
  <div class="card-media"><img src="..." alt="Raket badminton Yonex"></div>
  <div class="card-body">
    <h3 class="card-title"><a class="card-link" href="{% url 'items:detail' item.pk %}">{{ item.name }}</a></h3>
    <p class="card-meta">{{ item.get_category_display }} · {{ item.get_condition_display }}</p>
  </div>
  <div class="card-footer">
    <span class="badge badge-available">Tersedia</span>
  </div>
</article>
```

`.card-link` membuat seluruh card bisa diklik (stretched link) tanpa membungkus card dengan `<a>`. Tombol di `.card-footer` tetap bisa diklik terpisah. `.card-interactive` menambah efek angkat saat hover/fokus.

### Badge

```html
<span class="badge">Netral</span>
<span class="badge badge-verified">✓ Terverifikasi</span>
<span class="badge badge-available">Tersedia</span>
<span class="badge badge-unavailable">Sedang dipinjam</span>
<span class="badge badge-warning">Menunggu</span>
```

Jangan menyampaikan status hanya lewat warna; teks badge harus menjelaskan statusnya.

### Form field

```django
<form method="post" novalidate>
  {% csrf_token %}
  {% for field in form %}
    {% include "partials/form_field.html" with field=field %}
  {% endfor %}
  {% include "partials/form_field.html" with field=form.agree inline=True %}  {# checkbox #}
  <button type="submit" class="button button-primary">Simpan</button>
</form>
```

Partial ini merender label, tanda wajib, help text, dan error. Django 5.2 otomatis menambah `aria-invalid` dan `aria-describedby` pada input, dan id help/error di partial sudah disesuaikan, jadi tidak perlu menambah atribut sendiri. Input di dalam `.form-field` otomatis ter-style; untuk input di luar partial pakai class `.form-input`.

### Empty state

```django
{% url 'items:create' as create_url %}
{% include "partials/empty_state.html" with title="Belum ada barang" text="Barang yang kamu tambahkan akan muncul di sini." action_url=create_url action_label="Tambah barang" icon="📦" %}
```

Semua parameter selain `title` opsional. Pakai `heading_level=3` jika berada di bawah `<h2>` lain.

### Pagination

```django
{% include "partials/pagination.html" with page_obj=page_obj %}
{# dengan HTMX: container #item-list di-swap tanpa full reload, URL ikut berubah #}
{% include "partials/pagination.html" with page_obj=page_obj hx_target="#item-list" %}
```

Parameter query lain (search, filter, sort) otomatis tetap terbawa (`{% querystring %}`, butuh Django ≥ 5.1). Tidak merender apa pun jika hanya satu halaman.

### Toast / messages

Halaman biasa (redirect setelah POST): cukup pakai Django messages, toast tampil otomatis.

```python
messages.success(request, "Barang berhasil disimpan.")
return redirect("items:my_items")
```

Respons HTMX (tanpa reload): kirim header `HX-Trigger`.

```python
import json

response = render(request, "items/partials/item_card.html", {"item": item})
response["HX-Trigger"] = json.dumps({"showToast": {"message": "Barang berhasil disimpan.", "level": "success"}})
return response
```

Biarkan `ensure_ascii` default (`True`) agar karakter non-ASCII aman di header. Level: `success`, `info`, `warning`, `error`. Sukses/info hilang sendiri setelah 5 detik; warning/error tetap sampai ditutup.

Dari JS: `ShareSpace.toast("Pesan", "success")`.

Error HTMX (403, 404, 429, 5xx, koneksi putus) otomatis memunculkan toast error. Jika server mengirim `showToast` sendiri pada respons error, toast generik tidak ditampilkan.

### Indikator loading (HTMX)

```html
<button class="button button-primary" hx-post="..." hx-indicator="#simpan-loading">
  Simpan <span id="simpan-loading" class="spinner htmx-indicator" aria-hidden="true"></span>
</button>
```

## HTMX

- **CSRF sudah otomatis**: `<body hx-headers='{"X-CSRFToken": "..."}'>` berlaku untuk semua `hx-post`, `hx-put`, `hx-delete`. Form biasa tetap butuh `{% csrf_token %}`.
- Respons 4xx/5xx tidak di-swap oleh HTMX (default); pengguna diberi tahu lewat toast.
- Deteksi request HTMX di view: `if request.headers.get("HX-Request"):` lalu kembalikan partial, selain itu halaman penuh.

## Navbar

Link modul diambil dengan `{% url ... as var %}` dan hanya tampil jika URL-nya ada, sehingga halaman tidak error walau app belum di-merge. Nama URL yang dipakai (sepakati; ubah di `templates/partials/header.html` jika berbeda):

| Link | Nama URL | Tampil untuk |
|---|---|---|
| Katalog | `items:catalog` | Semua |
| Lokasi COD | `cod_location:location_list` | Semua |
| Barang saya | `items:my_items` | User login (menu akun) |
| Peminjaman saya | `loans:loan_list` | User login (menu akun) |
| Laporan | `review:report_list` | Staff (menu akun) |
| Admin | `admin:index` | Staff (menu akun) |

Link aktif diberi `aria-current="page"` jika `request.path` sama dengan URL link. Logout memakai form POST.

## Halaman 403 dan 404

Dirender otomatis oleh handler bawaan Django (tidak perlu `handler403`/`handler404` di `urls.py`), **hanya saat `DEBUG=False`**.

```python
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

item = get_object_or_404(Item, pk=pk)            # 404 bersama
if item.owner != request.user and not request.user.is_staff:
    raise PermissionDenied("Hanya pemilik barang yang dapat mengubah barang ini.")  # 403 bersama
```

Pesan `PermissionDenied` ditampilkan di halaman 403. Pengguna yang belum login mendapat tombol masuk dengan `?next=`.

## Dark mode

Class `.dark` di `<html>` dipasang `theme-init.js` sebelum halaman digambar (pilihan dari localStorage, atau preferensi sistem). Tombol toggle ada di navbar. Dari JS: `ShareSpace.theme.get()`, `ShareSpace.theme.set("dark")`, `ShareSpace.theme.toggle()`. Selama memakai token, halaman modul otomatis ikut. Selalu cek halamanmu di kedua tema.

## Checklist aksesibilitas per halaman

- [ ] Satu `<h1>` per halaman, heading berurutan (h1 → h2 → h3).
- [ ] Setiap input punya `<label>` (pakai `partials/form_field.html`).
- [ ] Setiap `<img>` punya `alt` yang bermakna (atau `alt=""` jika dekoratif).
- [ ] Tombol ikon punya `aria-label`; ikon dekoratif `aria-hidden="true"`.
- [ ] Semua aksi bisa dilakukan dengan keyboard (Tab, Enter, Esc) dan cincin fokus terlihat.
- [ ] Status tidak hanya disampaikan lewat warna.
- [ ] Tampilan benar di 375px, 768px, dan desktop; tanpa scroll horizontal.
- [ ] Animasi tambahan menghormati `prefers-reduced-motion` (aturan global di `style.css` sudah menangani sebagian besar).
- [ ] Teks memakai token warna (kontras sudah diuji ≥ 4.5:1 di kedua tema).
