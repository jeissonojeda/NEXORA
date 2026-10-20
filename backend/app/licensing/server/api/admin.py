"""Endpoints del panel administrativo global (propietario de NEXORA).

Todos requieren un token administrativo (``LICENSE_JWT_SECRET``), totalmente
independiente de los usuarios del supermercado.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.licensing.server import schemas
from app.licensing.server.db import get_license_db
from app.licensing.server.deps import get_signer_dep, require_admin
from app.licensing.server.models import LicenseAdmin
from app.licensing.server.security import (
    create_admin_token,
    verify_password,
)
from app.licensing.server.services import activation as activation_service
from app.licensing.server.services import licenses as licenses_service
from app.licensing.server.signing import LicenseSigner
from app.licensing.server.utils import utc_now

router = APIRouter(prefix="/admin", tags=["licensing-admin"])

Admin = Annotated[LicenseAdmin, Depends(require_admin)]
DB = Annotated[Session, Depends(get_license_db)]


# ----------------------------------------------------------------------
# Autenticación
# ----------------------------------------------------------------------
@router.post("/auth/login", response_model=schemas.AdminToken)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DB,
) -> schemas.AdminToken:
    admin = db.scalar(select(LicenseAdmin).where(LicenseAdmin.username == form.username))
    # Se verifica siempre para no filtrar si el usuario existe.
    valid = admin is not None and verify_password(form.password, admin.password_hash)
    if not valid:
        raise AppError(401, "INVALID_CREDENTIALS", "Usuario o contraseña incorrectos")
    assert admin is not None
    if not admin.is_active:
        raise AppError(403, "ADMIN_INACTIVE", "La cuenta administrativa está inactiva")
    admin.last_login = utc_now()
    db.commit()
    return schemas.AdminToken(access_token=create_admin_token(str(admin.id)))


@router.get("/auth/me", response_model=schemas.AdminResponse)
def me(admin: Admin) -> schemas.AdminResponse:
    return schemas.AdminResponse.model_validate(admin)


# ----------------------------------------------------------------------
# Clientes
# ----------------------------------------------------------------------
@router.post("/customers", response_model=schemas.CustomerResponse, status_code=201)
def create_customer(
    data: schemas.CustomerCreate, db: DB, admin: Admin
) -> schemas.CustomerResponse:
    customer = licenses_service.create_customer(db, data)
    return schemas.CustomerResponse.model_validate(customer)


@router.get("/customers", response_model=list[schemas.CustomerResponse])
def list_customers(db: DB, admin: Admin) -> list[schemas.CustomerResponse]:
    return [
        schemas.CustomerResponse.model_validate(c)
        for c in licenses_service.list_customers(db)
    ]


# ----------------------------------------------------------------------
# Planes
# ----------------------------------------------------------------------
@router.post("/plans", response_model=schemas.PlanResponse, status_code=201)
def create_plan(
    data: schemas.PlanCreate, db: DB, admin: Admin
) -> schemas.PlanResponse:
    return licenses_service.plan_to_response(licenses_service.create_plan(db, data))


@router.get("/plans", response_model=list[schemas.PlanResponse])
def list_plans(db: DB, admin: Admin) -> list[schemas.PlanResponse]:
    return [licenses_service.plan_to_response(p) for p in licenses_service.list_plans(db)]


# ----------------------------------------------------------------------
# Licencias
# ----------------------------------------------------------------------
@router.post("/licenses", response_model=schemas.LicenseResponse, status_code=201)
def create_license(
    data: schemas.LicenseCreate, db: DB, admin: Admin
) -> schemas.LicenseResponse:
    license = licenses_service.create_license(db, data)
    return licenses_service.license_to_response(db, license)


@router.get("/licenses", response_model=list[schemas.LicenseResponse])
def list_licenses(
    db: DB,
    admin: Admin,
    status: str | None = None,
    customer_id: UUID | None = None,
) -> list[schemas.LicenseResponse]:
    return [
        licenses_service.license_to_response(db, lic)
        for lic in licenses_service.list_licenses(
            db, status=status, customer_id=customer_id
        )
    ]


@router.get("/licenses/{license_id}", response_model=schemas.LicenseResponse)
def get_license(license_id: UUID, db: DB, admin: Admin) -> schemas.LicenseResponse:
    license = licenses_service.get_license_or_404(db, license_id)
    return licenses_service.license_to_response(db, license)


@router.patch("/licenses/{license_id}/status", response_model=schemas.LicenseResponse)
def update_license_status(
    license_id: UUID,
    data: schemas.LicenseStatusUpdate,
    db: DB,
    admin: Admin,
) -> schemas.LicenseResponse:
    license = licenses_service.set_license_status(
        db, license_id, data, actor=admin.username
    )
    return licenses_service.license_to_response(db, license)


# ----------------------------------------------------------------------
# Instalaciones
# ----------------------------------------------------------------------
@router.get(
    "/licenses/{license_id}/installations",
    response_model=list[schemas.InstallationBrief],
)
def list_installations(
    license_id: UUID, db: DB, admin: Admin
) -> list[schemas.InstallationBrief]:
    return [
        schemas.InstallationBrief.model_validate(i)
        for i in licenses_service.list_installations(db, license_id)
    ]


@router.post(
    "/licenses/{license_id}/installations/{installation_id}/release",
    response_model=schemas.InstallationBrief,
)
def release_installation(
    license_id: UUID,
    installation_id: str,
    data: schemas.ReleaseInstallationRequest,
    db: DB,
    admin: Admin,
) -> schemas.InstallationBrief:
    installation = licenses_service.release_installation(
        db, license_id, installation_id, data, actor=admin.username
    )
    return schemas.InstallationBrief.model_validate(installation)


@router.post("/transfers", response_model=schemas.TransferResponse, status_code=201)
def create_transfer(
    data: schemas.TransferCreate, db: DB, admin: Admin
) -> schemas.TransferResponse:
    transfer = licenses_service.create_transfer(db, data, actor=admin.username)
    return schemas.TransferResponse.model_validate(transfer)


# ----------------------------------------------------------------------
# Activación manual
# ----------------------------------------------------------------------
@router.get("/manual-requests", response_model=list[schemas.ManualRequestResponse])
def list_manual_requests(
    db: DB, admin: Admin, status: str | None = None
) -> list[schemas.ManualRequestResponse]:
    return [
        schemas.ManualRequestResponse.model_validate(r)
        for r in activation_service.list_manual_requests(db, status=status)
    ]


@router.post(
    "/manual-requests/{request_id}/authorize",
    response_model=schemas.ManualAuthorizeResponse,
)
def authorize_manual_request(
    request_id: UUID,
    db: DB,
    admin: Admin,
    signer: Annotated[LicenseSigner, Depends(get_signer_dep)],
    note: str | None = None,
) -> schemas.ManualAuthorizeResponse:
    return activation_service.authorize_manual_request(
        db, signer, request_id, note=note, actor=admin.username
    )


@router.post(
    "/manual-requests/{request_id}/reject",
    response_model=schemas.ManualRequestResponse,
)
def reject_manual_request(
    request_id: UUID,
    db: DB,
    admin: Admin,
    note: str | None = None,
) -> schemas.ManualRequestResponse:
    record = activation_service.reject_manual_request(
        db, request_id, note=note, actor=admin.username
    )
    return schemas.ManualRequestResponse.model_validate(record)


# ----------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------
@router.get("/audit", response_model=list[schemas.AuditEventResponse])
def list_audit(
    db: DB, admin: Admin, license_id: UUID | None = None, limit: int = 100
) -> list[schemas.AuditEventResponse]:
    return [
        schemas.AuditEventResponse.model_validate(e)
        for e in licenses_service.list_audit_events(
            db, license_id=license_id, limit=min(limit, 500)
        )
    ]
