"""Activación online y activación manual firmada."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.licensing.constants import (
    InstallationStatus,
    LicenseStatus,
    ManualRequestStatus,
)
from app.licensing.documents import build_license_payload, decode_activation_request
from app.licensing.errors import LicenseError
from app.licensing.server import schemas
from app.licensing.server.models import (
    License,
    LicenseActivationRequest,
    LicenseInstallation,
)
from app.licensing.server.services import licenses as licenses_service
from app.licensing.server.services.audit import record_event
from app.licensing.server.signing import LicenseSigner
from app.licensing.server.utils import (
    dumps,
    hash_fingerprint,
    hash_text,
    loads,
    to_utc,
    utc_now,
)


def _iso(value: datetime | None) -> str | None:
    value = to_utc(value)
    return value.replace(microsecond=0).isoformat() if value else None


def _validate_for_activation(license: License) -> None:
    if license.status == LicenseStatus.REVOKED.value:
        raise AppError(403, "LICENSE_REVOKED", "La licencia está revocada")
    if license.status == LicenseStatus.SUSPENDED.value:
        raise AppError(403, "LICENSE_SUSPENDED", "La licencia está suspendida")
    expires = to_utc(license.expires_at)
    if expires is not None:
        grace = timedelta(days=license.grace_days or 0)
        if utc_now() > expires + grace:
            raise AppError(403, "LICENSE_EXPIRED", "La licencia ha caducado")


def issue_document(
    signer: LicenseSigner,
    license: License,
    *,
    installation_id: str,
    fingerprint_hash: str,
    nonce: str | None,
) -> dict:
    plan_code = license.plan.code if license.plan else ""
    payload = build_license_payload(
        license_id=str(license.id),
        license_key=license.license_key,
        customer_name=license.customer.name if license.customer else "",
        plan_code=plan_code,
        license_type=license.license_type,
        activated_at=_iso(license.activated_at or utc_now()),
        expires_at=_iso(license.expires_at),
        grace_days=license.grace_days or 0,
        updates_until=_iso(license.updates_until),
        max_installations=license.max_installations,
        features=loads(license.features_json, []),
        min_version=license.min_version,
        max_version=license.max_version,
        installation_id=installation_id,
        installation_fingerprint=fingerprint_hash,
        nonce=nonce,
        issued_by="nexora-central",
    )
    return signer.sign(payload)


def _register_installation(
    db: Session,
    license: License,
    *,
    installation_id: str,
    fingerprint_hash: str,
    app_version: str | None,
    machine_label: str | None,
) -> LicenseInstallation:
    existing = db.scalar(
        select(LicenseInstallation).where(
            LicenseInstallation.installation_id == installation_id
        )
    )
    if existing is not None:
        if existing.license_id != license.id:
            raise AppError(
                409,
                "INSTALLATION_CONFLICT",
                "La instalación ya está vinculada a otra licencia",
            )
        if existing.status == InstallationStatus.REVOKED.value:
            raise AppError(
                403, "INSTALLATION_REVOKED", "La instalación está revocada"
            )
        # Reactivación idempotente (o reinstalación tras liberación).
        if existing.status == InstallationStatus.RELEASED.value:
            _ensure_capacity(db, license)
            existing.status = InstallationStatus.ACTIVE.value
            existing.released_at = None
            existing.release_reason = None
        existing.fingerprint_hash = fingerprint_hash
        existing.app_version = app_version or existing.app_version
        existing.machine_label = machine_label or existing.machine_label
        existing.last_seen_at = utc_now()
        return existing

    _ensure_capacity(db, license)
    installation = LicenseInstallation(
        license_id=license.id,
        installation_id=installation_id,
        fingerprint_hash=fingerprint_hash,
        app_version=app_version,
        machine_label=machine_label,
        status=InstallationStatus.ACTIVE.value,
        last_seen_at=utc_now(),
    )
    db.add(installation)
    return installation


def _ensure_capacity(db: Session, license: License) -> None:
    # Bloquea la fila de la licencia para que el conteo sea atómico.
    db.execute(select(License.id).where(License.id == license.id).with_for_update())
    active = licenses_service.count_active_installations(db, license.id)
    if active >= license.max_installations:
        raise AppError(
            409,
            "INSTALLATION_LIMIT_REACHED",
            "Se alcanzó el número máximo de instalaciones de la licencia",
        )


def activate_online(
    db: Session,
    signer: LicenseSigner,
    data: schemas.PublicActivationRequest,
    *,
    client_ip: str | None = None,
) -> schemas.PublicActivationResponse:
    license = licenses_service.get_license_by_key(db, data.license_key)
    if license is None:
        record_event(
            db,
            action="ACTIVATION_DENIED",
            actor=f"ip:{client_ip}" if client_ip else "public",
            result="FAILURE",
            reason="LICENSE_NOT_FOUND",
        )
        db.commit()
        raise AppError(404, "LICENSE_NOT_FOUND", "Licencia no encontrada")

    fingerprint_hash = hash_fingerprint(data.fingerprint)
    try:
        _validate_for_activation(license)
        installation = _register_installation(
            db,
            license,
            installation_id=data.installation_id,
            fingerprint_hash=fingerprint_hash,
            app_version=data.app_version,
            machine_label=data.machine_label,
        )
        if license.activated_at is None:
            license.activated_at = utc_now()
        document = issue_document(
            signer,
            license,
            installation_id=installation.installation_id,
            fingerprint_hash=fingerprint_hash,
            nonce=data.nonce,
        )
        record_event(
            db,
            action="ACTIVATION_SUCCESS",
            actor=f"ip:{client_ip}" if client_ip else "public",
            license_id=license.id,
            installation_id=installation.installation_id,
            detail={"app_version": data.app_version},
        )
        db.commit()
    except AppError as exc:
        record_event(
            db,
            action="ACTIVATION_DENIED",
            actor=f"ip:{client_ip}" if client_ip else "public",
            license_id=license.id,
            installation_id=data.installation_id,
            result="FAILURE",
            reason=exc.error_code,
        )
        db.commit()
        raise

    return schemas.PublicActivationResponse(
        status=LicenseStatus.ACTIVE.value, document=document
    )


def get_public_status(db: Session, license_key: str) -> schemas.PublicLicenseStatus:
    license = licenses_service.get_license_by_key(db, license_key)
    if license is None:
        raise AppError(404, "LICENSE_NOT_FOUND", "Licencia no encontrada")
    return schemas.PublicLicenseStatus(
        license_key=license.license_key,
        status=license.status,
        license_type=license.license_type,
        expires_at=to_utc(license.expires_at),
        max_installations=license.max_installations,
        active_installations=licenses_service.count_active_installations(
            db, license.id
        ),
    )


# ----------------------------------------------------------------------
# Activación manual
# ----------------------------------------------------------------------
def _decode_request_or_error(request_code: str) -> dict:
    try:
        return decode_activation_request(request_code)
    except LicenseError as exc:
        raise AppError(400, exc.error_code, exc.message)


def create_manual_request(
    db: Session, data: schemas.ManualRequestPublic
) -> LicenseActivationRequest:
    payload = _decode_request_or_error(data.request_code)
    request_hash = hash_text(data.request_code)

    existing = db.scalar(
        select(LicenseActivationRequest).where(
            LicenseActivationRequest.request_hash == request_hash
        )
    )
    if existing is not None:
        return existing

    license = licenses_service.get_license_by_key(db, payload["license_key"])
    request = LicenseActivationRequest(
        request_hash=request_hash,
        license_key=payload["license_key"],
        license_id=license.id if license else None,
        installation_id=payload["installation_id"],
        fingerprint_hash=hash_fingerprint(payload["fingerprint"]),
        nonce=payload.get("nonce", ""),
        app_version=payload.get("app_version"),
        status=ManualRequestStatus.PENDING.value,
    )
    db.add(request)
    record_event(
        db,
        action="MANUAL_REQUEST_CREATED",
        actor=f"install:{payload['installation_id']}",
        license_id=license.id if license else None,
        installation_id=payload["installation_id"],
    )
    db.commit()
    db.refresh(request)
    return request


def list_manual_requests(
    db: Session, *, status: str | None = None
) -> list[LicenseActivationRequest]:
    stmt = select(LicenseActivationRequest).order_by(
        LicenseActivationRequest.created_at.desc()
    )
    if status:
        stmt = stmt.where(LicenseActivationRequest.status == status)
    return list(db.scalars(stmt))


def authorize_manual_request(
    db: Session,
    signer: LicenseSigner,
    request_id: UUID,
    *,
    note: str | None = None,
    actor: str = "admin",
) -> schemas.ManualAuthorizeResponse:
    request = db.get(LicenseActivationRequest, request_id)
    if request is None:
        raise AppError(404, "REQUEST_NOT_FOUND", "Solicitud no encontrada")
    if request.status == ManualRequestStatus.AUTHORIZED.value:
        # Idempotente: devuelve la respuesta ya emitida.
        return schemas.ManualAuthorizeResponse(
            status=request.status,
            request_id=request.id,
            response_document=loads(request.response_document_json),
        )
    if request.status == ManualRequestStatus.REJECTED.value:
        raise AppError(409, "REQUEST_ALREADY_REJECTED", "La solicitud fue rechazada")

    license = licenses_service.get_license_by_key(db, request.license_key)
    if license is None:
        raise AppError(404, "LICENSE_NOT_FOUND", "Licencia no encontrada")

    try:
        _validate_for_activation(license)
        installation = _register_installation(
            db,
            license,
            installation_id=request.installation_id,
            fingerprint_hash=request.fingerprint_hash,
            app_version=request.app_version,
            machine_label=None,
        )
        if license.activated_at is None:
            license.activated_at = utc_now()
        document = issue_document(
            signer,
            license,
            installation_id=installation.installation_id,
            fingerprint_hash=request.fingerprint_hash,
            nonce=request.nonce,
        )
    except AppError as exc:
        record_event(
            db,
            action="MANUAL_REQUEST_DENIED",
            actor=actor,
            license_id=license.id,
            installation_id=request.installation_id,
            result="FAILURE",
            reason=exc.error_code,
        )
        db.commit()
        raise

    request.status = ManualRequestStatus.AUTHORIZED.value
    request.response_document_json = dumps(document)
    request.resolution_note = note
    request.resolved_by = actor
    request.resolved_at = utc_now()
    db.add(request)
    record_event(
        db,
        action="MANUAL_REQUEST_AUTHORIZED",
        actor=actor,
        license_id=license.id,
        installation_id=request.installation_id,
    )
    db.commit()
    db.refresh(request)
    return schemas.ManualAuthorizeResponse(
        status=request.status,
        request_id=request.id,
        response_document=document,
    )


def reject_manual_request(
    db: Session, request_id: UUID, *, note: str | None = None, actor: str = "admin"
) -> LicenseActivationRequest:
    request = db.get(LicenseActivationRequest, request_id)
    if request is None:
        raise AppError(404, "REQUEST_NOT_FOUND", "Solicitud no encontrada")
    if request.status != ManualRequestStatus.PENDING.value:
        raise AppError(409, "REQUEST_NOT_PENDING", "La solicitud ya fue resuelta")
    request.status = ManualRequestStatus.REJECTED.value
    request.resolved_by = actor
    request.resolved_at = utc_now()
    request.resolution_note = note
    record_event(
        db,
        action="MANUAL_REQUEST_REJECTED",
        actor=actor,
        license_id=request.license_id,
        installation_id=request.installation_id,
        reason=note,
    )
    db.commit()
    db.refresh(request)
    return request
