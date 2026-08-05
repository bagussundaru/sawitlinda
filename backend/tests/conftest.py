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


@pytest.fixture
def client(settings, tmp_path):
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
