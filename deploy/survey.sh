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

line "Ringkasan"
echo "Periksa di atas: (1) Docker ada & bisa dipakai tanpa sudo,"
echo "(2) port 8000/3000 bebas atau perlu diganti, (3) reverse proxy mana yang"
echo "sudah ada — SawitScan akan menumpang di situ, bukan menggantikannya."
