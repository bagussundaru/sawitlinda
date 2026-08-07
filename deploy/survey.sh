#!/usr/bin/env bash
# Survei VM SEBELUM deploy. Skrip ini HANYA MEMBACA — tidak memasang, mengubah,
# menghentikan, atau menghapus apa pun. Aman dijalankan di server yang sedang
# menjalankan aplikasi lain.
#
#   bash deploy/survey.sh
#
# Tujuannya menjawab: apakah Docker tersedia, port mana yang sudah terpakai,
# reverse proxy apa yang sudah ada, dan apakah sumber daya masih cukup.

set -uo pipefail

line() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

line "Sistem"
. /etc/os-release 2>/dev/null && echo "OS       : $PRETTY_NAME"
echo "Kernel   : $(uname -r)"
echo "Uptime   : $(uptime -p 2>/dev/null || uptime)"

line "Sumber daya"
free -h 2>/dev/null | sed -n '1,2p'
echo
df -h / 2>/dev/null | sed -n '1,2p'
echo "CPU      : $(nproc 2>/dev/null) core"

line "Docker"
if have docker; then
  docker --version
  docker compose version 2>/dev/null || echo "docker compose plugin: TIDAK ADA"
  echo
  echo "Container yang sedang jalan:"
  docker ps --format '  {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null \
    || echo "  (tidak bisa membaca — user mungkin belum masuk grup docker)"
  echo
  echo "Nama yang akan dipakai SawitScan — pastikan belum terpakai:"
  for name in sawitscan-db sawitscan-backend sawitscan-frontend; do
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$name"; then
      echo "  BENTROK: $name sudah ada"
    else
      echo "  aman   : $name"
    fi
  done
  echo
  echo "Volume & jaringan bernama sawitscan:"
  docker volume ls --filter name=sawitscan --format '  volume {{.Name}}' 2>/dev/null
  docker network ls --filter name=sawitscan --format '  network {{.Name}}' 2>/dev/null
else
  echo "Docker TIDAK terpasang."
fi

line "Port yang sedang didengarkan"
if have ss; then
  ss -tulpn 2>/dev/null | awk 'NR==1 || /LISTEN/'
elif have netstat; then
  netstat -tulpn 2>/dev/null | grep LISTEN
else
  echo "ss/netstat tidak tersedia."
fi

line "Port yang dibutuhkan SawitScan"
for port in 8000 3000 5432; do
  if (have ss && ss -tuln 2>/dev/null | grep -q ":$port ") \
     || (have netstat && netstat -tuln 2>/dev/null | grep -q ":$port "); then
    echo "  TERPAKAI: $port  -> ubah di .env (BACKEND_PORT / FRONTEND_PORT)"
  else
    echo "  bebas   : $port"
  fi
done
echo "  Catatan: PostgreSQL SawitScan tidak mem-publish port ke host,"
echo "  jadi 5432 yang terpakai aplikasi lain tidak menjadi masalah."

line "Reverse proxy"
for svc in nginx apache2 caddy traefik; do
  if have "$svc" || systemctl list-unit-files 2>/dev/null | grep -q "^$svc"; then
    echo "$svc terpasang — status: $(systemctl is-active "$svc" 2>/dev/null || echo tidak diketahui)"
  fi
done
if [ -d /etc/nginx/sites-enabled ]; then
  echo
  echo "Site nginx yang aktif:"
  ls -1 /etc/nginx/sites-enabled 2>/dev/null | sed 's/^/  /'
  echo "Server name yang sudah dipakai:"
  grep -rhoP '(?<=server_name\s)[^;]+' /etc/nginx/sites-enabled 2>/dev/null | sed 's/^/  /' | sort -u
fi

line "Firewall"
if have ufw; then ufw status 2>/dev/null | head -12; fi

line "Ketahanan reverse proxy"
# Pertanyaannya bukan "apakah proxy jalan", tapi "apakah ia masih BISA start".
# Konfigurasi dengan upstream statis ke container yang sudah mati membuat nginx
# menolak start — dan sekali ia turun, SELURUH situs di VM ikut mati, termasuk
# aplikasi yang tidak ada hubungannya. Ini ditemukan di VM sebelumnya.
if have nginx; then
  echo "nginx -t (host):"
  sudo nginx -t 2>&1 | sed 's/^/  /'
fi
if have docker; then
  for c in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'nginx|caddy|traefik'); do
    echo "nginx -t di container $c:"
    docker exec "$c" nginx -t 2>&1 | sed 's/^/  /'
  done
fi

line "Aplikasi lain di VM ini"
echo "Layanan systemd yang aktif (di luar bawaan):"
systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null   | awk '{print $1}'   | grep -viE '^(systemd|dbus|cron|ssh|rsyslog|snapd|polkit|networkd|resolved|udev|getty|unattended|multipathd|irqbalance|chrony|accounts|user@)'   | sed 's/^/  /'
if have pm2; then
  echo
  echo "Proses PM2:"
  pm2 list 2>/dev/null | sed 's/^/  /'
fi

line "Ruang untuk SawitScan"
# Angka acuan dari deployment yang sudah berjalan: image backend 2,31 GB,
# ketiga container memakai sekitar 153 MB memori saat menganggur, dan proses
# build sendiri butuh beberapa GB sementara.
mem_avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null)
disk_avail_gb=$(df -BG --output=avail / 2>/dev/null | tail -1 | tr -dc '0-9')
echo "Memori tersedia : ${mem_avail_mb:-?} MB   (SawitScan idle ±153 MB)"
echo "Disk tersedia   : ${disk_avail_gb:-?} GB   (image 2,31 GB + ruang build ±4 GB)"
[ "${mem_avail_mb:-0}" -lt 600 ] 2>/dev/null && echo "  PERINGATAN: memori tipis — build bisa memicu OOM killer yang menyasar aplikasi lain."
[ "${disk_avail_gb:-0}" -lt 8 ] 2>/dev/null && echo "  PERINGATAN: disk tipis — build image bisa memenuhi disk dan menjatuhkan aplikasi lain."
echo
echo "Swap:"
swapon --show 2>/dev/null | sed 's/^/  /' || echo "  tidak ada swap"

line "Ringkasan"
echo "Periksa di atas: (1) Docker ada & bisa dipakai tanpa sudo,"
echo "(2) port 8000/3000 bebas atau perlu diganti, (3) reverse proxy mana yang"
echo "sudah ada — SawitScan akan menumpang di situ, bukan menggantikannya."
