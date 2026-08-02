# Deploy SawitScan AI

Panduan pemasangan di VM Ubuntu **yang sudah menjalankan aplikasi lain**. Seluruh
langkah dirancang agar tidak menyentuh apa pun milik aplikasi lain di server itu.

## Prinsip isolasi

| Hal | Bagaimana SawitScan menghindarinya |
| --- | --- |
| Nama container/volume/jaringan | Semua berawalan `sawitscan`, project name `sawitscan` |
| Port PostgreSQL | **Tidak** di-publish ke host — hanya jaringan internal compose. Instance PostgreSQL lain di VM tidak terganggu |
| Port 8000 / 3000 | Di-bind ke `127.0.0.1` saja, dan bisa diganti lewat `.env` |
| Reverse proxy | Menambah **site baru** di nginx, tidak mengubah/mengganti site yang ada |
| Firewall | Tidak ada aturan baru yang dibutuhkan; yang menghadap internet hanya nginx yang sudah jalan |

## 0. Survei dulu — wajib

Jalankan di server. Skrip ini **hanya membaca**, tidak memasang atau mengubah apa pun:

```bash
bash deploy/survey.sh
```

Baca hasilnya sebelum lanjut:
- Docker + plugin `compose` ada, dan bisa dipakai tanpa `sudo`?
- Port `8000` dan `3000` bebas? Kalau tidak, catat penggantinya.
- Nama `sawitscan-db`, `sawitscan-backend`, `sawitscan-frontend` belum terpakai?
- Reverse proxy apa yang sudah ada, dan domain apa saja yang sudah dipakai?
- Sisa disk & memori cukup? Perlu ± 2 GB disk dan ± 1 GB RAM bebas.

**Jangan lanjut kalau ada yang bentrok.** Ubah dulu port di `.env`.

## 1. Ambil kode

```bash
git clone https://github.com/bagussundaru/sawitlinda.git sawitscan
cd sawitscan
```

## 2. Konfigurasi

```bash
cp deploy/.env.prod.example .env
chmod 600 .env
```

Buat password database yang acak dan isikan ke `.env`:

```bash
openssl rand -base64 24
```

Sesuaikan juga `PUBLIC_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, dan — bila
survei menunjukkan bentrok — `BACKEND_PORT` / `FRONTEND_PORT`.

> `NEXT_PUBLIC_API_URL` ditanam saat image frontend dibangun. Mengubahnya berarti
> membangun ulang image frontend, bukan sekadar `restart`.

## 3. Nyalakan

```bash
docker compose -p sawitscan -f docker-compose.prod.yml up -d --build
```

Migrasi database berjalan otomatis saat container backend start.

Periksa:

```bash
docker compose -p sawitscan -f docker-compose.prod.yml ps
curl -s http://127.0.0.1:8000/health
```

`/health` harus menjawab `{"status":"ok","database":"ok"}`. Kalau `database`
bukan `ok`, jangan lanjut ke nginx — periksa log dulu.

## 4. Reverse proxy

```bash
sudo cp deploy/nginx-sawitscan.conf /etc/nginx/sites-available/sawitscan
# ganti sawit.contoh.id dengan domain Anda
sudo nano /etc/nginx/sites-available/sawitscan
sudo ln -s /etc/nginx/sites-available/sawitscan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

`nginx -t` menguji seluruh konfigurasi termasuk milik aplikasi lain — kalau gagal,
**jangan** reload. `reload` tidak memutus koneksi yang sedang berjalan.

HTTPS:

```bash
sudo certbot --nginx -d sawit.contoh.id
```

## 5. Verifikasi

- Buka `https://<domain>` → layar unggah muncul.
- Unggah satu citra UAV → proses → hasil deteksi tampil dengan bounding box.
- Buka Dashboard dan Peta Sebaran.
- Unduh laporan PDF dan CSV.

## Operasi harian

```bash
# Log
docker compose -p sawitscan -f docker-compose.prod.yml logs -f backend

# Perbarui ke versi terbaru
git pull
docker compose -p sawitscan -f docker-compose.prod.yml up -d --build

# Cadangkan database
docker exec sawitscan-db pg_dump -U sawitscan sawitscan | gzip > backup-$(date +%F).sql.gz

# Cadangkan citra terunggah
docker run --rm -v sawitscan_storage:/data -v "$PWD":/out alpine \
  tar czf /out/storage-$(date +%F).tar.gz -C /data .
```

Menghentikan SawitScan tanpa menyentuh aplikasi lain:

```bash
docker compose -p sawitscan -f docker-compose.prod.yml down
```

`down` tanpa `-v` **tidak** menghapus volume, jadi data dan citra tetap aman.

## Catatan keamanan

- `.env` berisi password database. Jangan pernah di-commit; `chmod 600`.
- Aplikasi **belum punya autentikasi**. Siapa pun yang bisa membuka domainnya bisa
  mengunggah citra dan melihat seluruh hasil. Kalau server dapat diakses publik,
  tambahkan minimal HTTP Basic Auth di nginx, atau batasi dengan `allow`/`deny`,
  sampai autentikasi dibangun.
- Matikan login SSH dengan password, pakai kunci publik:
  `PasswordAuthentication no` di `/etc/ssh/sshd_config`.
