# Audit: Proposal vs Sistem yang Berjalan

Pemeriksaan butir demi butir proposal terhadap kode yang benar-benar ada.
Diperiksa langsung ke berkas sumber, endpoint, dan migrasi — bukan dari ingatan.

Tanggal audit: 5 Agustus 2026 · commit `739f3bc` · 92 tes lulus.

---

## §3 Ruang Lingkup Pekerjaan

| Komponen | Status | Bukti di sistem |
| --- | --- | --- |
| **Modul upload** — single & batch, validasi format, ekstraksi GPS | ✅ **Selesai** | `POST /api/upload`, batch multi-berkas, 5 format (`jpg/jpeg/png/tif/tiff`), `services/exif.py` membaca GPS & waktu pemotretan. Batas ukuran `MAX_UPLOAD_MB`. |
| **Pipeline inference** — integrasi model final (YOLOv8 + Swin + MTL) | ⚠️ **Titik integrasi siap, model belum ada** | `run_inference()` di `inference/engine.py` adalah satu-satunya titik sentuh model; isinya masih mock. `MODEL_PATH` sudah dibaca, `GET /api/system` melaporkan `inference_mode`. |
| **Visualisasi hasil** — bbox, label, keparahan, confidence | ✅ **Selesai** | `/hasil/{id}`: bbox SVG di atas citra, warna per keparahan, label persentase, panel temuan, sorot silang. |
| **Dashboard** — agregat sehat vs sakit, distribusi per jenis | ✅ **Selesai** | `GET /api/dashboard`, 4 kartu KPI, bar distribusi kondisi, donat rasio. Bisa disaring per blok. |
| **Peta sebaran** — Leaflet berdasarkan GPS | ✅ **Selesai** | `GET /api/map`, Leaflet + OpenStreetMap, pengalih layer, klik titik → detail pohon. |
| **Riwayat & database** | ✅ **Selesai** | PostgreSQL, 4 migrasi Alembic, `GET /api/results`, layar `/riwayat`. |
| **Export laporan** — PDF / CSV | ✅ **Selesai** | `export.pdf` (ringkasan + rekomendasi tindakan + rincian) dan `export.csv` (satu baris per pohon, BOM UTF-8). |

**6 dari 7 komponen selesai.** Satu-satunya yang tertahan adalah pipeline
inference, dan bukan karena pekerjaan web — berkas model final belum ada.

---

## §4 Arsitektur Teknis

| Butir proposal | Status |
| --- | --- |
| Frontend Next.js / React + Leaflet | ✅ Next.js 15, React 19, react-leaflet |
| Backend FastAPI (Python) | ✅ FastAPI 0.115 |
| Inference: YOLOv8 → Swin + MTL | ⚠️ Belum — masih mock |
| Basis data PostgreSQL | ✅ PostgreSQL 16, teruji lewat `scripts/check_postgres.py` |
| Model sebagai berkas `.pt`/ONNX yang di-swap | ✅ Terdokumentasi di `docs/SWAP_MODEL.md`; hanya `engine.py` yang perlu disentuh |

---

## §5 Hal yang Perlu Diklarifikasi

Ini pertanyaan terbuka di proposal, bukan komponen yang bisa "selesai" oleh web.

| Pertanyaan | Status | Catatan |
| --- | --- | --- |
| **Skala citra** — satu pohon/petak kecil atau orthomosaic seluruh kebun? | ❌ **Belum dijawab** | Sistem sekarang menganggap satu berkas = satu bingkai UAV. **Tiling belum dibangun.** Kalau citra ternyata orthomosaic, ini pekerjaan tambahan yang nyata. |
| **Daftar penyakit + definisi keparahan** | ⚠️ **Separuh terjawab** | Kelas kondisi sudah pasti dari dataset (4 kelas). **Definisi & label keparahan masih kosong** — lihat bagian di bawah. |
| **Retrain dari web** | ✅ **Tidak dibangun, sesuai proposal** | Proposal menyebutnya opsional dan di luar paket. |
| **Jumlah & resolusi citra (± 3.000)** | ❌ **Belum diuji pada skala itu** | Inference masih **sinkron**; belum ada antrean (Celery/RQ). Uji beban belum dilakukan. |
| **Cloud atau on-premise** | ✅ **Terjawab dalam praktik** | Terpasang di VM Anda (`43.157.197.253`), berdampingan dengan aplikasi lain. |

