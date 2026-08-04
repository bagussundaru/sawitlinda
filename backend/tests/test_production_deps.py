"""Jaga agar image produksi tidak kehilangan paket yang dipakai saat start.

Dockerfile menyaring paket khusus pengembangan dari requirements.txt. Menambah
dependensi runtime baru tanpa memindahkannya keluar dari bagian dev membuat
container gagal start — dan kegagalannya baru terlihat setelah deploy, karena
pengujian lokal memakai virtualenv yang berisi semuanya. Justru itu yang pernah
terjadi pada httpx saat lapisan analisis AI ditambahkan.
"""

import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

#: Nama modul yang diimpor -> nama distribusi di requirements.txt.
DISTRIBUTION = {
    "PIL": "pillow",
    "reportlab": "reportlab",
    "httpx": "httpx",
    "fastapi": "fastapi",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "psycopg": "psycopg",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
}


def _production_packages() -> set[str]:
    """Paket yang benar-benar terpasang di image, mengikuti filter Dockerfile."""
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    pola = re.search(r"grep -viE '\^\(([^)]+)\)'", dockerfile)
    assert pola, "filter dependensi di Dockerfile tidak ditemukan"
    dibuang = re.compile(rf"^({pola.group(1)})", re.IGNORECASE)

    paket = set()
    for baris in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or dibuang.match(baris):
            continue
        paket.add(re.split(r"[=<>\[]", baris)[0].strip().lower())
    return paket


def _imported_modules() -> set[str]:
    """Modul pihak ketiga yang diimpor di seluruh app/."""
    modul = set()
    for berkas in (BACKEND / "app").rglob("*.py"):
        pohon = ast.parse(berkas.read_text(encoding="utf-8"))
        for simpul in ast.walk(pohon):
            if isinstance(simpul, ast.Import):
                modul.update(alias.name.split(".")[0] for alias in simpul.names)
            elif isinstance(simpul, ast.ImportFrom) and simpul.level == 0 and simpul.module:
                modul.add(simpul.module.split(".")[0])

    bawaan = set(sys.stdlib_module_names) | {"app"}
    return {m for m in modul if m not in bawaan}


def test_every_runtime_import_survives_the_dockerfile_filter():
    tersedia = _production_packages()

    hilang = []
    for modul in sorted(_imported_modules()):
        distribusi = DISTRIBUTION.get(modul, modul).lower()
        if distribusi not in tersedia:
            hilang.append(f"{modul} (butuh paket {distribusi!r})")

    assert not hilang, (
        "Paket berikut diimpor app/ tapi tidak akan ada di image produksi: "
        + ", ".join(hilang)
        + ". Pindahkan keluar dari bagian dev pada requirements.txt."
    )


def test_httpx_is_a_runtime_dependency():
    """Penjaga khusus: nebius.py mengimpornya saat modul dimuat."""
    assert "httpx" in _production_packages()
