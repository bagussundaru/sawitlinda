"""Autentikasi: hashing password, sesi, dan dependency untuk melindungi route.

Password di-hash dengan scrypt dari pustaka standar. Dipilih daripada bcrypt
karena tidak menambah dependensi ke image produksi, sementara kekuatannya
memadai: scrypt dirancang mahal di memori, sehingga serangan dengan GPU tidak
memberi keuntungan sebesar pada fungsi yang hanya mahal di CPU.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db

logger = logging.getLogger("sawitscan")

COOKIE_NAME = "sawitscan_session"

#: Parameter scrypt. n harus pangkat dua; 2^15 menahan ±100 ms per percobaan
#: pada CPU biasa — tak terasa saat login, mahal saat ditebak berulang.
_N, _R, _P = 2**15, 8, 1
_SALT_BYTES = 16
_KEY_LEN = 32


# --- Password ---------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    turunan = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LEN
    )
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${turunan.hex()}"


def verify_password(password: str, disimpan: str) -> bool:
    try:
        skema, n, r, p, salt_hex, hash_hex = disimpan.split("$")
        if skema != "scrypt":
            return False
        turunan = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(hash_hex) // 2,
        )
    except (ValueError, TypeError):
        # Hash rusak atau format tak dikenal: perlakukan sebagai gagal, jangan
        # sampai galat parsing menjadi jalan masuk.
        return False
    return hmac.compare_digest(turunan.hex(), hash_hex)


# --- Pengguna ---------------------------------------------------------------
def create_user(db: Session, username: str, password: str, full_name: str | None = None):
    pengguna = models.User(
        username=username.strip().lower(),
        password_hash=hash_password(password),
        full_name=full_name,
    )
    db.add(pengguna)
    db.commit()
    return pengguna


def user_count(db: Session) -> int:
    return db.query(models.User).count()


def authenticate(db: Session, username: str, password: str) -> models.User | None:
    pengguna = db.get(models.User, username.strip().lower())
    if pengguna is None:
        # Tetap hitung hash walau pengguna tidak ada. Tanpa ini, permintaan untuk
        # nama yang tidak terdaftar dijawab jauh lebih cepat, dan selisihnya
        # cukup untuk memetakan siapa saja yang terdaftar.
        hash_password(password)
        return None
    if not verify_password(password, pengguna.password_hash):
        return None
    pengguna.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return pengguna


# --- Sesi -------------------------------------------------------------------
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(db: Session, username: str, umur_jam: int) -> tuple[str, datetime]:
    """Buat sesi baru. Mengembalikan token mentah — hanya sekali ini ia ada."""
    token = secrets.token_urlsafe(32)
    kedaluwarsa = datetime.now(timezone.utc) + timedelta(hours=umur_jam)
    db.add(
        models.SessionToken(
            token_hash=_hash_token(token), username=username, expires_at=kedaluwarsa
        )
    )
    _bersihkan_kedaluwarsa(db)
    db.commit()
    return token, kedaluwarsa


def end_session(db: Session, token: str) -> None:
    db.execute(
        delete(models.SessionToken).where(models.SessionToken.token_hash == _hash_token(token))
    )
    db.commit()


def _bersihkan_kedaluwarsa(db: Session) -> None:
    db.execute(
        delete(models.SessionToken).where(
            models.SessionToken.expires_at < datetime.now(timezone.utc)
        )
    )


def resolve_session(db: Session, token: str | None) -> models.User | None:
    if not token:
        return None
    sesi = db.get(models.SessionToken, _hash_token(token))
    if sesi is None:
        return None
    kedaluwarsa = sesi.expires_at
    if kedaluwarsa.tzinfo is None:  # SQLite mengembalikan datetime tanpa zona
        kedaluwarsa = kedaluwarsa.replace(tzinfo=timezone.utc)
    if kedaluwarsa < datetime.now(timezone.utc):
        return None
    return db.get(models.User, sesi.username)


# --- Dependency -------------------------------------------------------------
def current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    """Wajibkan sesi yang sah.

    Bila belum ada pengguna sama sekali, permintaan DITOLAK, bukan diloloskan.
    Aplikasi yang terbuka karena pengaturannya belum selesai adalah persis
    keadaan yang hendak dihindari — apalagi kini satu permintaan dapat memicu
    biaya GPU. Cara membuat pengguna pertama ada di pesan galatnya.
    """
    pengguna = resolve_session(db, request.cookies.get(COOKIE_NAME))
    if pengguna is not None:
        return pengguna

    if user_count(db) == 0:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Belum ada pengguna terdaftar. Jalankan `python scripts/create_user.py` "
            "di server untuk membuat akun pertama.",
        )
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Silakan masuk terlebih dahulu.")
