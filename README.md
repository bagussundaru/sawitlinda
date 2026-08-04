# SawitScan AI

Aplikasi web untuk **deteksi & klasifikasi penyakit kelapa sawit dari citra UAV (drone)**.
Web ini adalah lapisan **inference & pelaporan** di atas model AI yang dilatih terpisah
(YOLOv8 → Swin Transformer + Multi-Task Learning).

> **Batas scope:** web ini tidak melatih model. Training & labeling adalah tanggung jawab
> klien. Web menerima berkas model final (`.pt` / ONNX) yang cukup di-swap saat retrain —
> lihat [`docs/SWAP_MODEL.md`](docs/SWAP_MODEL.md).

Spesifikasi teknis & urutan pengerjaan: [`SPEC.md`](SPEC.md).

## Status

**Tahap 1–7 selesai** — MVP lengkap: unggah citra → hasil deteksi (mock) → dashboard
& peta → export laporan.

Tampilan mengikuti [`docs/SawitScan_Prototype.html`](docs/SawitScan_Prototype.html).

| Layar | Rute |
| --- | --- |
| Upload | `/` |
| Proses (animasi pipeline) | `/proses?ids=…` |
| Hasil deteksi | `/hasil/{image_id}` |
| Riwayat | `/riwayat` |
| Dashboard | `/dashboard` |
| Peta sebaran (Leaflet) | `/peta` |

| Endpoint | Keterangan |
| --- | --- |
| `POST /api/upload` | Unggah batch citra; GPS & waktu pemotretan diambil dari EXIF |
| `POST /api/analyze/{image_id}` | Jalankan inference, simpan hasil (analisis ulang menimpa hasil lama) |
| `GET /api/results` | Riwayat unggahan, terbaru dulu |
| `GET /api/results/{image_id}` | Satu hasil deteksi lengkap |
| `GET /api/dashboard` | Agregat lintas citra |
| `GET /api/blocks` | Daftar blok kebun beserta jumlah citra, pohon, dan luas |
| `GET /api/system` | Status sistem: mode inference, batas unggah, jumlah kelas |
| `GET /api/conditions` | Tabel acuan kondisi pohon: ciri, interpretasi, tindakan |
| `GET /api/images/{image_id}/file` | Berkas citra asli, untuk digambari bbox |
| `GET /api/map` | Seluruh deteksi ber-GPS lintas citra, untuk peta |
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

## Konfigurasi

Seluruh kredensial lewat environment variable — tidak ada yang di-hardcode.
Salin `backend/.env.example` ke `backend/.env`.

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL lokal | Koneksi database. **Wajib diganti di produksi.** |
| `CORS_ORIGINS` | `http://localhost:3000` | Asal frontend yang diizinkan, dipisah koma. **Wajib diganti di produksi.** |
| `STORAGE_DIR` | `storage` | Lokasi citra terunggah, relatif terhadap `backend/`. |
| `MAX_UPLOAD_MB` | `50` | Batas ukuran satu citra. |
| `MODEL_PATH` | kosong | Berkas model terlatih; belum dipakai selama inference mock. |

Frontend: `NEXT_PUBLIC_API_URL` di `frontend/.env.local` (default `http://localhost:8000`).

## Penanganan galat

Setiap kegagalan API mengembalikan bentuk yang sama — `{"detail": "<pesan>"}` —
dengan pesan berbahasa Indonesia yang bisa ditindaklanjuti operator. Rincian teknis
(stack trace, galat validasi Pydantic) masuk ke log, bukan ke layar pengguna.

| Kode | Kapan muncul |
| --- | --- |
| `400` | Format berkas tidak didukung |
| `404` | Citra tidak ditemukan |
| `409` | Citra belum dianalisis |
| `410` | Berkas citra hilang dari penyimpanan |
| `413` | Ukuran citra melebihi `MAX_UPLOAD_MB` |
| `422` | Permintaan tidak valid |
| `503` | Database tidak dapat diakses |

`GET /health` melakukan kueri nyata ke database, bukan sekadar menjawab "ok".

## Deploy

Panduan lengkap: [`docs/DEPLOY.md`](docs/DEPLOY.md). Dirancang untuk VM yang sudah
menjalankan aplikasi lain — semua sumber daya berawalan `sawitscan`, PostgreSQL tidak
mem-publish port ke host, dan nginx ditambahi site baru alih-alih diganti.

Selalu jalankan survei (hanya membaca, tidak mengubah apa pun) sebelum memasang:

```bash
bash deploy/survey.sh
```

## Presentasi

Prompt siap pakai untuk membuat deck panduan penggunaan ada di
[`docs/PROMPT_PRESENTASI.md`](docs/PROMPT_PRESENTASI.md), lengkap dengan screenshot
tiap layar di [`docs/screenshots/`](docs/screenshots/).

## Konvensi

- Seluruh label & teks UI berbahasa **Indonesia**; komentar kode & nama variabel berbahasa Inggris.
- Kredensial selalu lewat environment variable — jangan pernah di-hardcode.
- Kontrak JSON hasil deteksi didefinisikan di `CLAUDE.md` dan dicerminkan di
  `backend/app/schemas.py` serta `frontend/src/types/detection.ts`. Ubah ketiganya bersamaan.
- Yang dideteksi sistem adalah **kondisi tanaman** (sehat, menguning, mati/stres,
  kerdil), bukan diagnosis penyakit — itulah isi dataset klien. Istilah
  "penyakit" hanya dipakai untuk judul proyek. Lihat `docs/SWAP_MODEL.md`.
