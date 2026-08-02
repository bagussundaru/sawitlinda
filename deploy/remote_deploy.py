#!/usr/bin/env python3
"""Survei dan deploy SawitScan ke VM lewat SSH.

Password diminta saat skrip berjalan lewat getpass — TIDAK pernah ditulis di
berkas ini, tidak lewat argumen baris perintah (yang akan tersimpan di riwayat
shell), dan tidak dicetak ke layar atau log.

Butuh paramiko:

    pip install paramiko

Pemakaian:

    # Hanya survei — tidak mengubah apa pun di server
    python deploy/remote_deploy.py --host 43.157.197.253 --user ubuntu

    # Survei lalu deploy
    python deploy/remote_deploy.py --host 43.157.197.253 --user ubuntu --deploy

Lebih disarankan memakai kunci SSH daripada password:

    ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@<host>
    python deploy/remote_deploy.py --host <host> --user ubuntu --key ~/.ssh/id_ed25519
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

REPO_URL = "https://github.com/bagussundaru/sawitlinda.git"
APP_DIR = "sawitscan"
COMPOSE = f"docker compose -p sawitscan -f docker-compose.prod.yml"

#: Perintah survei. Semuanya HANYA MEMBACA — tidak memasang, mengubah,
#: menghentikan, atau menghapus apa pun di server.
SURVEY = [
    ("Sistem", "cat /etc/os-release | head -2; uname -r; uptime -p"),
    ("Memori & disk", "free -h | head -2; echo; df -h / | head -2; echo CPU: $(nproc) core"),
    ("Docker", "docker --version 2>&1; docker compose version 2>&1 | head -1"),
    ("Container berjalan", "docker ps --format '{{.Names}}\\t{{.Image}}\\t{{.Ports}}' 2>&1"),
    (
        "Bentrok nama SawitScan",
        "for n in sawitscan-db sawitscan-backend sawitscan-frontend; do "
        "if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx $n; "
        "then echo \"BENTROK: $n\"; else echo \"aman: $n\"; fi; done",
    ),
    ("Port didengarkan", "ss -tuln 2>/dev/null | grep LISTEN | head -30"),
    (
        "Port yang dibutuhkan",
        "for p in 8000 3000; do if ss -tuln 2>/dev/null | grep -q \":$p \"; "
        "then echo \"TERPAKAI: $p\"; else echo \"bebas: $p\"; fi; done",
    ),
    (
        "Reverse proxy",
        "systemctl is-active nginx 2>&1; ls -1 /etc/nginx/sites-enabled 2>/dev/null",
    ),
]


def connect(host: str, user: str, key: str | None, port: int):
    try:
        import paramiko
    except ImportError:
        sys.exit("Butuh paramiko:  pip install paramiko")

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    if key:
        client.connect(host, port=port, username=user, key_filename=key, timeout=20)
        return client

    # Diminta di sini, di terminal Anda. Tidak disimpan ke mana pun.
    password = getpass.getpass(f"Password SSH untuk {user}@{host}: ")
    client.connect(
        host,
        port=port,
        username=user,
        password=password,
        timeout=20,
        look_for_keys=False,
        allow_agent=False,
    )
    return client, password


def run(client, command: str, sudo_password: str | None = None) -> tuple[int, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=600, get_pty=bool(sudo_password))
    if sudo_password:
        stdin.write(sudo_password + "\n")
        stdin.flush()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return stdout.channel.recv_exit_status(), (out + err).strip()


def survey(client) -> None:
    print("\n=== SURVEI VM (hanya membaca) ===")
    for title, command in SURVEY:
        _, output = run(client, command)
        print(f"\n-- {title} --")
        print(output or "(kosong)")


def deploy(client, env_file: Path) -> None:
    if not env_file.is_file():
        sys.exit(
            f"Berkas {env_file} tidak ada. Salin deploy/.env.prod.example, isi, "
            "lalu tunjuk dengan --env-file."
        )

    print("\n=== DEPLOY ===")

    steps = [
        ("Ambil kode", f"test -d {APP_DIR}/.git && (cd {APP_DIR} && git pull) "
                       f"|| git clone {REPO_URL} {APP_DIR}"),
    ]
    for label, command in steps:
        code, output = run(client, command)
        print(f"\n-- {label} --\n{output}")
        if code != 0:
            sys.exit(f"Gagal pada langkah: {label}")

    # .env dikirim lewat SFTP, tidak lewat baris perintah, agar isinya tidak
    # muncul di daftar proses atau riwayat shell di server.
    print("\n-- Kirim .env --")
    sftp = client.open_sftp()
    sftp.put(str(env_file), f"{APP_DIR}/.env")
    sftp.chmod(f"{APP_DIR}/.env", 0o600)
    sftp.close()
    print("terkirim, mode 600")

    for label, command in [
        ("Build & jalankan", f"cd {APP_DIR} && {COMPOSE} up -d --build"),
        ("Status", f"cd {APP_DIR} && {COMPOSE} ps"),
        ("Health check", "sleep 12; curl -s http://127.0.0.1:8000/health"),
    ]:
        code, output = run(client, command)
        print(f"\n-- {label} --\n{output}")
        if code != 0:
            sys.exit(f"Gagal pada langkah: {label}")

    print(
        "\nSelesai. Langkah berikutnya (butuh sudo, jalankan sendiri di server):\n"
        f"  sudo cp {APP_DIR}/deploy/nginx-sawitscan.conf /etc/nginx/sites-available/sawitscan\n"
        "  sudo nano /etc/nginx/sites-available/sawitscan   # ganti server_name\n"
        "  sudo ln -s /etc/nginx/sites-available/sawitscan /etc/nginx/sites-enabled/\n"
        "  sudo nginx -t && sudo systemctl reload nginx"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--key", help="Path kunci privat SSH (lebih disarankan)")
    parser.add_argument("--deploy", action="store_true", help="Deploy setelah survei")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Berkas .env produksi yang akan dikirim ke server",
    )
    args = parser.parse_args()

    result = connect(args.host, args.user, args.key, args.port)
    client = result[0] if isinstance(result, tuple) else result

    try:
        survey(client)
        if args.deploy:
            deploy(client, args.env_file)
        else:
            print("\nSurvei selesai. Tambahkan --deploy untuk memasang.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
