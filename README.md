# Proyek Kelompok PBP (ShareSpace ♻️)
**Tema:** Sustainable Living (Sub-tema: Waste Management & Conscious Shopping)

## 📖 Deskripsi Aplikasi
ShareSpace adalah platform *lending library* (peminjaman barang) berbasis komunitas yang memfasilitasi mahasiswa dan warga sekitar untuk saling meminjamkan barang yang jarang dipakai, alih-alih membeli baru. Banyak barang spesifik seperti calculator, raket badminton, bor listrik, atau buku referensi mahal yang hanya digunakan sesekali, lalu menumpuk dan berpotensi menjadi limbah.

**Manfaat bagi masyarakat:**
1. **Mengurangi Limbah (Waste Reduction):** Menekan angka produksi dan limbah dari barang-barang yang dibeli namun jarang digunakan.
2. **Efisiensi Ekonomi:** Membantu mahasiswa dan masyarakat menghemat pengeluaran.
3. **Membangun Komunitas:** Mendorong interaksi sosial dan rasa saling percaya antar warga lokal/mahasiswa dalam satu kawasan.

## Anggota kelompok

| NPM | Nama |
| --- | --- |
| 2506536143 | Muhammad Taufiq Ramadhan |
| 2506612410 | Azka Nur Jauhar |
| 2506656690 | Fadhil Abdurrohman |
| 2506613552 | Maximus Quinn Hertada |
| 2506544763 | Matthew Raeann Alexandra |

## 🎭 Peran Pengguna (User Roles)
Aplikasi ini menggunakan satu jenis akun terpadu di mana setiap pengguna bisa bertindak sebagai dua peran sekaligus, ditambah satu peran pengelola:
1. **Peminjam:** Pengguna yang mencari, melihat lokasi, dan meminjam barang dari katalog.
2. **Pemilik Barang:** Pengguna yang mendaftarkan barangnya ke dalam platform untuk dipinjamkan, serta menentukan syarat peminjaman.
3. **Admin:** Moderator yang mengawasi aktivitas platform, memverifikasi barang, dan menangani laporan (report) jika terjadi pelanggaran atau kerusakan barang.

## Daftar Modul dan Pembagian Kerja

| No. | Modul | Penanggung Jawab | Model/Data Utama | Public API |
|---|---|---|---|---|
| 1 | Autentikasi & Manajemen Akun | Azka Nur Jauhar | User, UserProfile | Google OAuth / Google Identity Services |
| 2 | Katalog & Manajemen Barang | Matthew Raeann Alexandra | Item ||
| 3 | Transaksi Peminjaman | Fadhil Abdurrohman | LoanRequest | Google reCAPTCHA |
| 4 | Lokasi COD & Jadwal Pengambilan | Muhammad Taufiq Ramadhan  | CODLocation, PickupSchedule | OpenStreetMap / Overpass API |
| 5 | Review, Reputasi & Laporan | Maximus Quinn Hertada | Review, Report ||

---

## Modul 1 — Autentikasi & Manajemen Akun

*Penanggung jawab:* Azka Nur Jauhar
*Model utama:* User, UserProfile
*Public API:* Google OAuth 2.0 / Google Identity Services

Modul ini mengelola proses autentikasi, identitas pengguna, serta informasi profil yang diperlukan untuk membangun komunitas peminjaman yang aman.

### Fitur
- Registrasi, login, logout, dan pengelolaan sesi pengguna.
- Login menggunakan akun Google melalui Google OAuth.
- Pembuatan dan pengubahan profil pengguna.
- Tampilan nama, email, dan foto profil dari akun Google yang terhubung.
- Pengaturan informasi kontak dan area domisili.
- Pembatasan akses: hanya pengguna yang sudah login dapat membuat barang, mengajukan peminjaman, memberi ulasan, atau membuat laporan.
- Pengguna hanya dapat mengubah profil miliknya sendiri.
- Penghapusan/nonaktifkan akun pengguna.

