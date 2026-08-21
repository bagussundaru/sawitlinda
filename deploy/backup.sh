#!/usr/bin/env bash
# Cadangan database SawitScan.
#
#   bash deploy/backup.sh            # sekali jalan
#   sudo crontab -e                  # untuk menjadwalkan; lihat docs/DEPLOY.md
#
# Ditulis sebagai dump SQL terkompresi, bukan salinan volume: dump dapat
# dipulihkan ke versi PostgreSQL mana pun dan isinya dapat dibaca mata manusia
# bila perlu diperiksa. Menyalin direktori data PostgreSQL yang sedang hidup
# justru menghasilkan cadangan yang rusak.
#
# TIDAK menyertakan berkas citra. Citra ada di volume storage dan berukuran
# ratusan megabyte; yang tidak tergantikan adalah metadatanya — label, deteksi,
# evaluasi, akun. Citra dapat diunggah ulang, hasil analisis tidak.

set -euo pipefail

PROYEK="${PROYEK:-sawitscan}"
COMPOSE="${COMPOSE:-$HOME/sawitscan/docker-compose.prod.yml}"
TUJUAN="${TUJUAN:-$HOME/sawitscan-backups}"
SIMPAN_HARI="${SIMPAN_HARI:-14}"

DB_USER="${POSTGRES_USER:-sawitscan}"
DB_NAME="${POSTGRES_DB:-sawitscan}"

mkdir -p "$TUJUAN"
BERKAS="$TUJUAN/sawitscan-$(date +%Y%m%d-%H%M%S).sql.gz"

# Ditulis ke berkas sementara lalu dipindahkan: cadangan yang terpotong di
# tengah proses tidak boleh terlihat seperti cadangan yang utuh.
SEMENTARA="$BERKAS.part"

docker compose -p "$PROYEK" -f "$COMPOSE" exec -T db \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists \
    | gzip -9 > "$SEMENTARA"

# pg_dump yang gagal tetap menghasilkan berkas gzip kecil; ukuran diperiksa
# supaya kegagalan tidak lolos sebagai keberhasilan.
UKURAN=$(stat -c%s "$SEMENTARA")
if [ "$UKURAN" -lt 10240 ]; then
    rm -f "$SEMENTARA"
    echo "GAGAL: dump hanya $UKURAN bita — terlalu kecil untuk sah." >&2
    exit 1
fi

mv "$SEMENTARA" "$BERKAS"
echo "Cadangan: $BERKAS ($((UKURAN / 1024)) KB)"

# Buang cadangan yang lebih tua dari batas simpan.
find "$TUJUAN" -name 'sawitscan-*.sql.gz' -mtime "+$SIMPAN_HARI" -delete
echo "Tersimpan: $(find "$TUJUAN" -name 'sawitscan-*.sql.gz' | wc -l) cadangan"
