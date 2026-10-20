"""Endpoints públicos del servicio central.

Solo aceptan lo mínimo necesario para activar: no exponen datos de otros
clientes ni permiten enumerar licencias (se requiere la clave exacta).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.licensing.server import schemas
from app.licensing.server.db import get_license_db
from app.licensing.server.deps import get_signer_dep
from app.licensing.server.rate_limit import rate_limiter
from app.licensing.server.services import activation as activation_service
from app.licensing.server.signing import LicenseSigner

router = APIRouter(prefix="/public", tags=["licensing-public"])


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(request: Request, scope: str) -> None:
    ip = _client_ip(request)
    if not rate_limiter.check(f"{scope}:{ip}"):
        raise AppError(
            429, "RATE_LIMITED", "Demasiados intentos. Intente más tarde."
        )


@router.get("/public-key")
def get_public_key(
    signer: Annotated[LicenseSigner, Depends(get_signer_dep)],
) -> dict:
    return {"key_id": signer.key_id, "public_key_pem": signer.public_key_pem}


@router.post("/activate", response_model=schemas.PublicActivationResponse)
def activate(
    request: Request,
    data: schemas.PublicActivationRequest,
    db: Annotated[Session, Depends(get_license_db)],
    signer: Annotated[LicenseSigner, Depends(get_signer_dep)],
) -> schemas.PublicActivationResponse:
    _enforce_rate_limit(request, "activate")
    return activation_service.activate_online(
        db, signer, data, client_ip=_client_ip(request)
    )


@router.get("/status/{license_key}", response_model=schemas.PublicLicenseStatus)
def status(
    license_key: str,
    db: Annotated[Session, Depends(get_license_db)],
) -> schemas.PublicLicenseStatus:
    return activation_service.get_public_status(db, license_key)


@router.post("/manual-request", response_model=schemas.ManualRequestResponse)
def create_manual_request(
    request: Request,
    data: schemas.ManualRequestPublic,
    db: Annotated[Session, Depends(get_license_db)],
) -> schemas.ManualRequestResponse:
    _enforce_rate_limit(request, "manual-request")
    record = activation_service.create_manual_request(db, data)
    return schemas.ManualRequestResponse.model_validate(record)
