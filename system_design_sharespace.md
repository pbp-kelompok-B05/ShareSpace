# System Design: ShareSpace ♻️

ShareSpace adalah platform *lending library* berbasis komunitas yang dibangun menggunakan arsitektur web modern. Dokumen ini merangkum rancangan sistem (System Design) berdasarkan kebutuhan yang tertulis dalam `README.md` dan struktur awal tampilan antarmuka (`html` & `css`).

---

## 1. Arsitektur Sistem & Tech Stack

Aplikasi ShareSpace dirancang menggunakan pola arsitektur **MTV (Model-Template-View)** yang umum pada **Django** (Python). 

```mermaid
flowchart TD
    Client[Client Browser]
    
    subgraph Django Application
        Views[Django Views]
        Templates[Django Templates\nHTML/CSS]
        Models[Django Models\nORM]
    end
    
    DB[(Database\ne.g., PostgreSQL/SQLite)]
    
    subgraph External APIs
        Auth[Google OAuth 2.0]
        Captcha[Google reCAPTCHA]
        Maps[OSM / Overpass API]
    end

    Client <-->|HTTP Request/Response| Views
    Views <--> Templates
    Views <--> Models
    Models <--> DB
    
    Views <-->|API Calls| External APIs
```

- **Frontend:** HTML5, CSS3, dan JavaScript (Leaflet.js untuk peta). Desain UI sudah mengadopsi pendekatan responsif dan aksesibilitas (terlihat dari `base.html` dan `style.css`).
  - **Interaktivitas Sisi Klien:** Diperkaya dengan **AJAX / HTMX** (sesuai spesifikasi proyek) untuk pengalaman pengguna yang dinamis tanpa *full page reload* (contoh: load data ulasan, filter katalog).
- **Backend:** Django (Python).
  - **Auth & Filter:** Implementasi kontrol akses dan filter spesifik pengguna (contoh: halaman profil, data pinjaman pribadi) berdasarkan *session* pengguna yang login.
- **Database:** Relational Database (seperti PostgreSQL untuk production di PWS).

---

## 2. Entity-Relationship Diagram (ERD)

Berdasarkan pembagian modul, berikut adalah rancangan model database utama untuk ShareSpace:

```mermaid
erDiagram
    USER ||--o{ USER_PROFILE : "has"
    USER ||--o{ ITEM : "owns"
    USER ||--o{ LOAN_REQUEST : "borrows"
    USER ||--o{ COD_LOCATION : "creates"
    USER ||--o{ REVIEW : "writes"
    USER ||--o{ REPORT : "submits"

    ITEM ||--o{ LOAN_REQUEST : "is requested in"
    ITEM ||--o{ REPORT : "is reported in"

    LOAN_REQUEST ||--o| PICKUP_SCHEDULE : "has"
    LOAN_REQUEST ||--o{ REVIEW : "has"

    COD_LOCATION ||--o{ PICKUP_SCHEDULE : "used in"

    USER {
        int id PK
        string email
        string username
        boolean is_admin
    }
    USER_PROFILE {
        int id PK
        int user_id FK
        string full_name
        string phone_number
        string address
        string profile_picture_url
    }
    ITEM {
        int id PK
        int owner_id FK
        string name
        string description
        string category
        string condition
        string image_url
        boolean is_available
    }
    LOAN_REQUEST {
        int id PK
        int borrower_id FK
        int item_id FK
        date start_date
        date due_date
        string status "Menunggu, Disetujui, Dipinjam, Selesai, Ditolak, Dibatalkan"
        string notes
    }
    COD_LOCATION {
        int id PK
        int creator_id FK
        string name
        string address
        float latitude
        float longitude
        string notes
    }
    PICKUP_SCHEDULE {
        int id PK
        int loan_request_id FK
        int cod_location_id FK
        datetime pickup_time
        datetime return_time
    }
    REVIEW {
        int id PK
        int reviewer_id FK
        int loan_request_id FK
        int rating
        string comment
    }
    REPORT {
        int id PK
        int reporter_id FK
        int target_item_id FK "nullable"
        int target_user_id FK "nullable"
        string reason
        string status "Menunggu, Ditinjau, Selesai"
    }
```

