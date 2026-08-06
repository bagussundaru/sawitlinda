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

Tampilan mengikuti [`docs/SawitScan_Redesign.html`](docs/SawitScan_Redesign.html).

| Layar | Rute |
| --- | --- |
| Dashboard | `/` |
| Hasil deteksi (riwayat) | `/riwayat` |
| Hasil deteksi (satu citra) | `/hasil/{image_id}` |
| Peta sebaran (Leaflet) | `/peta` |
| Unggah | `/unggah` |
| Proses (animasi pipeline) | `/proses?ids=…` |
| Laporan | `/laporan` |
| Evaluasi | `/evaluasi` |
| Pengaturan | `/pengaturan` |

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
| `POST /api/analyze/{image_id}/ai` | Penilaian tingkat citra oleh model vision (opsional) |
| `POST /api/evaluate` | Evaluasi terhadap anotasi ground truth (YOLOv8 .zip / COCO .json) |
| `GET /api/evaluations` | Riwayat evaluasi |
| `GET /api/results/{image_id}/export.csv` | Unduh CSV, satu baris per pohon |
| `GET /api/results/{image_id}/export.pdf` | Unduh laporan PDF |

> **Model terlatih sudah terintegrasi.** Isi `MODEL_PATH` dengan lokasi berkas
> `.pt` dan sistem otomatis memakainya; tanpa berkas itu ia jatuh ke generator
> mock dan tetap berjalan penuh. `GET /api/system` melaporkan mana yang aktif.
> Lihat [`docs/SWAP_MODEL.md`](docs/SWAP_MODEL.md).

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
| `MODEL_PATH` | kosong | Berkas model terlatih, mis. `models/best.pt`. Kosong = pakai mock. |
| `NEBIUS_API_KEY` | kosong | Kunci Nebius Token Factory. Kosong = analisis AI mati. |
| `NEBIUS_MODEL` | `Qwen/Qwen2.5-VL-72B-Instruct` | Model vision yang dipakai. |

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

## Arsitektur

Rancangan sistem lengkap — komponen, alur data, model data, keputusan rancangan
beserta alasannya, kinerja terukur, dan batasan yang diketahui:
[`docs/ARSITEKTUR.md`](docs/ARSITEKTUR.md).

## Audit terhadap proposal

Pemeriksaan butir demi butir proposal klien terhadap sistem yang berjalan —
apa yang sudah selesai, apa yang tertahan, dan apa yang masih perlu diputuskan:
[`docs/AUDIT_PROPOSAL.md`](docs/AUDIT_PROPOSAL.md).

## Evaluasi model

Layar **Evaluasi** membandingkan deteksi yang tersimpan dengan anotasi acuan yang
diunggah, lalu menghitung **mAP@50, presisi/recall/F1 per kelas, dan confusion
matrix** — angka yang biasanya dituntut pada bab hasil.

Menerima ekspor **YOLOv8** (`.zip` berisi `labels/` + `data.yaml`) maupun **COCO
JSON**, langsung dari Roboflow. Pencocokan berdasarkan nama berkas citra.

Tiap hasil menyimpan keadaan sistem saat dijalankan (`mock` atau `model`),
sehingga angka dari inference mock tidak akan pernah tertukar dengan angka model
sungguhan.

## Analisis AI (opsional)

Di samping deteksi per pohon, satu citra dapat dinilai secara keseluruhan oleh
model vision lewat **Nebius Token Factory**: kondisi apa yang dominan, perkiraan
bagian tanaman yang bermasalah, ringkasan, dan saran tindakan.

Ini **pendamping, bukan pengganti** YOLOv8 + Swin. Model vision umum tidak dapat
melokalisasi puluhan pohon satu per satu; yang dinilainya adalah citra secara
utuh. Selisih antara perkiraannya dan hasil deteksi ditampilkan apa adanya —
selisih besar berarti citra layak diperiksa manual.

Aktifkan dengan mengisi `NEBIUS_API_KEY` di `backend/.env`, lalu tekan
**Jalankan** pada kartu "Analisis AI" di layar hasil deteksi. Tanpa kunci,
seluruh fitur lain tetap berjalan normal.

## Syarat titik muncul di peta

Sebuah pohon hasil deteksi baru diplot di peta bila citranya memenuhi **dua**
syarat sekaligus:

1. **Koordinat citra** — dari EXIF GPS (foto drone asli yang belum diedit ulang),
   atau diisi manual saat unggah. EXIF selalu menang bila keduanya ada.
2. **Luas area tercakup (ha)** — dari sinilah skala tanah (meter per piksel)
   dihitung untuk menempatkan tiap pohon dari kotak deteksinya.

Tanpa luas area, citra tetap dianalisis dan bounding box tetap tampil di layar
hasil, tapi deteksinya sengaja tidak diberi koordinat: peta kosong lebih baik
daripada titik yang salah tempat.

## Membuktikan model bekerja

Cara pembuktian paling kuat memakai dataset klien sendiri: split **test** berisi
citra kebun sungguhan yang tidak pernah dilihat model saat pelatihan, lengkap
dengan anotasi acuannya.

Unduh dari Roboflow (versi 3, format **YOLOv8**), lalu:

```bash
python scripts/validate_with_dataset.py /path/dataset.zip
```

Skrip mengunggah citra split test, menganalisisnya, lalu mengirim arsip yang sama
ke `/api/evaluate`. Label untuk citra yang tidak diunggah otomatis terlewat, jadi
arsipnya tidak perlu dibongkar. Keluarannya mAP@50, presisi/recall per kelas, dan
confusion matrix — tersimpan dan dapat dibuka kembali di layar Evaluasi.

## Data demo

Untuk mengisi sistem dengan kebun contoh yang menyerupai keadaan sebenarnya —
5 blok, 23 bingkai UAV bersebelahan, pola tanam segitiga 9 m, dan persoalan yang
mengelompok seperti bercak di lapangan:

```bash
python scripts/seed_demo.py
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
