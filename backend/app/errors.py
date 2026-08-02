"""Uniform error responses.

Every failure leaves the API in the same shape — ``{"detail": "<pesan>"}`` — so the
frontend has exactly one thing to read, and the operator always gets a sentence in
Indonesian rather than a stack trace or an English validation dump.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("sawitscan")


def register(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's own message is English and field-path shaped; log it for the
        # developer, show the operator something they can act on.
        logger.info("Permintaan tidak valid pada %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Permintaan tidak valid. Periksa kembali data yang dikirim."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def on_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Kegagalan database pada %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database sedang tidak dapat diakses. Coba lagi sebentar lagi."},
        )

    @app.exception_handler(Exception)
    async def on_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Galat tak terduga pada %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Terjadi kesalahan pada server. Laporkan ke administrator."},
        )
