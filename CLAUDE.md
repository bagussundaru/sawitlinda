# SawitScan AI — Panduan Proyek (dibaca otomatis tiap sesi)

## Ringkasan
Aplikasi web untuk deteksi & klasifikasi penyakit kelapa sawit dari citra UAV (drone).
Web ini adalah **lapisan inference & pelaporan** di atas model AI yang dilatih terpisah.
Model: YOLOv8 (deteksi area) → Swin Transformer + Multi-Task Learning (klasifikasi jenis penyakit + tingkat keparahan).

Referensi wajib dibaca sebelum mulai:
- `docs/Proposal_Deteksi_Penyakit_Sawit.docx` — ruang lingkup, alur bisnis, batas tanggung jawab.
- `docs/SawitScan_Prototype.html` — acuan tampilan (UI/UX) dan alur layar. IKUTI desain & alur ini.

## Bahasa
- Seluruh label & teks UI: **Bahasa Inggris** (diubah atas permintaan klien,
  Agustus 2026; sebelumnya Bahasa Indonesia).
- Komentar kode: Bahasa Indonesia — catatan untuk yang merawat kode.
- Nama variabel & identifier: bebas, mengikuti berkas sekitarnya.

## Stack
- Backend: **FastAPI** (Python). Model PyTorch jalan native di sini.
- Frontend: **Next.js / React**, peta pakai **Leaflet**.
- Database: **PostgreSQL**.
- Untuk MVP: inference **sinkron** dulu. Batch besar → tambahkan queue (Celery/RQ) belakangan.

## BATAS SCOPE — PENTING
- Web ini **TIDAK** melatih model. Training/labeling = tanggung jawab klien (Roboflow + notebook).
- Web menerima model **final** sebagai berkas (`.pt` / ONNX) yang cukup **di-swap** saat retrain.
- **Tahap sekarang: endpoint inference masih MOCK.** Kembalikan JSON sesuai kontrak di bawah,
  belum load model asli. Nanti tinggal ganti isi fungsi `run_inference()` dengan `model.predict()`.
- JANGAN membangun ulang integrasi tiap kali model berubah — abstraksi model harus di satu tempat.

## Kontrak JSON hasil deteksi (dipegang backend & frontend)
```json
{
  "image_id": "uuid",
  "filename": "blok_a3_001.jpg",
  "captured_at": "2026-07-21T08:12:00Z",
  "gps": { "lat": -0.78912, "lng": 101.41233 },
  "summary": { "total": 35, "healthy": 27, "infected": 8, "severe": 2 },
  "detections": [
    {
      "id": 1,
      "bbox": [x, y, w, h],
      "condition": "Mati/stres",     // label kondisi, bukan diagnosis penyakit
      "severity": "berat",           // sehat | ringan | sedang | berat
      "confidence": 0.94,
      "gps": { "lat": -0.78915, "lng": 101.41240 }
    }
  ]
}
```
Frontend menggambar bbox + label dari array `detections`; dashboard & peta memakai `summary` + `gps`.

## Daftar kondisi tanaman (mengikuti dataset klien)
Dataset Roboflow `heras-workspace/oil-palm-central-kalimantan` berisi 4 kelas
**kondisi tanaman**, bukan nama penyakit:
`healthy` (Sehat), `yellow` (Menguning), `dead` (Mati/stres), `small` (Kerdil).

Daftar penyakit di proposal (Ganoderma, karat daun, bercak daun Curvularia,
defisiensi hara) TIDAK ada di dataset — hanya "defisiensi hara" yang bersinggungan
dengan `yellow`. Karena itu istilah di kode & UI memakai **kondisi**, bukan penyakit.
Keparahan (`severity`) juga belum ada labelnya di dataset. Lihat `docs/SWAP_MODEL.md`.

## Prinsip kerja
- Jelaskan rencana sebelum menulis banyak kode. Tunggu konfirmasi untuk keputusan besar.
- Buat commit kecil & jelas. Sertakan cara menjalankan (dev) di README.
- Gunakan variabel lingkungan untuk kredensial DB; jangan hardcode.