---

## 3. Integrasi Eksternal (Public APIs)

ShareSpace sangat bergantung pada integrasi API pihak ketiga untuk memperkaya fungsionalitas:

1. **Google Identity Services (OAuth 2.0):** 
   - Digunakan untuk Single Sign-On (SSO). 
   - Mengambil `email`, `nama`, dan `profile_picture` saat registrasi/login.
2. **Google reCAPTCHA:**
   - Diintegrasikan di halaman/form "Ajukan Peminjaman" (`LoanRequest`) untuk mencegah spam bot.
3. **OpenStreetMap & Overpass API:**
   - Digunakan pada penentuan `CODLocation`.
   - Mengambil POI (Point of Interest) publik seperti taman, kafe, atau perpustakaan di sekitar lokasi user untuk rekomendasi tempat COD.

---

## 4. Alur Interaksi Pengguna (User Flow)

Berikut adalah diagram sekuens untuk salah satu fitur utama aplikasi: **Alur Peminjaman Barang.**

```mermaid
sequenceDiagram
    actor Borrower
    participant WebUI
    participant Backend
    participant DB
    actor Lender

    Borrower->>WebUI: Melihat halaman Katalog & Detail Barang
    WebUI->>Borrower: Menampilkan Item
    Borrower->>WebUI: Klik "Ajukan Pinjaman" & Isi Form + reCAPTCHA
    WebUI->>Backend: POST /loan-request/create
    Backend->>Backend: Validasi reCAPTCHA
    Backend->>DB: Simpan LoanRequest (Status: Menunggu)
    DB-->>Backend: OK
    Backend-->>WebUI: Redirect ke Halaman Transaksi
    WebUI-->>Borrower: Notifikasi "Pengajuan Berhasil"
    
    Lender->>WebUI: Buka Notifikasi/Halaman Transaksi
    Lender->>Backend: GET /loan-requests (miliknya)
    Backend->>DB: Fetch Requests
    DB-->>Backend: Data Requests
    Backend-->>WebUI: Tampilkan Daftar Permintaan
    Lender->>WebUI: Klik "Terima" pada request Borrower
    WebUI->>Backend: POST /loan-request/{id}/approve
    Backend->>DB: Update Status -> Disetujui
    Backend->>DB: Update Item Availability -> False
    DB-->>Backend: OK
    Backend-->>WebUI: Transaksi Disetujui
```

---

## 5. Pemetaan UI & Template (Berdasarkan Kode Saat Ini)

Saat ini, Anda sudah memiliki:
- `base.html`: Kerangka utama (Header, Navigasi, Footer). Memuat `style.css`.
- `index.html`: Landing page (Hero section, Tentang, Cara Kerja, Manfaat).
- `style.css`: Styling global dengan palet warna "Sustainable" (hijau, cream, lime).

**Rencana Halaman Selanjutnya (Sesuai Modul):**

1. **Autentikasi (`/auth/...`)**
   - Halaman Login/Register terintegrasi dengan tombol "Sign in with Google".
   - Halaman Profil Pengguna (Edit kontak, domisili, lihat Trust Score).
2. **Katalog (`/katalog/...`)**
   - Halaman Daftar Barang (Grid cards) dengan Filter (Kategori, Kondisi) & Search bar.
   - Halaman Detail Barang.
   - Halaman Form Tambah Barang.
3. **Transaksi (`/transaksi/...`)**
   - Dashboard Transaksi (Daftar Pinjaman Aktif, Riwayat, Permintaan Masuk).
   - Halaman Form Peminjaman (dengan Google reCAPTCHA).
4. **Lokasi COD (`/cod/...`)**
   - Halaman Peta Interaktif (Leaflet.js) untuk memilih atau melihat lokasi COD.
5. **Review & Laporan (`/review/...`, `/report/...`)**
   - Halaman Form Ulasan (dengan bintang 1-5).
   - Dashboard Admin untuk mengelola ulasan dan menindaklanjuti Laporan pengguna.