---

## Temuan audit yang perlu ditindaklanjuti

### 1. Tiling & resize belum ada, padahal layar proses sempat menjanjikannya

Proposal §2 menyebut *"preprocessing: penyesuaian ukuran, pemotongan (tiling) bila
diperlukan"*. Pencarian di `backend/app/` tidak menemukan kode tiling, resize,
maupun crop.

Layar "Proses" menampilkan tahap **"Preprocessing — resize · tiling · GPS"**,
yang mengklaim pekerjaan yang tidak dilakukan. Label itu sudah diperbaiki
menjadi **"validasi · EXIF · GPS"** — sesuai yang benar-benar dikerjakan — dan
layar itu kini menyatakan bahwa tahap YOLOv8 serta Swin + MTL menggambarkan
pipeline yang dituju, belum yang berjalan.

Apakah tiling perlu dibangun bergantung pada jawaban §5 butir 1.

### 2. Keparahan belum punya dasar data

Dataset klien tidak memuat label keparahan sama sekali. Nilai `severity` yang
tampil sekarang berasal dari mock. Ini memengaruhi `summary.severe`, warna titik
di peta, dan kartu "Kasus Berat".

**Untuk disertasi, ini tidak boleh dilaporkan sebagai hasil pengukuran.**

### 3. Belum ada modul evaluasi kuantitatif

Sistem tidak menghitung mAP, precision, recall, F1, maupun confusion matrix —
karena tidak ada model dan tidak ada ground truth di dalam sistem.

Disertasi bidang ini umumnya menuntut angka evaluasi. Modul evaluasi bisa
dibangun (unggah anotasi ground truth → hitung metrik → tampilkan), tapi baru
bermakna setelah model asli terpasang.

### 4. Uji beban belum dilakukan

Referensi proposal ± 3.000 citra. Saat ini inference sinkron, satu per satu,
di VM 2 core. Dengan model asli, satu citra realistis 2–10 detik di CPU —
3.000 citra berarti 1,5–8 jam berturut-turut dan seluruh permintaan lain
mengantre. Antrean (Celery/RQ) yang disebut `CLAUDE.md` menjadi wajib.

---

## Catatan khusus disertasi

Aplikasi ini **layak dipakai sebagai artefak rekayasa perangkat lunak**: arsitektur
sesuai proposal, 6 dari 7 komponen berjalan, 92 tes otomatis, migrasi database
berversi, dan terpasang di server sungguhan.

Yang **tidak boleh** dilakukan:

- Melaporkan angka apa pun dari sistem saat ini sebagai temuan lapangan atau
  hasil pengukuran model. Seluruh deteksi masih dibangkitkan secara sintetis.
- Mengutip metrik akurasi. Tidak ada satu pun yang dihitung.
- Menampilkan tangkapan layar berisi data mock tanpa keterangan bahwa itu mock.

Sistem sudah menandai statusnya sendiri di beberapa tempat — panel "Mode mock"
di sidebar, peringatan di layar Pengaturan, dan keterangan di layar Proses —
sehingga tangkapan layar apa pun membawa konteksnya sendiri.

Yang **dibutuhkan** agar bisa masuk bab hasil:

1. Berkas model final (`.pt`/ONNX) hasil pelatihan di Roboflow.
2. Label keparahan, atau keputusan untuk menghapus dimensi keparahan dari ruang lingkup.
3. Test set berlabel + modul evaluasi untuk menghasilkan mAP/precision/recall.
4. Citra UAV asli ber-EXIF untuk validasi ujung-ke-ujung.
5. Jawaban atas skala citra (§5 butir 1) — menentukan perlu tidaknya tiling.
