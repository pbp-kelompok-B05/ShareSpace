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

### Azka Nur Jauhar (Modul 1: Autentikasi & Manajemen Akun)

Saya menggunakan **Google Antigravity IDE** (dengan model Google Gemini 3.8 Flash) sebagai asisten *pair-programming* utama untuk mengembangkan Modul 1 (Autentikasi, Profil Pengguna, Reputasi & Trust Score, serta Login Helpdesk). Antigravity dimanfaatkan untuk membantu penulisan kode dasar pada form Django, implementasi backend autentikasi eksternal (Google Identity Services GSI dan CAS SSO UI), integrasi AJAX Trust Score & ulasan profil, pembuatan validator hierarki moderasi admin (`AdminModerationPermission` dan `UserDeletionValidator`), serta penyusunan 126 unit test komprehensif yang mencapai cakupan pengujian (*coverage*) hingga 99%.

Strategi prompt saya:
* **Role-Based Persona:** Mengondisikan AI bertindak sebagai rekan mahasiswa programming, dengan batasan untuk selalu menerapkan konsep OOP SOLID (inheritance, polymorphism, encapsulation), tidak menggunakan pustaka eksternal di luar panduan PBP.
* **Test-Driven & Defensive Verification:** Mewajibkan AI merancang skenario pengujian unit test dan coverage terlebih dahulu sebelum melakukan implementasi fitur guna mencegah terjadinya regresi (*regression testing*).
* **Non-Destructive Git Workflow:** Memberlakukan aturan ketat di mana AI dilarang keras mengeksekusi git commit atau push secara mandiri; setiap tindakan commit dan push wajib melalui konfirmasi bertingkat 2–3 kali kepada saya untuk memastikan integritas branch.

#### Keterbatasan AI yang saya temukan
- **Salah Asumsi Hak Akses Verifikasi (*Logical Business Flaw*).** Pada implementasi awal Google OAuth, AI mengasumsikan bahwa semua pengguna yang berhasil login via Google berhak langsung mendapatkan centang hijau `is_verified = True`. Padahal, siapa pun dapat membuat akun Google publik, sehingga tidak membuktikan bahwa pengguna tersebut adalah mahasiswa/civitas akademika UI yang tepercaya.
- **Lokalisasi Waktu Campuran (*Hybrid Localization*).** Saat memformat waktu ulasan relatif, AI menggabungkan fungsi bawaan Django `timesince` secara mentah: `f"{timesince(dt)} yang lalu"`, sehingga menghasilkan tampilan bahasa campuran yang rancu seperti *"1 month yang lalu"* atau *"2 weeks yang lalu"*.
- **Penanganan Exception Parser yang Tidak Lengkap.** Pada fungsi parser XML CAS SSO UI (`parse_cas_xml`), AI awalnya hanya menangani `ValueError` dan `AttributeError`. Ketika server SSO UI mengembalikan respons `None` atau string kosong, terjadi error `TypeError: argument of type 'NoneType' is not iterable` yang meloloskan exception tak tertangani.
- **Pemblokiran WAF / Nginx Server SSO UI.** AI memanggil endpoint validasi tiket SSO UI menggunakan `requests.get()` standar tanpa menyadari bahwa Nginx server `sso.ui.ac.id` memblokir *User-Agent* default Python (`python-requests`) dengan status HTTP 400 Bad Request, sehingga login SSO UI selalu gagal di browser.
- **Kebocoran Informasi Pengguna (*User Enumeration*).** Pada form helpdesk publik (`LoginHelpRequestForm`), AI menerapkan validasi `User.objects.filter(...)` yang menampilkan pesan error *"Akun tidak ditemukan"* jika username belum terdaftar. Hal ini membuka celah keamanan *user enumeration* di mana pihak asing bisa mengecek username/email mana saja yang terdaftar di ShareSpace.

