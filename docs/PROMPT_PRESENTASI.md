# Prompt untuk Membuat Presentasi SawitScan AI

Berkas ini berisi **prompt siap pakai** untuk membuat deck presentasi tentang cara
menggunakan aplikasi SawitScan AI, beserta daftar screenshot yang menyertainya.

Screenshot ada di [`docs/screenshots/`](screenshots/) — diambil langsung dari
aplikasi yang berjalan (viewport 1440×960, retina 2×, full page).

| Berkas | Layar | Dipakai di slide |
| --- | --- | --- |
| `01-dashboard.png` | Dashboard, semua blok | 4 |
| `02-dashboard-blok.png` | Dashboard difilter Blok A-3, satu pohon terpilih | 5 |
| `03-unggah.png` | Form unggah + keterangan citra | 6 |
| `04-hasil-deteksi.png` | Hasil deteksi: bbox + panel temuan | 7 |
| `05-riwayat.png` | Riwayat citra | 8 |
| `06-peta.png` | Peta sebaran penuh | 9 |
| `07-laporan.png` | Tabel unduhan PDF/CSV | 10 |
| `08-pengaturan.png` | Acuan kondisi & status sistem | 11 |

---

## PROMPT — salin mulai dari sini

````
Kamu adalah seorang technical writer yang membuat deck presentasi internal.

Buatkan presentasi berjudul "SawitScan AI — Panduan Penggunaan Aplikasi"
sebanyak 13 slide dalam Bahasa Indonesia.

## Konteks aplikasi

SawitScan AI adalah aplikasi web untuk mendeteksi dan mengklasifikasi KONDISI
TANAMAN kelapa sawit dari citra UAV (drone). Aplikasi ini adalah lapisan
inference & pelaporan di atas model AI yang dilatih terpisah (YOLOv8 untuk
deteksi area, Swin Transformer + Multi-Task Learning untuk klasifikasi).

Alur kerja pengguna: unggah citra UAV → sistem mengekstrak GPS & waktu dari
metadata EXIF → inference berjalan → hasil ditampilkan sebagai bounding box di
atas citra → agregat masuk ke dashboard dan peta → laporan diekspor PDF/CSV.

Empat kelas kondisi yang dikenali (dari dataset klien di Roboflow,
`heras-workspace/oil-palm-central-kalimantan`, 1.007 citra):

| Kelas | Label UI | Ciri dari citra atas | Interpretasi | Tindakan |
|---|---|---|---|---|
| healthy | Sehat | Tajuk hijau rapat, ukuran pelepah normal | Tanaman sehat | Tidak ada tindakan |
| yellow | Menguning | Tajuk didominasi kuning atau hijau pucat | Dugaan defisiensi nutrisi | Periksa unsur hara, pemupukan susulan (N/Mg/K) |
| dead | Mati/stres | Tajuk mengering, cokelat, pelepah mati | Pelepah mati atau tanaman stres berat | Pemangkasan atau inspeksi lapangan |
| small | Kerdil | Tajuk lebih kecil dibanding sekitarnya | Pertumbuhan terhambat | Review pemupukan, evaluasi kondisi tanah |

Tingkat keparahan: sehat / ringan / sedang / berat. Warna di seluruh aplikasi:
hijau #2FBF71 (sehat), kuning #E8B93B (ringan–sedang), merah #E2574C (berat).

## Aturan istilah — WAJIB dipatuhi

- Gunakan **"kondisi tanaman"**, JANGAN "penyakit", untuk apa yang dideteksi
  sistem. Kata "penyakit" hanya boleh muncul saat menyebut judul proyek.
- JANGAN pernah menyebut nama penyakit seperti Ganoderma, Leaf Blight, Stem Rot,
  atau Rhinoceros Beetle. Nama-nama itu tidak ada di dataset, jadi model tidak
  akan pernah mengeluarkannya.

## Aturan kejujuran — WAJIB dipatuhi

- Inference saat ini masih **MOCK**: model asli belum dipasang, hasil deteksi
  dibangkitkan secara sintetis. Ini harus disebut jelas di slide 2 dan slide 12.
- JANGAN mengarang metrik model (akurasi, mAP, presisi, recall). Belum ada
  angkanya karena model belum dipasang.
- JANGAN mengarang angka bisnis (penghematan biaya, kenaikan hasil panen,
  jumlah hektar yang dipantau). Tidak ada datanya.
- Angka yang boleh dipakai hanyalah yang tampil di screenshot.
- Aplikasi belum punya autentikasi — sebutkan sebagai keterbatasan di slide 12.

## Struktur slide

1. **Judul** — "SawitScan AI: Panduan Penggunaan", subjudul "Deteksi kondisi
   tanaman kelapa sawit dari citra UAV". Tanpa screenshot.
2. **Apa itu SawitScan AI** — tiga poin: (a) yang dilakukan aplikasi, (b) yang
   BUKAN cakupannya (aplikasi tidak melatih model; training & labeling ada di
   sisi klien lewat Roboflow), (c) status sekarang: inference masih mock.
