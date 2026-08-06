"""Buat atau ganti kata sandi pengguna aplikasi.

    python scripts/create_user.py

Kata sandi diminta lewat getpass — tidak muncul di layar, tidak masuk riwayat
shell, dan tidak pernah menjadi argumen perintah (argumen terlihat oleh siapa
pun yang menjalankan `ps` di server yang sama).

Yang tersimpan hanya turunan scrypt-nya. Kata sandi yang hilang tidak dapat
dipulihkan — jalankan skrip ini lagi untuk menggantinya.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import auth  # noqa: E402

MIN_PANJANG = 10


def main() -> int:
    username = input("Nama pengguna: ").strip().lower()
    if not username:
        print("Nama pengguna tidak boleh kosong.")
        return 1

    sandi = getpass.getpass("Kata sandi: ")
    if len(sandi) < MIN_PANJANG:
        print(f"Kata sandi minimal {MIN_PANJANG} karakter.")
        return 1
    if sandi != getpass.getpass("Ulangi kata sandi: "):
        print("Kata sandi tidak sama.")
        return 1

    nama_lengkap = input("Nama lengkap (opsional): ").strip() or None

    with SessionLocal() as db:
        ada = db.get(models.User, username)
        if ada is not None:
            if input(f"'{username}' sudah ada. Ganti kata sandinya? [y/N] ").lower() != "y":
                print("Dibatalkan.")
                return 1
            ada.password_hash = auth.hash_password(sandi)
            if nama_lengkap:
                ada.full_name = nama_lengkap
            db.commit()
            print(f"Kata sandi '{username}' diganti.")
        else:
            auth.create_user(db, username, sandi, nama_lengkap)
            print(f"Pengguna '{username}' dibuat.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
