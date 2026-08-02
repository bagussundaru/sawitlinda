# Mengganti Model (Swap Model)

> Dokumen ini diisi lengkap pada tahap 7. Kerangkanya sudah ditetapkan sejak awal
> supaya batas tanggung jawab jelas.

## Prinsip
Web **tidak** melatih model. Training & labeling adalah tanggung jawab klien
(Roboflow + notebook). Web hanya menerima berkas model **final**.

## Satu titik sentuh
Seluruh aplikasi memanggil `run_inference()` di
[`backend/app/inference/engine.py`](../backend/app/inference/engine.py).
Mengganti model = mengubah isi fungsi itu saja. Signature dan bentuk payload
(lihat kontrak JSON di `CLAUDE.md`) **tidak boleh berubah** — kalau berubah,
frontend dan endpoint lain ikut rusak.

## Langkah (ringkas)
1. Simpan berkas model (`.pt` / ONNX) di luar repo, mis. `backend/models/`.
2. Set `MODEL_PATH` di `backend/.env`.
3. Ubah isi `run_inference()`: load model → `predict` → petakan output ke kontrak JSON.
4. Jalankan tes; endpoint dan frontend tidak perlu disentuh.

## Yang masih perlu dikonfirmasi ke klien
- Daftar kelas penyakit final (harus sama persis dengan label dataset).
- Cara model menyatakan tingkat keparahan (ringan | sedang | berat).
