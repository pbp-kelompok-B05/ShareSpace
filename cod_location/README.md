## Perubahan Implementasi Overpass API

Pada implementasi awal, pencarian lokasi dilakukan dengan mengirim request langsung ke **Overpass API**. Namun, pendekatan ini mengalami kendala karena **layanan Overpass API sering mengalami timeout atau gagal merespons**, sehingga menyebabkan runtime error dan mengganggu fitur pencarian lokasi COD.

Untuk mengatasi masalah tersebut, mekanisme pencarian diubah menjadi menggunakan **data yang bersumber dari Overpass API**, kemudian diimpor dan disimpan dalam database melalui model `Place`.

**Implementasi ini tetap menggunakan data dari Overpass API.** Perbedaannya, pengambilan data dari Overpass dilakukan pada tahap persiapan/import, bukan setiap kali pengguna melakukan pencarian. Selanjutnya, pencarian berdasarkan kategori, radius, dan kata kunci dilakukan menggunakan data yang sudah tersimpan, kemudian hasilnya dikembalikan dalam format JSON.

Dengan perubahan ini, fitur pencarian menjadi lebih stabil karena **tidak lagi bergantung pada ketersediaan dan waktu respons Overpass API secara langsung saat aplikasi digunakan**.