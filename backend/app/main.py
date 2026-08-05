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
from app.routers import dashboard, evaluation, export, results, settings as settings_router, upload

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

app.include_router(upload.router)
app.include_router(results.router)
app.include_router(dashboard.router)
app.include_router(export.router)
app.include_router(evaluation.router)
app.include_router(settings_router.router)
