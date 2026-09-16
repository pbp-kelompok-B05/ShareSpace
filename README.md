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
| 2 | Katalog & Manajemen Barang | Matthew Raeann Alexandra | Item | Open Library API |
| 3 | Transaksi Peminjaman | Fadhil Abdurrohman | LoanRequest | Google reCAPTCHA |
| 4 | Lokasi COD & Jadwal Pengambilan | Muhammad Taufiq Ramadhan  | CODLocation, PickupSchedule | OpenStreetMap / Overpass API |
| 5 | Review, Reputasi & Laporan | Maximus Quinn Hertada | Review, Report | Hugging Face Inference API |

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
*Public API:* Open Library API

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

### Pemanfaatan Public API
Untuk barang berkategori buku, pengguna dapat mencari metadata buku menggunakan Open Library API melalui judul atau ISBN. Hasil API, seperti judul, penulis, sampul, tahun terbit, dan subjek buku, akan ditampilkan sebelum pengguna memilih buku yang sesuai untuk dimasukkan ke katalog.

Hasil pencarian dari API dapat difilter berdasarkan judul, penulis, tahun terbit, atau subjek buku.

*Dokumentasi:* <https://openlibrary.org/developers/api>

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
*Public API:* Hugging Face Inference API

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

### Pemanfaatan Public API
Hugging Face Inference API digunakan untuk melakukan analisis sentimen terhadap isi ulasan pengguna. Sistem menerima hasil klasifikasi sentimen, seperti positif, netral, atau negatif, beserta confidence score dari model.

Hasil analisis API ditampilkan pada daftar ulasan dan dapat difilter berdasarkan:

- semua ulasan;
- sentimen positif;
- sentimen netral;
- sentimen negatif;
- ulasan yang perlu ditinjau admin.

Ulasan dengan sentimen negatif atau confidence rendah dapat ditandai sebagai needs_review, tetapi keputusan akhir untuk menyembunyikan atau menolak ulasan tetap dilakukan oleh admin.

*Dokumentasi:* <https://huggingface.co/docs/inference-providers/index>

## 🔗 Tautan Penting
*   **Tautan Deployment (PWS):** `https://pws.cs.ui.ac.id/maximus.quinn/sharespace`
*   **Tautan Desain (Figma):** `https://www.figma.com/files/folder/655547835`