### Pemanfaatan Public API
Google Identity Services digunakan untuk mengautentikasi pengguna melalui akun Google. Setelah autentikasi berhasil, aplikasi memperoleh data dasar seperti nama, email, foto profil, dan status email terverifikasi untuk membantu pengisian profil ShareSpace.

*Dokumentasi:* <https://developers.google.com/identity/gsi/web/guides/overview>

---

## Modul 2 — Katalog & Manajemen Barang

*Penanggung jawab:* Matthew Raeann Alexandra
*Model utama:* Item

Modul ini menjadi pusat katalog barang yang tersedia untuk dipinjamkan oleh pengguna ShareSpace.

### Fitur
- CRUD barang: menambahkan, melihat, mengubah, dan menghapus barang.
- Data barang meliputi nama, deskripsi, kategori, kondisi, foto, pemilik, dan status ketersediaan.
- Halaman katalog utama dengan minimal 50 data barang awal saat aplikasi di-deploy.
- Halaman detail barang.
- Fitur pencarian berdasarkan nama atau deskripsi barang.
- Filter berdasarkan kategori, kondisi barang, dan status ketersediaan.
- Pemilik barang hanya dapat mengubah atau menghapus barang miliknya sendiri.
- Barang yang memiliki transaksi aktif tidak dapat ditawarkan kepada borrower lain.

---

## Modul 3 — Transaksi Peminjaman

*Penanggung jawab:* Fadhil Abdurrohman
*Model utama:* LoanRequest
*Public API:* Google reCAPTCHA

Modul ini mengatur alur permintaan peminjaman barang sejak borrower mengajukan permintaan sampai barang dikembalikan.

### Fitur
- Membuat, melihat, mengubah, dan membatalkan permintaan peminjaman.
- Data transaksi meliputi borrower, lender, barang, tanggal mulai pinjam, due date, catatan, dan status transaksi.
- Lender dapat menerima atau menolak permintaan peminjaman.
- Borrower dapat membatalkan permintaan selama belum disetujui.
- Perubahan status transaksi:

  Menunggu Konfirmasi → Disetujui → Sedang Dipinjam → Selesai

- Halaman daftar transaksi terpisah untuk borrower dan lender.
- Filter transaksi berdasarkan status:
  - Menunggu Konfirmasi;
  - Disetujui;
  - Sedang Dipinjam;
  - Selesai;
  - Ditolak;
  - Dibatalkan.
- Validasi agar satu barang tidak memiliki lebih dari satu transaksi aktif.

### Pemanfaatan Public API
Google reCAPTCHA digunakan pada form pengajuan peminjaman untuk mengurangi spam dan aktivitas bot. Permintaan peminjaman hanya diproses apabila respons verifikasi reCAPTCHA menunjukkan bahwa request berasal dari pengguna yang valid.

*Dokumentasi:* <https://developers.google.com/recaptcha/docs/display>

---

## Modul 4 — Lokasi COD & Jadwal Pengambilan

*Penanggung jawab:* Muhammad Taufiq Ramadhan
*Model utama:* CODLocation, PickupSchedule
*Public API:* OpenStreetMap dan Overpass API

Modul ini membantu lender dan borrower menentukan titik pertemuan atau Cash on Delivery (COD) yang mudah dijangkau dan sesuai untuk proses penyerahan maupun pengembalian barang.

### Fitur
- CRUD titik COD: nama tempat, alamat/deskripsi, koordinat, catatan, dan pembuat titik.
- CRUD jadwal pengambilan dan pengembalian barang.
- Menampilkan titik COD pada peta interaktif menggunakan Leaflet dan OpenStreetMap.
- Borrower dan lender dapat memilih titik COD yang telah tersedia untuk transaksi.
- Tampilan detail titik COD dan jadwal pengambilan pada halaman transaksi.
- Pembatasan akses agar hanya pengguna yang terkait dalam transaksi dapat melihat detail titik COD yang dipilih.

### Pemanfaatan Public API
Overpass API digunakan untuk mengambil rekomendasi lokasi publik di sekitar pengguna, seperti perpustakaan, taman, kafe, atau community centre. Lokasi hasil API ditampilkan pada peta dan dapat difilter berdasarkan:

