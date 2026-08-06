"""Login, logout, dan identitas pengguna yang sedang masuk."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.config import Settings, get_settings
from app.db import get_db
from app.services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])

logger = logging.getLogger("sawitscan")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    username: str
    full_name: str | None = None


class AuthState(BaseModel):
    authenticated: bool
    #: False berarti belum ada akun sama sekali; aplikasi tidak dapat dipakai
    #: sampai akun pertama dibuat di server.
    ready: bool
    user: UserOut | None = None


@router.get("/state", response_model=AuthState)
def state(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthState:
    """Dipakai halaman login untuk tahu perlu menampilkan apa.

    Tidak dilindungi — justru inilah yang menjawab "apakah saya sudah masuk".
    """
    pengguna = auth.resolve_session(db, request.cookies.get(auth.COOKIE_NAME))
    return AuthState(
        authenticated=pengguna is not None,
        ready=auth.user_count(db) > 0,
        user=UserOut(username=pengguna.username, full_name=pengguna.full_name)
        if pengguna
        else None,
    )


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    pengguna = auth.authenticate(db, body.username, body.password)
    if pengguna is None:
        # Satu pesan untuk nama yang salah maupun password yang salah: pesan
        # berbeda akan memberi tahu penebak nama mana yang terdaftar.
        logger.warning("Login gagal untuk '%s'", body.username[:32])
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Nama pengguna atau kata sandi salah."
        )

    token, kedaluwarsa = auth.start_session(db, pengguna.username, settings.session_hours)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,  # tidak dapat dibaca JavaScript
        secure=settings.cookie_secure,
        samesite="lax",  # ikut terkirim saat berpindah halaman, tidak pada POST lintas situs
        max_age=settings.session_hours * 3600,
        path="/",
    )
    logger.info("Login berhasil: %s", pengguna.username)
    return UserOut(username=pengguna.username, full_name=pengguna.full_name)


# Tanpa anotasi kembalian: FastAPI memakai anotasi itu sebagai response model,
# dan `-> None` menghasilkan NoneType — sebuah kelas, yang truthy — sehingga
# 204 dianggap punya badan respons dan pendaftaran route gagal.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Hapus sesi di server, bukan hanya cookie di peramban.

    Menghapus cookie saja meninggalkan token yang masih sah di database.
    """
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.end_session(db, token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(pengguna: models.User = Depends(auth.current_user)) -> UserOut:
    return UserOut(username=pengguna.username, full_name=pengguna.full_name)
