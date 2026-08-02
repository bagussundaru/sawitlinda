from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import dashboard, export, results, upload

settings = get_settings()

app = FastAPI(
    title="SawitScan AI API",
    description="Inference & reporting layer for oil palm disease detection from UAV imagery.",
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
def health() -> dict:
    return {"status": "ok", "version": app.version}


app.include_router(upload.router)
app.include_router(results.router)
app.include_router(dashboard.router)
app.include_router(export.router)
