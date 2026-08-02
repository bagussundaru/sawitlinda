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
    {"bbox": [x, y, w, h], "disease": str, "severity": str,
     "confidence": float, "gps": {"lat": float, "lng": float} | None},
]}
```

`image_id`, `filename`, `captured_at`, dan `summary` dirakit oleh pemanggil —
model tidak mengetahui data itu.

## Langkah
1. Simpan berkas model (`.pt` / ONNX) di luar repo, mis. `backend/models/`.
2. Set `MODEL_PATH` di `backend/.env`.
3. Ubah isi `run_inference()`: load model → `predict` → petakan output ke bentuk di atas.
4. Selaraskan `CLASS_LABELS` di
   [`backend/app/inference/diseases.py`](../backend/app/inference/diseases.py)
   dengan label model.
5. `pytest` lalu `python scripts/check_postgres.py`. Endpoint dan frontend tidak disentuh.

---

## ⚠️ Ketidakcocokan dataset vs daftar penyakit

Dataset klien —
[`heras-workspace/oil-palm-central-kalimantan`](https://universe.roboflow.com/heras-workspace/oil-palm-central-kalimantan),
Object Detection, 1.007 citra, 3 versi — memiliki **4 kelas**:

| Kelas model | Label di UI | Ciri dari citra atas | Interpretasi | Tindakan |
| --- | --- | --- | --- | --- |
| `healthy` | Sehat | Tajuk hijau rapat, ukuran pelepah normal | Tanaman sehat | Tidak ada tindakan |
| `yellow` | Daun menguning | Tajuk dominan kuning/hijau pucat | Dugaan defisiensi nutrisi | Cek unsur hara, pemupukan N/Mg/K |
| `dead` | Pohon mati | Tajuk kering, coklat, pelepah mati | Pelepah mati atau tanaman mengalami stres | Pemangkasan/inspeksi lebih lanjut |
| `small` | Pertumbuhan kerdil | Tajuk kecil dibanding tanaman sekitar | Pertumbuhan terhambat | Evaluasi pemupukan dan kondisi tanah |

Tabel ini tersimpan di
[`backend/app/inference/diseases.py`](../backend/app/inference/diseases.py), disajikan
lewat `GET /api/conditions`, dan dipakai sebagai bagian "Rekomendasi tindakan" pada
laporan PDF.

Kelas-kelas ini adalah **kondisi pohon**, bukan diagnosis penyakit. Daftar penyakit
di `CLAUDE.md` (Ganoderma, karat daun, bercak daun Curvularia, defisiensi hara)
**tidak ada di dataset ini**, sehingga model yang dilatih atasnya tidak akan pernah
mengeluarkan nama-nama tersebut.

Konsekuensinya:

- Sistem sekarang melaporkan kondisi pohon apa adanya. Kolom pada kontrak JSON tetap
  bernama `disease` demi kompatibilitas, isinya label pada tabel di atas.
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

1. Apakah cakupan memang deteksi **kondisi** pohon (bukan diagnosis penyakit)? Kalau
   ya, istilah "penyakit" di UI dan proposal sebaiknya diganti jadi "kondisi".
2. Kalau diagnosis penyakit tetap diinginkan, dataset baru dengan label penyakit
   harus dibuat — itu pekerjaan labeling di sisi klien, bukan pekerjaan web.
3. Bagaimana label keparahan (ringan/sedang/berat) akan disediakan? Dataset saat ini
   tidak memuatnya, padahal `summary.severe`, warna titik di peta, dan kepala MTL
   semuanya bergantung padanya.
