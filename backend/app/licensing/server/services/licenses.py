"""Gestión de clientes, planes, licencias, instalaciones y transferencias."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.licensing.constants import (
    InstallationStatus,
    LicenseStatus,
    LicenseType,
    TransferStatus,
)
from app.licensing.server import schemas
from app.licensing.server.models import (
    License,
    LicenseCustomer,
    LicenseInstallation,
    LicensePlan,
    LicenseTransfer,
)
from app.licensing.server.services.audit import record_event
from app.licensing.server.utils import (
    dumps,
    generate_license_key,
    loads,
    to_utc,
    utc_now,
)


# ----------------------------------------------------------------------
# Serialización
# ----------------------------------------------------------------------
def count_active_installations(db: Session, license_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(LicenseInstallation)
            .where(
                LicenseInstallation.license_id == license_id,
                LicenseInstallation.status == InstallationStatus.ACTIVE.value,
            )
        )
        or 0
    )


def license_to_response(db: Session, license: License) -> schemas.LicenseResponse:
    return schemas.LicenseResponse(
        id=license.id,
        license_key=license.license_key,
        customer_id=license.customer_id,
        customer_name=license.customer.name if license.customer else None,
        plan_id=license.plan_id,
        license_type=license.license_type,
        status=license.status,
        features=loads(license.features_json, []),
        max_installations=license.max_installations,
        active_installations=count_active_installations(db, license.id),
        expires_at=to_utc(license.expires_at),
        grace_days=license.grace_days,
        updates_until=to_utc(license.updates_until),
        min_version=license.min_version,
        max_version=license.max_version,
        activated_at=to_utc(license.activated_at),
        revoked_at=to_utc(license.revoked_at),
        revoked_reason=license.revoked_reason,
        created_at=to_utc(license.created_at),
    )


def get_license_or_404(db: Session, license_id: UUID) -> License:
    license = db.get(License, license_id)
    if license is None:
        raise AppError(404, "LICENSE_NOT_FOUND", "Licencia no encontrada")
    return license


# ----------------------------------------------------------------------
# Clientes
# ----------------------------------------------------------------------
def create_customer(db: Session, data: schemas.CustomerCreate) -> LicenseCustomer:
    customer = LicenseCustomer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def list_customers(db: Session) -> list[LicenseCustomer]:
    return list(
        db.scalars(select(LicenseCustomer).order_by(LicenseCustomer.created_at.desc()))
    )


# ----------------------------------------------------------------------
# Planes
# ----------------------------------------------------------------------
def create_plan(db: Session, data: schemas.PlanCreate) -> LicensePlan:
    existing = db.scalar(select(LicensePlan).where(LicensePlan.code == data.code))
    if existing is not None:
        raise AppError(409, "PLAN_CODE_TAKEN", "Ya existe un plan con ese código")
    plan = LicensePlan(
        code=data.code,
        name=data.name,
        license_type=data.license_type,
        default_max_installations=data.default_max_installations,
        duration_days=data.duration_days,
        features_json=dumps(sorted(data.features)),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def plan_to_response(plan: LicensePlan) -> schemas.PlanResponse:
    return schemas.PlanResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        license_type=plan.license_type,
        default_max_installations=plan.default_max_installations,
        duration_days=plan.duration_days,
        features=loads(plan.features_json, []),
        is_active=plan.is_active,
        created_at=to_utc(plan.created_at),
    )


def list_plans(db: Session) -> list[LicensePlan]:
    return list(db.scalars(select(LicensePlan).order_by(LicensePlan.code)))


# ----------------------------------------------------------------------
# Licencias
# ----------------------------------------------------------------------
def _resolve_expiry(
    *,
    license_type: str,
    expires_at: datetime | None,
    duration_days: int | None,
) -> datetime | None:
    # Una licencia perpetua NUNCA caduca por tiempo.
    if license_type == LicenseType.PERPETUAL.value:
        return None
    if expires_at is not None:
        return expires_at
    if duration_days:
        return utc_now() + timedelta(days=duration_days)
    return None


def create_license(db: Session, data: schemas.LicenseCreate) -> License:
    customer = db.get(LicenseCustomer, data.customer_id)
    if customer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")

    plan = None
    if data.plan_id is not None:
        plan = db.get(LicensePlan, data.plan_id)
        if plan is None:
            raise AppError(404, "PLAN_NOT_FOUND", "Plan no encontrado")

    license_key = data.license_key
    if not license_key:
        for _ in range(5):
            candidate = generate_license_key()
            if db.scalar(select(License).where(License.license_key == candidate)) is None:
                license_key = candidate
                break
        else:
            raise AppError(500, "KEY_GENERATION_FAILED", "No se pudo generar la clave")
    elif db.scalar(select(License).where(License.license_key == license_key)) is not None:
        raise AppError(409, "LICENSE_KEY_TAKEN", "La clave de licencia ya existe")

    features = data.features or (loads(plan.features_json, []) if plan else [])
    max_installations = data.max_installations or (
        plan.default_max_installations if plan else 1
    )
    expires_at = _resolve_expiry(
        license_type=data.license_type,
        expires_at=data.expires_at,
        duration_days=plan.duration_days if plan else None,
    )

    license = License(
        license_key=license_key,
        customer_id=customer.id,
        plan_id=plan.id if plan else None,
        license_type=data.license_type,
        status=LicenseStatus.ACTIVE.value,
        features_json=dumps(sorted(features)),
        max_installations=max_installations,
        expires_at=expires_at,
        grace_days=data.grace_days,
        updates_until=data.updates_until,
        min_version=data.min_version,
        max_version=data.max_version,
    )
    db.add(license)
    db.flush()
    record_event(
        db,
        action="LICENSE_CREATED",
        actor="admin",
        license_id=license.id,
        detail={"license_type": license.license_type},
    )
    db.commit()
    db.refresh(license)
    return license


def list_licenses(
    db: Session, *, status: str | None = None, customer_id: UUID | None = None
) -> list[License]:
    stmt = select(License).order_by(License.created_at.desc())
    if status:
        stmt = stmt.where(License.status == status)
    if customer_id:
        stmt = stmt.where(License.customer_id == customer_id)
    return list(db.scalars(stmt))


def get_license_by_key(db: Session, license_key: str) -> License | None:
    return db.scalar(select(License).where(License.license_key == license_key))


def set_license_status(
    db: Session,
    license_id: UUID,
    data: schemas.LicenseStatusUpdate,
    *,
    actor: str = "admin",
) -> License:
    license = get_license_or_404(db, license_id)
    license.status = data.status
    if data.status == LicenseStatus.REVOKED.value:
        license.revoked_at = utc_now()
        license.revoked_reason = data.reason
    elif data.status == LicenseStatus.ACTIVE.value:
        license.revoked_at = None
        license.revoked_reason = None
    record_event(
        db,
        action=f"LICENSE_{data.status}",
        actor=actor,
        license_id=license.id,
        reason=data.reason,
    )
    db.commit()
    db.refresh(license)
    return license


# ----------------------------------------------------------------------
# Instalaciones
# ----------------------------------------------------------------------
def list_installations(db: Session, license_id: UUID) -> list[LicenseInstallation]:
    get_license_or_404(db, license_id)
    return list(
        db.scalars(
            select(LicenseInstallation)
            .where(LicenseInstallation.license_id == license_id)
            .order_by(LicenseInstallation.activated_at.desc())
        )
    )


def release_installation(
    db: Session,
    license_id: UUID,
    installation_id: str,
    data: schemas.ReleaseInstallationRequest,
    *,
    actor: str = "admin",
) -> LicenseInstallation:
    get_license_or_404(db, license_id)
    installation = db.scalar(
        select(LicenseInstallation).where(
            LicenseInstallation.license_id == license_id,
            LicenseInstallation.installation_id == installation_id,
        )
    )
    if installation is None:
        raise AppError(404, "INSTALLATION_NOT_FOUND", "Instalación no encontrada")

    installation.status = InstallationStatus.RELEASED.value
    installation.released_at = utc_now()
    installation.release_reason = data.reason
    record_event(
        db,
        action="INSTALLATION_RELEASED",
        actor=actor,
        license_id=license_id,
        installation_id=installation_id,
        reason=data.reason,
    )
    db.commit()
    db.refresh(installation)
    return installation


def create_transfer(
    db: Session, data: schemas.TransferCreate, *, actor: str = "admin"
) -> LicenseTransfer:
    license = get_license_or_404(db, data.license_id)
    if license.status == LicenseStatus.REVOKED.value:
        raise AppError(
            409, "LICENSE_REVOKED", "No se puede transferir una licencia revocada"
        )
    transfer = LicenseTransfer(
        license_id=license.id,
        from_installation_id=data.from_installation_id,
        to_installation_id=data.to_installation_id,
        reason=data.reason,
        status=TransferStatus.APPROVED.value,
        resolved_by=actor,
        resolved_at=utc_now(),
    )

    # Libera la instalación de origen para que el cupo quede disponible.
    if data.from_installation_id:
        origin = db.scalar(
            select(LicenseInstallation).where(
                LicenseInstallation.license_id == license.id,
                LicenseInstallation.installation_id == data.from_installation_id,
            )
        )
        if origin is not None and origin.status == InstallationStatus.ACTIVE.value:
            origin.status = InstallationStatus.RELEASED.value
            origin.released_at = utc_now()
            origin.release_reason = f"Transferencia: {data.reason}"

    db.add(transfer)
    record_event(
        db,
        action="LICENSE_TRANSFER",
        actor=actor,
        license_id=license.id,
        installation_id=data.from_installation_id,
        reason=data.reason,
    )
    db.commit()
    db.refresh(transfer)
    return transfer


# ----------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------
def list_audit_events(
    db: Session, *, license_id: UUID | None = None, limit: int = 100
) -> list:
    from app.licensing.server.models import LicenseAuditEvent

    stmt = select(LicenseAuditEvent).order_by(LicenseAuditEvent.created_at.desc()).limit(
        limit
    )
    if license_id:
        stmt = stmt.where(LicenseAuditEvent.license_id == license_id)
    return list(db.scalars(stmt))