#### Koreksi dan perbaikan manual
- Saya meluruskan logika verifikasi akun: status `is_verified = True` hanya diberikan secara otomatis jika email akun berakhiran `@ui.ac.id` atau `@office.ui.ac.id`, atau diverifikasi manual oleh admin di panel profil publik.
- Saya merancang fungsi helper waktu relatif berbahasa Indonesia murni (`format_relative_time_id`) untuk menggantikan `timesince`, menghasilkan frasa alami seperti *"Baru saja"*, *"3 hari yang lalu"*, *"2 minggu yang lalu"*, atau *"1 bulan yang lalu"*.
- Saya menambal penanganan exception pada backend autentikasi eksternal dengan menambahkan `TypeError` pada blok `try-except` serta merancang fallback yang aman.
- Saya menganalisis kegagalan respons HTTP 400 dari Nginx UI dan menambahkan header `User-Agent` peramban standar pada pemanggilan `requests.get` di `SSOUIAuthBackend.validate_ticket` sehingga tiket CAS SSO UI berhasil diverifikasi dengan HTTP 200.
- Saya menghapus validasi keberadaan akun pada form helpdesk publik dan menyamakan pesan sukses feedback (*"Permohonan bantuan Anda telah diterima. Jika akun terdaftar, admin akan menghubungi email kontakmu."*) serta menambahkan decorator `@rate_limit` untuk mencegah spamming dan kebocoran identitas akun.
- Saya menyusun kelas perizinan moderasi `AdminModerationPermission` berbasis OOP SOLID untuk mencegah staf biasa memoderasi akun superuser atau sesama staf (*privilege escalation*), dan mengondisikan panel admin pada template profil agar disembunyikan bagi staf non-otoritas.

#### Chat Antigravity (Gemini)
- Tidak dapat share link. Transcript chat ada di folder [`Transcript AI Modul 1 (Azka Nur Jauhar)`](<Transcript AI Modul 1 (Azka Nur Jauhar)/>) yang terbagi menjadi:
  - [`Tahap 1: Integrasi Google Identity Services (GSI), CAS SSO UI, dan Custom Auth Backends`](<Transcript AI Modul 1 (Azka Nur Jauhar)/tahap1-google-oauth-sso-backends.md>)
  - [`Tahap 2: Profil Pengguna, AJAX Trust Score, Ulasan Komunitas, dan Integrasi Lintas-Modul`](<Transcript AI Modul 1 (Azka Nur Jauhar)/tahap2-profile-reputation-trust-score.md>)
  - [`Tahap 3: Form Bantuan Login Helpdesk, Anti-Enumeration, Rate Limit, dan Hierarki Moderasi Admin`](<Transcript AI Modul 1 (Azka Nur Jauhar)/tahap3-login-helpdesk-admin-moderation.md>)

---


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

## Fadhil Abdurrohman (Modul 3: Loan Transactions)

Dalam pengembangan proyek **ShareSpace**, khususnya modul **Loan Transactions**, saya menggunakan **ChatGPT (OpenAI)** sebagai alat bantu dalam proses implementasi, debugging, dan pengujian kode.

#### Penggunaan AI
Beberapa bagian kode ditulis dengan bantuan AI, terutama pada implementasi views, validasi transaksi, AJAX, integrasi reCAPTCHA, serta unit testing. AI juga digunakan untuk memberikan saran perbaikan kode, menjelaskan konsep, dan membantu mengidentifikasi penyebab error.

#### Batasan Penggunaan AI
Penggunaan AI dibatasi sebagai alat bantu pengembangan. Saya tetap menentukan kebutuhan fitur, alur transaksi, struktur implementasi, dan keputusan akhir. Kode yang dihasilkan AI tidak langsung digunakan tanpa pemeriksaan dan penyesuaian terlebih dahulu.

#### Strategi Prompt
Prompt diberikan secara spesifik dan bertahap dengan menyertakan konteks proyek, struktur kode yang sudah ada, kebutuhan fitur, serta pesan error yang ditemukan. Saya juga memberikan instruksi tambahan agar solusi AI sesuai dengan implementasi modul lain dan tidak mengubah fungsionalitas yang sudah berjalan.

#### Keterbatasan AI
- Beberapa kode yang dihasilkan belum sepenuhnya sesuai dengan struktur dan versi terbaru proyek.
- AI terkadang mengasumsikan keberadaan fungsi, atribut, atau konfigurasi yang belum tersedia.
- Solusi yang diberikan terkadang menimbulkan konflik dengan implementasi modul lain.
- Beberapa implementasi belum berhasil melewati seluruh unit test, khususnya terkait validasi reCAPTCHA.
- AI tidak dapat memastikan seluruh fitur berjalan dengan benar tanpa pengujian langsung pada lingkungan proyek.

#### Koreksi dan Perbaikan Manual
- Meninjau dan menyesuaikan kode AI dengan struktur proyek serta kebutuhan fitur.
- Memperbaiki integrasi modul Loan Transactions dengan Items, Authentication, dan Reviews & Reports.
- Menyelesaikan merge conflict pada `settings.py` agar konfigurasi Google OAuth dan reCAPTCHA tetap berjalan.
- Memperbaiki penanganan reCAPTCHA agar pengujian tidak gagal akibat konfigurasi lingkungan pengujian.
- Memeriksa dan memperbaiki error yang berkaitan dengan database migration setelah integrasi antar-branch.
- Menjalankan dan mengevaluasi unit test serta memperbaiki error yang ditemukan.
- Memeriksa kembali implementasi sebelum melakukan commit, push, dan pull request.