3. **Alur kerja dalam 5 langkah** — diagram sederhana:
   Unggah → Preprocessing & ekstraksi GPS → Deteksi (YOLOv8) → Klasifikasi
   (Swin + MTL) → Dashboard, Peta, Laporan. Tanpa screenshot.
4. **Dashboard** — gambar `01-dashboard.png`. Jelaskan empat kartu KPI (Total
   Pohon Terdeteksi 84, Pohon Sehat 59, Pohon Bermasalah 25, Kasus Berat 11),
   peta perkebunan, panel citra drone, distribusi kondisi, dan antrian inference.
5. **Menyaring per blok kebun** — gambar `02-dashboard-blok.png`. Tunjukkan tab
   BLOK (Semua / A-3 / B-7); memilih satu blok menyaring SEMUA panel sekaligus —
   judul, KPI (jadi 62/44/18/8), bar distribusi, titik peta, dan antrian. Klik
   satu titik pohon di peta membuka detailnya di panel kanan.
6. **Mengunggah citra** — gambar `03-unggah.png`. Jelaskan tiga isian keterangan
   dan alasannya: blok kebun, luas area (ha), dan titik koordinat. Tekankan
   bahwa ketiganya tidak dapat disimpulkan dari berkas citra, sehingga diisi
   operator. Tekankan juga: koordinat manual HANYA dipakai bila EXIF tidak
   membawa GPS — metadata asli selalu menang.
7. **Membaca hasil deteksi** — gambar `04-hasil-deteksi.png`. Jelaskan bounding
   box berwarna sesuai keparahan, angka keyakinan pada label, panel daftar
   temuan di kanan, dan sorot silang saat kursor diarahkan.
8. **Riwayat citra** — gambar `05-riwayat.png`. Semua unggahan tersimpan dan
   dapat dibuka kembali; kartu menampilkan blok, waktu pemotretan, dan ringkasan.
9. **Peta sebaran** — gambar `06-peta.png`. Titik diplot dari koordinat GPS.
   Catat keterbatasan penting: peta hanya terisi bila citra membawa GPS di EXIF.
10. **Mengekspor laporan** — gambar `07-laporan.png`. PDF berisi ringkasan,
    rekomendasi tindakan per kondisi yang ditemukan, dan rincian temuan. CSV
    berisi satu baris per pohon, memakai BOM UTF-8 agar rapi dibuka di Excel.
11. **Pengaturan & acuan kondisi** — gambar `08-pengaturan.png`. Tabel acuan
    keempat kelas, skala keparahan, dan status sistem.
12. **Keterbatasan saat ini** — jujur dan spesifik:
    - Inference masih mock; hasil belum mencerminkan isi citra.
    - Label keparahan belum ada di dataset, jadi nilai severity belum dapat
      dipertanggungjawabkan sampai klien menyediakannya.
    - Belum ada autentikasi pengguna.
    - Peta kosong bila citra tidak membawa GPS.
13. **Langkah berikutnya** — apa yang dibutuhkan agar sistem siap produksi:
    berkas model final (.pt/ONNX) dari klien, label keparahan, citra UAV asli
    ber-EXIF untuk pengujian, dan autentikasi.

## Gaya visual

- Palet: hijau tua #0B3D2C (aksen utama & latar slide judul), hijau #2FBF71
  (aksen terang), latar terang #EEF2EE, teks #12261C.
- Font: Plus Jakarta Sans (atau sans-serif serupa) untuk judul dan isi.
- Bersih dan lapang. Maksimal 5 poin per slide, kalimat pendek.
- Setiap slide berscreenshot: gambar mendominasi, teks penjelas ringkas di
  samping atau di bawah.

## Keluaran

Untuk tiap slide, tuliskan:
- Judul slide
- Isi (bullet, maksimal 5)
- Nama berkas screenshot yang dipakai (atau "tanpa gambar")
- Catatan pembicara: 2–3 kalimat, bahasa lisan, untuk dibacakan presenter
````

## PROMPT — selesai di sini

---

## Catatan tentang screenshot

Beberapa hal yang perlu diketahui agar tidak salah dibaca saat presentasi:

- **Citra pada screenshot adalah gambar sintetis**, bukan foto drone asli.
  Belum ada citra UAV sungguhan di sistem, jadi bounding box tampak melayang di
  atas latar hijau polos. Kalau Anda punya foto drone asli, unggah dulu lalu
  ambil ulang screenshot-nya agar jauh lebih meyakinkan.
- **Latar peta tampak polos** karena OpenStreetMap tidak memiliki data terpetakan
  di koordinat contoh tersebut, bukan karena peta gagal dimuat. Dengan koordinat
  kebun yang sebenarnya, latar peta akan terlihat wajar.
- **Angka pada screenshot berasal dari inference mock**, jadi jangan dikutip
  sebagai temuan lapangan.

## Mengambil ulang screenshot

Jalankan backend dan frontend, lalu gunakan Playwright:

```bash
pip install playwright && playwright install chromium
```

Skrip pengambilan gambar ada di riwayat commit; intinya membuka tiap rute dengan
viewport 1440×960, `device_scale_factor=2`, menunggu ubin peta termuat
(`.leaflet-tile-loaded`), lalu `full_page=True`.
