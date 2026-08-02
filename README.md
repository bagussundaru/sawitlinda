# SawitScan AI

Aplikasi web untuk **deteksi & klasifikasi penyakit kelapa sawit dari citra UAV (drone)**.
Web ini adalah lapisan **inference & pelaporan** di atas model AI yang dilatih terpisah
(YOLOv8 → Swin Transformer + Multi-Task Learning).

> **Batas scope:** web ini tidak melatih model. Training & labeling adalah tanggung jawab
> klien. Web menerima berkas model final (`.pt` / ONNX) yang cukup di-swap saat retrain —
> lihat [`docs/SWAP_MODEL.md`](docs/SWAP_MODEL.md).

Spesifikasi teknis & urutan pengerjaan: [`SPEC.md`](SPEC.md).

## Status

Tahap **1–3** dan **6 (export)** selesai: seluruh backend MVP sudah berjalan.
Layar frontend (tahap 4–5) menunggu `docs/SawitScan_Prototype.html`.

| Endpoint | Keterangan |
| --- | --- |
| `POST /api/upload` | Unggah batch citra; GPS & waktu pemotretan diambil dari EXIF |
| `POST /api/analyze/{image_id}` | Jalankan inference, simpan hasil (analisis ulang menimpa hasil lama) |
| `GET /api/results` | Riwayat unggahan, terbaru dulu |
| `GET /api/results/{image_id}` | Satu hasil deteksi lengkap |
| `GET /api/dashboard` | Agregat lintas citra |
| `GET /api/conditions` | Tabel acuan kondisi pohon: ciri, interpretasi, tindakan |
| `GET /api/results/{image_id}/export.csv` | Unduh CSV, satu baris per pohon |
| `GET /api/results/{image_id}/export.pdf` | Unduh laporan PDF |

> **Inference masih MOCK.** `run_inference()` menghasilkan deteksi acak yang realistis
> dan deterministik per citra. Lihat [`docs/SWAP_MODEL.md`](docs/SWAP_MODEL.md).

> Tes memakai SQLite sehingga cepat dan tanpa dependensi. Untuk memastikan semuanya
> juga benar di PostgreSQL, jalankan `python scripts/check_postgres.py` — skrip itu
> menyalakan PostgreSQL sementara sendiri, tanpa Docker dan tanpa instalasi ke sistem.

## Prasyarat

- Python 3.11+
- Node.js 20+
- Docker Desktop (untuk PostgreSQL)

## Menjalankan (dev)

### 1. Database

```bash
docker compose up -d
```

PostgreSQL 16 jalan di `localhost:5432` (user/pass/db default: `sawitscan`).
Data disimpan di volume `pgdata` sehingga tetap ada setelah container mati.

### 2. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
```

Aktifkan virtualenv — PowerShell: `.venv\Scripts\Activate.ps1`, Git Bash: `source .venv/Scripts/activate`.

```bash
pip install -r requirements.txt
```

Salin konfigurasi lalu sesuaikan bila perlu:

```bash
cp .env.example .env
```

Terapkan migrasi database:

```bash
alembic upgrade head
```

Jalankan:

```bash
uvicorn app.main:app --reload --port 8000
```

- Cek kesehatan: <http://localhost:8000/health>
- Dokumentasi API otomatis: <http://localhost:8000/docs>

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Buka <http://localhost:3000>.

## Tes

```bash
cd backend
pytest
```

Verifikasi terhadap PostgreSQL sungguhan (alur upload → analyze → results →
dashboard → export):

```bash
python scripts/check_postgres.py
```

## Struktur

```
backend/
  app/
    main.py              aplikasi FastAPI + CORS
    config.py            konfigurasi dari environment (tanpa kredensial hardcoded)
    db.py                engine & session SQLAlchemy
    routers/             endpoint REST (tahap 2–3)
    services/            ekstraksi EXIF GPS, dll. (tahap 2)
    inference/
      engine.py          run_inference() — SATU-SATUNYA titik sentuh model
  storage/               citra hasil unggah (tidak masuk git)
  tests/
frontend/
  src/
    app/                 halaman (App Router)
    components/          komponen UI (tahap 4–5)
    lib/api.ts           seluruh panggilan REST terpusat di sini
    types/detection.ts   cerminan kontrak JSON
docs/                    proposal, prototype UI, panduan swap model
```

## Konvensi

- Seluruh label & teks UI berbahasa **Indonesia**; komentar kode & nama variabel berbahasa Inggris.
- Kredensial selalu lewat environment variable — jangan pernah di-hardcode.
- Kontrak JSON hasil deteksi didefinisikan di `CLAUDE.md` dan dicerminkan di
  `backend/app/schemas.py` serta `frontend/src/types/detection.ts`. Ubah ketiganya bersamaan.
