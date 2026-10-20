"""Endpoints locales de licenciamiento.

Son públicos a propósito: la pantalla de activación se muestra antes de iniciar
sesión. No aplican ``require_license`` (de lo contrario el sistema no se podría
activar).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.licensing.local import service

router = APIRouter(prefix="/license", tags=["license"])


class ActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=4, max_length=64)


class ManualRequestRequest(BaseModel):
    license_key: str = Field(..., min_length=4, max_length=64)


class ManualImportRequest(BaseModel):
    response_code: str = Field(..., min_length=8)


@router.get("/status")
def license_status(db: Annotated[Session, Depends(get_db)]) -> dict:
    return service.build_status_payload(db)


@router.post("/activate")
def activate(
    data: ActivateRequest, db: Annotated[Session, Depends(get_db)]
) -> dict:
    service.activate_online(db, data.license_key)
    return service.build_status_payload(db)


@router.post("/manual-request")
def manual_request(
    data: ManualRequestRequest, db: Annotated[Session, Depends(get_db)]
) -> dict:
    request_code = service.create_manual_request_code(db, data.license_key)
    return {"request_code": request_code}


@router.post("/manual-import")
def manual_import(
    data: ManualImportRequest, db: Annotated[Session, Depends(get_db)]
) -> dict:
    service.import_manual_response(db, data.response_code)
    return service.build_status_payload(db)