- jenis lokasi;
- radius pencarian;
- kata kunci lokasi.

Pengguna dapat memilih salah satu hasil lokasi tersebut sebagai titik COD.

*Dokumentasi:*
- OpenStreetMap: <https://www.openstreetmap.org/>
- Overpass API: <https://overpass-api.de/>

---

## Modul 5 — Review, Reputasi & Laporan

*Penanggung jawab:* Maximus Quinn Hertada
*Model utama:* Review, Report

Modul ini membangun rasa aman dan kepercayaan antaranggota ShareSpace melalui ulasan transaksi, reputasi pengguna, serta laporan masalah.

### Fitur
- CRUD ulasan transaksi.
- Rating 1–5 bintang untuk lender dan borrower.
- Ulasan hanya dapat dibuat oleh pengguna yang terlibat dalam transaksi berstatus selesai.
- Tampilan rata-rata rating dan jumlah ulasan pada profil pengguna.
- Perhitungan Trust Score berdasarkan rating rata-rata dan jumlah transaksi selesai.
- CRUD laporan terhadap barang, pengguna, atau transaksi.
- Contoh laporan: barang tidak sesuai deskripsi, barang terlambat dikembalikan, pengguna tidak merespons, atau perilaku tidak pantas saat COD.
- Admin dapat mengubah status laporan:

  Menunggu → Ditinjau → Selesai / Ditolak

## 🛠️ Cara Menjalankan Secara Lokal

**Prasyarat:** Python 3.12 atau lebih baru (dikembangkan dengan Python 3.13 dan Django 5.2), Git, dan Google Chrome (hanya untuk functional test Selenium).

1. Clone repositori dan masuk ke foldernya.
   ```bash
   git clone https://github.com/pbp-kelompok-B05/ShareSpace.git
   cd ShareSpace
   ```
2. Buat dan aktifkan virtual environment.
   ```bash
   python -m venv env
   env\Scripts\activate        # Windows
   source env/bin/activate     # macOS/Linux
   ```
3. Install dependency.
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan migration. Data awal (user dummy `demo_*` dan barang katalog) ikut dimuat otomatis lewat data migration, tanpa perintah `loaddata`.
   ```bash
   python manage.py migrate
   ```
5. (Opsional) Buat akun admin untuk moderasi dan Django admin.
   ```bash
   python manage.py createsuperuser
   ```
6. Jalankan server, lalu buka http://127.0.0.1:8000/.
   ```bash
   python manage.py runserver
   ```

