from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import logging
from contextlib import asynccontextmanager

from app import errors
from app.config import get_settings
from app.db import get_db
from app.routers import (
    auth as auth_router,
    dashboard,
    evaluation,
    experiments,
    jobs as jobs_router,
    export,
    results,
    settings as settings_router,
    spatial,
    training,
    upload,
)
from app.services import auth, jobs as job_queue

# Diimpor demi efek sampingnya: modul inilah yang mendaftarkan penjalan tiap
# jenis pekerjaan ke antrean.
from app.services import job_handlers  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)

settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Nyalakan pekerja latar saat start, hentikan saat berhenti.

    Sisa pekerjaan berstatus "running" dari proses sebelumnya dibereskan lebih
    dulu: prosesnya mati di tengah jalan, dan dibiarkan begitu layar akan
    memutar spinner tanpa akhir.
    """
    # Dirujuk lewat modulnya, bukan nama yang diikat saat impor: pengujian
    # menambal app.config.get_settings, dan nama yang sudah terikat tidak ikut
    # berubah.
    from app import config as app_config

    if app_config.get_settings().worker_enabled:
        try:
            job_queue.reset_interrupted()
            job_queue.start()
        except Exception:  # noqa: BLE001
            # Database belum siap saat start bukan alasan aplikasi gagal
            # menyala; pekerja mencoba lagi sendiri pada perulangan berikutnya.
            logging.getLogger("sawitscan").exception("Pekerja latar gagal dinyalakan")
    try:
        yield
    finally:
        job_queue.stop()


app = FastAPI(
    title="SawitScan AI API",
    description="Inference & reporting layer for oil palm plant condition detection from UAV imagery.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness plus a real database round-trip — an API that cannot reach its
    database is not healthy, however well it answers."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logging.getLogger("sawitscan").exception("Health check gagal menghubungi database")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "version": app.version, "database": "unreachable"},
        )
    return {"status": "ok", "version": app.version, "database": "ok"}


errors.register(app)

# Login dan status autentikasi harus dapat dicapai tanpa sudah masuk.
app.include_router(auth_router.router)

# Sisanya tertutup. Dependency dipasang di titik pendaftaran, bukan di tiap
# fungsi: route baru yang ditambahkan ke router mana pun ikut terlindungi tanpa
# harus diingat satu per satu — dan yang terlupa adalah yang bocor.
terlindungi = [
    upload.router,
    results.router,
    dashboard.router,
    export.router,
    evaluation.router,
    spatial.router,
    settings_router.router,
    jobs_router.router,
    experiments.router,
]
for r in terlindungi:
    app.include_router(r, dependencies=[Depends(auth.current_user)])

# Router training memakai objek pengguna, jadi ia meminta dependency-nya sendiri.
app.include_router(training.router)
