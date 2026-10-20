"""Aplicación FastAPI independiente del servicio central de licencias.

Ejecutar con::

    uvicorn app.licensing.server.main:app --host 0.0.0.0 --port 8100
"""

import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.licensing.errors import LicenseError
from app.licensing.server.api import admin, public
from app.licensing.server.config import get_license_settings

settings = get_license_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="NEXORA Licensing Service",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/health", tags=["licensing-health"])
def health() -> dict:
    return {"status": "ok", "service": "licensing"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
        },
        headers=exc.headers,
    )


@app.exception_handler(LicenseError)
async def license_error_handler(request: Request, exc: LicenseError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "status_code": exc.http_status,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "status_code": 500,
        },
    )