#### Log Chat ChatGPT
- [ChatGPT](https://chatgpt.com/share/6ae4b984-7890-83ec-a204-a2bcc41113a3)

## AI DIsclosure COD-LOCATION APP(Muhammad Taufiq Ramadhan) ##

Sebagian besar pengembangan modul COD Location dibantu oleh AI, terutama dalam pembuatan kode HTML, JavaScript, serta unit testing. Berikut penjelasan penggunaan AI, keterbatasannya, dan proses pengecekan yang dilakukan secara manual.

### 1. Penggunaan AI

- **Frontend:** Sebagian besar kode HTML dan JavaScript pada modul COD dibuat dengan bantuan AI. Peran saya terutama memeriksa kesesuaian tampilan, fitur, dan alur pengguna dengan kebutuhan aplikasi.
- **Unit Testing:** AI membantu membuat unit test untuk memeriksa fungsionalitas modul COD, termasuk pengelolaan lokasi, penjadwalan, dan pencarian tempat.
- **Debugging:** AI digunakan untuk membantu menganalisis error dan memberikan alternatif solusi selama proses pengembangan.
- **Integrasi Overpass API:** AI membantu mencari solusi atas permasalahan timeout dan kegagalan request ketika menggunakan layanan Overpass API secara langsung.

### 2. Keterbatasan AI dan Solusi yang Diterapkan

**Permasalahan Overpass API**

Pada awalnya, AI menyarankan penggunaan Overpass API secara langsung untuk mencari lokasi. Namun, implementasi tersebut sering mengalami timeout dan kegagalan respons saat dijalankan.

Beberapa endpoint Overpass API publik telah dicoba, tetapi permasalahan serupa masih terjadi. Akhirnya, AI menyarankan pendekatan alternatif, yaitu mengambil data dari Overpass API terlebih dahulu, lalu mengimpornya ke database melalui model `Place`.

Solusi ini membuat pencarian lebih stabil karena tidak lagi bergantung pada API eksternal setiap kali pengguna melakukan pencarian. Namun, **terdapat keterbatasan penting: hanya lokasi yang sudah tersedia dalam data JSON hasil pengambilan sebelumnya yang dapat ditemukan**. Lokasi baru atau lokasi yang belum diimpor tidak akan muncul, sehingga data perlu diperbarui secara berkala apabila ingin menjaga kelengkapan informasi.

**Keterbatasan Kode yang Dihasilkan AI**

Kode yang dihasilkan AI tidak selalu langsung sesuai dengan kebutuhan proyek atau terintegrasi dengan modul lain. Oleh karena itu, kode tetap perlu diperiksa dan diuji. Unit test yang dibuat AI juga tidak menjamin seluruh fitur berjalan dengan benar tanpa pengujian tambahan.

### 3. Pengecekan dan Perbaikan Manual

Meskipun sebagian besar implementasi dibantu AI, saya tetap melakukan pengecekan dan penyesuaian, antara lain:

- Memeriksa kesesuaian tampilan dan alur fitur COD dengan kebutuhan aplikasi.
- Mencoba fitur CRUD lokasi, pengelolaan jadwal, dan pencarian tempat secara langsung.
- Menguji berbagai endpoint Overpass publik untuk memastikan masalah timeout yang terjadi.
- Menjalankan unit test serta memeriksa hasil pengujiannya.
- Menyesuaikan implementasi berdasarkan error yang ditemukan dan masukan dari code review.

Dengan demikian, AI digunakan sebagai alat bantu utama dalam penulisan kode dan pencarian solusi, sedangkan pengecekan, pengujian, serta keputusan penerapan solusi tetap dilakukan berdasarkan kebutuhan dan hasil pengujian aplikasi.

### 4. Link chat

- https://claude.ai/share/33009b08-83ca-4ae3-902f-240a3181684f
- https://chatgpt.com/share/6ae4bb4c-d6fc-83ec-9e59-a55263f2c3e7

### 5. Cara agar data lokasi hasil import overpass dapat digunakan di pws
  Jalankan:
    python manage.py migrate
    python manage.py import_places places_overpass.json
    python manage.py import_places places_tambahan.json
