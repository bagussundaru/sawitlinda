from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import logging

from app import errors
from app.config import get_settings
from app.db import get_db
from app.routers import (
    auth as auth_router,
    dashboard,
    evaluation,
    export,
    results,
    settings as settings_router,
    training,
    upload,
)
from app.services import auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="SawitScan AI API",
    description="Inference & reporting layer for oil palm plant condition detection from UAV imagery.",
    version="0.1.0",
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
    settings_router.router,
]
for r in terlindungi:
    app.include_router(r, dependencies=[Depends(auth.current_user)])

# Router training memakai objek pengguna, jadi ia meminta dependency-nya sendiri.
app.include_router(training.router)
