## Perubahan Implementasi Overpass API

Pada implementasi awal, pencarian lokasi dilakukan dengan mengirim request langsung ke **Overpass API**. Namun, pendekatan ini mengalami kendala karena **layanan Overpass API sering mengalami timeout atau gagal merespons**, sehingga menyebabkan runtime error dan mengganggu fitur pencarian lokasi COD.

Untuk mengatasi masalah tersebut, mekanisme pencarian diubah menjadi menggunakan **data yang bersumber dari Overpass API**, kemudian diimpor dan disimpan dalam database melalui model `Place`.

**Implementasi ini tetap menggunakan data dari Overpass API.** Perbedaannya, pengambilan data dari Overpass dilakukan pada tahap persiapan/import, bukan setiap kali pengguna melakukan pencarian. Selanjutnya, pencarian berdasarkan kategori, radius, dan kata kunci dilakukan menggunakan data yang sudah tersimpan, kemudian hasilnya dikembalikan dalam format JSON.

Dengan perubahan ini, fitur pencarian menjadi lebih stabil karena **tidak lagi bergantung pada ketersediaan dan waktu respons Overpass API secara langsung saat aplikasi digunakan**.



## AI DIsclosure COD-LOCATION APP ##

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