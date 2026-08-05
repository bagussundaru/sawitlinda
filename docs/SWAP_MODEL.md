# Mengganti Model (Swap Model)

## Prinsip
Web **tidak** melatih model. Training & labeling adalah tanggung jawab klien
(Roboflow + notebook). Web hanya menerima berkas model **final**.

## Satu titik sentuh
Seluruh aplikasi memanggil `run_inference()` di
[`backend/app/inference/engine.py`](../backend/app/inference/engine.py).
Mengganti model = mengubah isi fungsi itu saja. Signature dan bentuk payload
**tidak boleh berubah** — kalau berubah, frontend dan endpoint lain ikut rusak.

`run_inference()` mengembalikan bagian yang berasal dari model saja:

```python
{"detections": [
    {"bbox": [x, y, w, h], "condition": str, "severity": str,
     "confidence": float, "gps": {"lat": float, "lng": float} | None},
]}
```

`condition` berisi label dari tabel kondisi di bawah; `severity` salah satu dari
`sehat | ringan | sedang | berat`.

`image_id`, `filename`, `captured_at`, dan `summary` dirakit oleh pemanggil —
model tidak mengetahui data itu.

## Langkah — SUDAH DIKERJAKAN untuk model saat ini

Model YOLOv8m klien (`best.pt`, 4 kelas, ultralytics 8.4.115) sudah terpasang.
Untuk model berikutnya, langkahnya jauh lebih singkat dari rencana semula:

1. Taruh berkas model di `backend/models/` (folder itu diabaikan git).
2. Set `MODEL_PATH=models/best.pt` di `backend/.env`. Path relatif diselesaikan
   terhadap `backend/`, jadi tidak bergantung direktori kerja.
3. Selesai. `run_inference()` **tidak perlu diubah lagi** — ia memilih sendiri
   antara model dan mock berdasarkan ada tidaknya berkas itu.

Yang perlu diperiksa hanya bila daftar kelas berubah: selaraskan `CLASS_LABELS`
di [`conditions.py`](../backend/app/inference/conditions.py). Nama kelas dibaca
dari model (`model.names`), bukan diasumsikan urutannya — model saat ini memakai
urutan alfabetis `dead, healthy, small, yellow`.

Verifikasi: `pytest` lalu `python scripts/check_postgres.py`.

### Dua hal yang BUKAN keluaran model

**Keparahan.** Model ini detektor 4 kelas tanpa kepala keparahan, dan dataset
belum memuat labelnya. `severity` diturunkan dari aturan tetap di
[`yolo.py`](../backend/app/inference/yolo.py): `healthy`→sehat, `yellow`→ringan,
`small`→sedang, `dead`→berat. `GET /api/system` melaporkannya sebagai
`severity_source: "rule"`. Ganti aturan itu begitu label keparahan tersedia.

**Koordinat per pohon.** Model mengembalikan kotak dalam piksel. Mengubahnya jadi
lintang/bujur butuh skala tanah (meter per piksel), yang tidak ada di dalam citra.
Skala dihitung dari **luas area yang diisi operator saat mengunggah**. Tanpa luas
itu, deteksi sengaja tidak diberi koordinat — peta kosong lebih baik daripada
titik yang salah tempat.

---

## ⚠️ Ketidakcocokan dataset vs daftar penyakit

Dataset klien —
[`heras-workspace/oil-palm-central-kalimantan`](https://universe.roboflow.com/heras-workspace/oil-palm-central-kalimantan),
Object Detection, 1.007 citra, 3 versi — memiliki **4 kelas**:

| Kelas model | Label di UI | Ciri dari citra atas | Interpretasi | Tindakan |
| --- | --- | --- | --- | --- |
| `healthy` | Sehat | Tajuk hijau rapat, ukuran pelepah normal | Tanaman sehat | Tidak ada tindakan |
| `yellow` | Menguning | Tajuk didominasi warna kuning atau hijau pucat | Dugaan defisiensi nutrisi | Periksa unsur hara, lakukan pemupukan susulan (N/Mg/K) |
| `dead` | Mati/stres | Tajuk mengering, berwarna cokelat, pelepah mati | Pelepah telah mati atau tanaman mengalami stres berat | Lakukan pemangkasan atau inspeksi lapangan lebih lanjut |
| `small` | Kerdil | Tajuk berukuran lebih kecil dibanding tanaman sekitar | Pertumbuhan tanaman terhambat | Review kembali pemupukan dan evaluasi kondisi tanah |

Tabel ini tersimpan di
[`backend/app/inference/conditions.py`](../backend/app/inference/conditions.py), disajikan
lewat `GET /api/conditions`, dan dipakai sebagai bagian "Rekomendasi tindakan" pada
laporan PDF.

Kelas-kelas ini adalah **kondisi pohon**, bukan diagnosis penyakit. Daftar penyakit
di `CLAUDE.md` (Ganoderma, karat daun, bercak daun Curvularia, defisiensi hara)
**tidak ada di dataset ini**, sehingga model yang dilatih atasnya tidak akan pernah
mengeluarkan nama-nama tersebut.

Konsekuensinya:

- Sistem melaporkan kondisi tanaman apa adanya. Istilah di database, API, dan UI
  memakai **`condition`** — bukan `disease` — agar tidak menjanjikan diagnosis yang
  tidak bisa dihasilkan model. Migrasi `0002` yang melakukan penggantian nama itu.
- **Tingkat keparahan tidak ada di dataset.** Menurut `CLAUDE.md`, keparahan berasal
  dari kepala klasifikasi terpisah (Swin + MTL) — label untuk itu harus disediakan
  klien. Untuk sementara `dead` selalu dipetakan ke `berat`, sisanya diacak oleh mock.

Satu titik temu: `yellow` → "Dugaan defisiensi nutrisi" bersinggungan dengan
"Defisiensi hara" pada daftar di `CLAUDE.md`. Tiga penyakit lainnya tidak punya
padanan di dataset.

### Perlu keputusan klien
Proposal §5 sudah mencatat dua di antaranya sebagai hal yang perlu disepakati
sebelum pengerjaan — lihat
[`Proposal_Deteksi_Penyakit_Sawit.pdf`](Proposal_Deteksi_Penyakit_Sawit.pdf).

1. Apakah cakupan memang deteksi **kondisi tanaman** (bukan diagnosis penyakit)?
   Sistem saat ini sudah memakai istilah "kondisi" secara konsisten; proposal masih
   memakai "penyakit" dan perlu disamakan.
2. Kalau diagnosis penyakit tetap diinginkan, dataset baru dengan label penyakit
   harus dibuat — itu pekerjaan labeling di sisi klien, bukan pekerjaan web.
3. Bagaimana label keparahan (ringan/sedang/berat) akan disediakan? Dataset saat ini
   tidak memuatnya, padahal `summary.severe`, warna titik di peta, dan kepala MTL
   semuanya bergantung padanya.
