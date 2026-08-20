"""Test fixtures.

Tests run against a throwaway SQLite file and a temporary storage directory, so the
suite needs neither Docker nor PostgreSQL. Production still targets PostgreSQL; the
ORM models deliberately use portable column types.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    test_settings = Settings(
        database_url="sqlite://",
        storage_dir=str(tmp_path / "storage"),
        cors_origins="http://localhost:3000",
        # Pekerja latar memakai koneksi database sendiri, di luar jangkauan
        # penggantian dependency — dinyalakan, ia akan menggantung mencoba
        # menghubungi database sungguhan.
        worker_enabled=False,
    )
    # Modul yang mengimpor get_settings langsung memegang rujukan sendiri, jadi
    # menambal app.config saja tidak menjangkau mereka.
    for modul in (
        "app.config",
        "app.routers.upload",
        "app.inference.engine",
    ):
        monkeypatch.setattr(f"{modul}.get_settings", lambda: test_settings)
    return test_settings


@pytest.fixture(autouse=True)
def scrypt_cepat(monkeypatch):
    """Turunkan biaya scrypt selama pengujian.

    Parameter produksi sengaja mahal (±100 ms per hash). Dikalikan ratusan tes
    yang masing-masing login, itu menambah menit ke waktu suite tanpa menguji
    apa pun — yang diuji adalah alurnya, bukan kekuatan parameternya.
    """
    monkeypatch.setattr("app.services.auth._N", 2**8)


@pytest.fixture
def anon_client(settings, tmp_path):
    """Klien tanpa sesi login. Untuk menguji route yang harus tertutup."""
    yield from _bangun_client(settings, tmp_path)


@pytest.fixture
def client(anon_client):
    """Klien yang sudah masuk sebagai pengguna uji.

    Login dijalankan sungguhan, bukan dengan menambal dependency: kalau alur
    autentikasi rusak, seluruh suite ikut merah — dan itu memang yang seharusnya
    terjadi.
    """
    anon_client.post(
        "/api/auth/login", json={"username": "tester", "password": "kata-sandi-uji"}
    ).raise_for_status()
    return anon_client


def _bangun_client(settings, tmp_path):
    from app import models
    from app.services import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Pengguna uji dibuat langsung, bukan lewat API: tidak ada endpoint
    # pendaftaran, dan memang tidak boleh ada.
    with TestingSession() as db:
        auth.create_user(db, "tester", "kata-sandi-uji", "Penguji")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()

