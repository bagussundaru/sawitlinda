# SPEC — SawitScan AI

Spesifikasi teknis & urutan pembangunan. Kerjakan bertahap; selesaikan & uji tiap tahap sebelum lanjut.

## 1. Arsitektur
```
Frontend (Next.js + Leaflet)
        │  REST / JSON
        ▼
Backend (FastAPI)
   ├── /api/upload        terima citra, ekstrak GPS (EXIF), simpan
   ├── /api/analyze/{id}  jalankan inference (MOCK dulu) → simpan hasil
   ├── /api/results/{id}  ambil satu hasil
   ├── /api/results       daftar riwayat
   └── /api/dashboard     agregat (summary lintas citra)
        │
        ▼
PostgreSQL  (tabel: images, detections)
        ▲
        │  berkas terpisah, di-swap saat retrain
Model (.pt / ONNX)  ← di luar scope web
```

## 2. Skema database (acuan awal)
- **images**: id (uuid, pk), filename, storage_path, captured_at, gps_lat, gps_lng, status (uploaded|analyzed), created_at
- **detections**: id (pk), image_id (fk), bbox_x, bbox_y, bbox_w, bbox_h, disease, severity (ringan|sedang|berat), confidence (float), gps_lat, gps_lng

## 3. Abstraksi model (kunci maintainability)
Satu modul, mis. `backend/inference/engine.py`:
```python
def run_inference(image_path: str) -> dict:
    """Kembalikan payload sesuai kontrak JSON di CLAUDE.md.
    TAHAP INI: mock — hasilkan deteksi acak yang realistis.
    NANTI: load model .pt/ONNX & jalankan predict di sini. Antarmuka fungsi TIDAK berubah."""
```
Semua kode lain hanya memanggil `run_inference()`. Ganti model = ubah isi fungsi ini saja.

## 4. Frontend — layar (ikuti prototype)
1. **Upload** — drag&drop + batch, tampilkan progress.
2. **Proses** — animasi pipeline (Preprocessing → YOLOv8 → Swin+MTL → Hasil).
3. **Hasil Deteksi** — gambar + bbox + label; panel daftar temuan; hover saling-sorot.
4. **Dashboard** — 4 kartu statistik, bar distribusi penyakit, donut sehat vs sakit.
5. **Peta Sebaran** — Leaflet, titik hijau/kuning/merah per keparahan; klik = detail pohon.
6. **Export** — tombol PDF & CSV.

## 5. Urutan pengerjaan
1. Scaffold repo (backend + frontend + docker-compose untuk PostgreSQL) + README dev.
2. Backend: model DB + migrasi + endpoint upload (ekstrak EXIF GPS).
3. Backend: `run_inference()` mock + endpoint analyze/results/dashboard.
4. Frontend: layar upload → proses → hasil (konsumsi API nyata).
5. Frontend: dashboard + peta Leaflet.
6. Export PDF/CSV.
7. Rapikan: env vars, error handling, dokumentasi swap model.

## 6. Definisi selesai (MVP)
Bisa upload citra → lihat hasil deteksi (mock) → dashboard & peta terisi → export laporan.
Mengganti mock ke model asli cukup menyentuh `engine.py` tanpa mengubah frontend/endpoint lain.