**Konfigurasi environment:** secara lokal tidak perlu file `.env`; aplikasi memakai SQLite (`db.sqlite3`). Di PWS, variabel `PRODUCTION=true` beserta `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, dan `SCHEMA` mengaktifkan PostgreSQL. Jangan commit nilai variabel tersebut.

Akun `demo_*` dari data awal sengaja tidak bisa dipakai login. Untuk mencoba fitur, daftar akun baru lewat halaman register.

### Menjalankan Test

```bash
python manage.py test                                   # seluruh test proyek
python manage.py test items                             # test satu app
python manage.py test --exclude-tag functional          # lewati functional test Selenium
```

Functional test Selenium membutuhkan Google Chrome dan otomatis dilewati jika Chrome atau driver-nya tidak tersedia. Untuk laporan coverage:

```bash
pip install coverage
coverage run --source=items manage.py test items
coverage report -m
```

### Deployment

Setiap push ke branch `main` menjalankan GitHub Actions (`.github/workflows/deploy.yml`) yang mendorong kode ke PWS. Alur kerja kelompok: `feature/*` → Pull Request ke `dev` (minimal 1 approval + AI review) → `dev` di-merge ke `main` → deploy otomatis ke PWS.

## 🔗 Tautan Penting
*   **Tautan Deployment (PWS):** `https://pws.cs.ui.ac.id/maximus.quinn/sharespace`
*   **Tautan Desain (Figma):** `https://www.figma.com/files/folder/655547835`

---

## 🤖 AI Disclosure

### Matthew Raeann Alexandra (Modul 2: Katalog & Manajemen Barang, Base Template & Design System)

Saya memakai **Claude Code** (aplikasi Claude Desktop, model Claude Opus 5.5) sebagai asisten utama, ditambah Figma MCP untuk membaca desain dan browser bawaan Claude untuk memverifikasi halaman di server lokal. Hampir seluruh kode di app `items` dan base template ditulis oleh Claude: model `Item` dengan soft delete, form dan validator, views HTML/JSON, decorator kepemilikan dan rate limit, interaksi HTMX dan JS (dialog edit/hapus, bulk action dengan optimistic UI), test unit dan functional test Selenium, serta `templates/base.html`, partials, dark mode, toast, dan `docs/DESIGN_SYSTEM.md`. Data seed (7 user `demo_*` dan 53 barang) juga data sintetis buatan Claude. Claude juga saya pakai untuk mereview PR anggota lain (#5, #13, #14) dan mengecek integrasi antarmodul.

Strategi prompt saya: spesifikasi modul, target rubrik nilai 4, batas file yang boleh diubah, dan aturan kerja ditulis dalam satu file instruksi proyek. Untuk setiap fitur, Claude wajib menulis rencana (file, field, URL, test) dan menunggu persetujuan saya, mengerjakan satu fitur per langkah dengan TDD (commit test yang gagal terpisah dari implementasinya), menjalankan seluruh test dan coverage, lalu mengecek hasilnya di browser. Claude tidak pernah melakukan commit; semua kode saya review, lalu saya commit dan push sendiri.

#### Keterbatasan AI yang saya temukan
- **Salah asumsi kontrak antarmodul.** Tombol "Ajukan Peminjaman" dibuat sebagai link GET ke `loans:create`, padahal endpoint itu hanya menerima POST, sehingga user mendapat JSON 405. Test tetap lulus karena memakai URL tiruan dan hanya memeriksa `href`. Bug ini baru ketahuan saat pengecekan integrasi di hari deadline.
- **Test yang lulus karena alasan yang salah.** Contohnya test yang membandingkan nilai dengan dirinya sendiri, dan penantian teks "1 barang ditemukan" yang juga cocok dengan "51 barang ditemukan". Keduanya tertangkap sebelum di-commit, tetapi menunjukkan bahwa test buatan AI tetap harus dibaca.
- **Info versi yang keliru.** Tailwind sempat di-pin ke 3.4.19, padahal Play CDN hanya sampai 3.4.17, dan CDN tetap mengembalikan HTTP 200 berisi error. Ini ketahuan dari console browser, bukan dari test.
- **Kasus tepi yang terlewat.** Toast tertutup oleh dialog modal, dan header `Vary` belum memuat `HX-History-Restore-Request` (diketahui dari komentar review PR #12).
- **Batas verifikasi.** Semua pengujian dilakukan di SQLite, tidak di PostgreSQL PWS. Screenshot sering gagal, sehingga tampilan sebagian besar dicek lewat DOM. Rate limit memakai LocMemCache yang berlaku per proses, dan perilakunya di PWS belum dipastikan.

#### Koreksi dan perbaikan manual
- Saya menetapkan semua keputusan desain (soft delete, `is_available` hanya diubah modul transaksi, seed lewat data migration, nama URL lintas modul) dan menolak commit oleh AI serta trailer `Co-Authored-By`.
- Saya menangkap ketika Claude diam-diam mengganti rekomendasi filter ketersediaan (dari tiga pilihan menjadi checkbox) tanpa menandainya sebagai perubahan.
- Saya meluruskan analisis Claude soal syarat `is_verified`: kelompok sudah sepakat syarat itu dihapus di modul loans, bukan di modul saya. Saya juga meminta Claude memeriksa ulang masalah tombol pinjam sampai akar masalahnya ketemu. Hasilnya, tombol diperbaiki menjadi modal form loans dan ditambah test integrasi dengan URL asli.

#### Chat Claude Code
- Tidak dapat share link. Transcript chat ada di folder [`Transcript AI Modul2 (Matthew Raeann)`](<Transcript AI Modul2 (Matthew Raeann)/>).
