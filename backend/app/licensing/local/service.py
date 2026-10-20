"""Servicio local de licencias.

Responsabilidades:
- Mantener la identidad de la instalación (installation_id + huella).
- Activar por internet o mediante código manual, verificando el documento.
- Evaluar el estado local (activa, gracia, vencida, revocada, rollback).
- Servir la información que el frontend usa para la pantalla de activación.

Nunca elimina datos de negocio: revocar/vencer solo bloquea el uso, no borra.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.licensing.constants import (
    CLOCK_ROLLBACK_TOLERANCE_SECONDS,
    LocalLicenseStatus,
)
from app.licensing.documents import (
    build_activation_request,
    decode_license_document,
    encode_activation_request,
)
from app.licensing.errors import LicenseError
from app.licensing.local.fingerprint import (
    fingerprint_hash,
    machine_fingerprint,
    machine_label,
)
from app.licensing.local.verifier import LicenseVerifier
from app.licensing.server.utils import dumps, loads, to_utc, utc_now
from app.models.license import LocalInstallation, LocalLicense

_STATUS_MESSAGES = {
    LocalLicenseStatus.NOT_ACTIVATED.value: "El sistema no tiene una licencia activada.",
    LocalLicenseStatus.EXPIRED.value: "La licencia ha caducado.",
    LocalLicenseStatus.REVOKED.value: "La licencia fue revocada.",
    LocalLicenseStatus.INVALID.value: "La licencia no es válida.",
    LocalLicenseStatus.CLOCK_ROLLBACK.value: (
        "Se detectó un retroceso del reloj del sistema."
    ),
}


# ----------------------------------------------------------------------
# Identidad de la instalación
# ----------------------------------------------------------------------
def ensure_installation(db: Session) -> LocalInstallation:
    current_hash = fingerprint_hash(machine_fingerprint())
    installation = db.scalar(select(LocalInstallation).limit(1))
    if installation is None:
        installation = LocalInstallation(
            installation_id=secrets.token_hex(16),
            fingerprint_hash=current_hash,
            machine_label=machine_label(),
        )
        db.add(installation)
        db.commit()
        db.refresh(installation)
    return installation


# ----------------------------------------------------------------------
# Consulta de estado
# ----------------------------------------------------------------------
def get_active_license(db: Session) -> LocalLicense | None:
    return db.scalar(select(LocalLicense).order_by(LocalLicense.created_at.desc()))


def evaluate_status(license: LocalLicense) -> str:
    if license.clock_rollback:
        return LocalLicenseStatus.CLOCK_ROLLBACK.value
    if license.status == LocalLicenseStatus.REVOKED.value:
        return LocalLicenseStatus.REVOKED.value

    expires = to_utc(license.expires_at)
    if expires is None:
        return LocalLicenseStatus.ACTIVE.value

    now = utc_now()
    if now <= expires:
        return LocalLicenseStatus.ACTIVE.value
    if now <= expires + timedelta(days=license.grace_days or 0):
        return LocalLicenseStatus.GRACE.value
    return LocalLicenseStatus.EXPIRED.value


def refresh_state(db: Session) -> LocalLicense | None:
    """Actualiza la marca de agua temporal y detecta retrocesos de reloj."""

    license = get_active_license(db)
    if license is None:
        return None

    now = utc_now()
    last_seen = to_utc(license.last_seen_at)
    if last_seen is not None:
        tolerance = timedelta(seconds=CLOCK_ROLLBACK_TOLERANCE_SECONDS)
        if now < last_seen - tolerance:
            license.clock_rollback = True
        elif now > last_seen:
            license.last_seen_at = now
    else:
        license.last_seen_at = now

    license.status = evaluate_status(license)
    db.commit()
    db.refresh(license)
    return license


def is_enforcement_enabled() -> bool:
    return get_settings().is_license_enforcement_enabled


def build_status_payload(db: Session) -> dict[str, Any]:
    license = refresh_state(db)
    enforcement = is_enforcement_enabled()
    if license is None:
        return {
            "status": LocalLicenseStatus.NOT_ACTIVATED.value,
            "enforced": enforcement,
            "activated": False,
            "message": _STATUS_MESSAGES[LocalLicenseStatus.NOT_ACTIVATED.value],
        }
    status = license.status
    return {
        "status": status,
        "enforced": enforcement,
        "activated": status
        in (LocalLicenseStatus.ACTIVE.value, LocalLicenseStatus.GRACE.value),
        "message": _STATUS_MESSAGES.get(status),
        "license_key": license.license_key,
        "license_type": license.license_type,
        "customer_name": license.customer_name,
        "plan_code": license.plan_code,
        "features": loads(license.features_json, []),
        "installation_id": license.installation_id,
        "expires_at": to_utc(license.expires_at),
        "activated_at": to_utc(license.activated_at),
        "grace_days": license.grace_days,
        "clock_rollback": license.clock_rollback,
    }


# ----------------------------------------------------------------------
# Activación
# ----------------------------------------------------------------------
def _verify_and_store(db: Session, document: dict[str, Any]) -> LocalLicense:
    from app.licensing.local.verifier import get_verifier

    verifier: LicenseVerifier = get_verifier()
    try:
        payload = verifier.verify(document)
    except LicenseError as exc:
        raise AppError(400, exc.error_code, exc.message)
    except RuntimeError as exc:
        raise AppError(500, "LICENSE_KEY_NOT_CONFIGURED", str(exc))

    installation = ensure_installation(db)
    current_hash = fingerprint_hash(machine_fingerprint())

    # El documento debe estar atado a ESTA instalación y a ESTA máquina.
    if payload.get("installation_id") != installation.installation_id:
        raise AppError(
            403,
            "LICENSE_INSTALLATION_MISMATCH",
            "La licencia corresponde a otra instalación.",
        )
    if payload.get("installation_fingerprint") != current_hash:
        raise AppError(
            403,
            "LICENSE_FINGERPRINT_MISMATCH",
            "La licencia fue activada en otro equipo.",
        )

    license = db.scalar(
        select(LocalLicense).where(LocalLicense.license_key == payload["license_key"])
    )
    if license is None:
        license = LocalLicense(
            license_key=payload["license_key"],
            installation_id=installation.installation_id,
            fingerprint_hash=current_hash,
        )
        db.add(license)

    license.license_id = payload.get("license_id")
    license.customer_name = payload.get("customer_name")
    license.plan_code = payload.get("plan_code")
    license.license_type = payload.get("license_type", "PERPETUAL")
    license.features_json = dumps(sorted(payload.get("features") or []))
    license.max_installations = int(payload.get("max_installations") or 1)
    license.fingerprint_hash = current_hash
    license.document_json = dumps(document)
    license.activated_at = _parse_dt(payload.get("activated_at")) or utc_now()
    license.expires_at = _parse_dt(payload.get("expires_at"))
    license.grace_days = int(payload.get("grace_days") or 0)
    license.updates_until = _parse_dt(payload.get("updates_until"))
    license.clock_rollback = False
    license.last_seen_at = utc_now()
    license.status = evaluate_status(license)

    # Solo una licencia local activa a la vez.
    for other in db.scalars(select(LocalLicense)).all():
        if other.id != license.id:
            db.delete(other)

    db.commit()
    db.refresh(license)
    return license


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        from datetime import datetime

        return to_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def activate_online(db: Session, license_key: str) -> LocalLicense:
    settings = get_settings()
    installation = ensure_installation(db)
    raw_fingerprint = machine_fingerprint()
    request_body = {
        "license_key": license_key.strip(),
        "installation_id": installation.installation_id,
        "fingerprint": raw_fingerprint,
        "app_version": settings.LICENSE_APP_VERSION,
        "machine_label": machine_label(),
    }
    url = settings.LICENSE_SERVER_URL.rstrip("/") + "/api/public/activate"
    try:
        with httpx.Client(timeout=settings.LICENSE_HTTP_TIMEOUT) as client:
            response = client.post(url, json=request_body)
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            "LICENSE_SERVER_UNREACHABLE",
            "No se pudo contactar el servidor de licencias. Use la activación manual.",
        ) from exc

    if response.status_code != 200:
        _raise_from_response(response)
    document = response.json().get("document")
    if not isinstance(document, dict):
        raise AppError(502, "LICENSE_SERVER_BAD_RESPONSE", "Respuesta inválida.")
    return _verify_and_store(db, document)


def _raise_from_response(response: httpx.Response) -> None:
    try:
        body = response.json()
        code = body.get("error_code", "LICENSE_ACTIVATION_FAILED")
        message = body.get("detail", "No se pudo activar la licencia.")
    except ValueError:
        code, message = "LICENSE_ACTIVATION_FAILED", "No se pudo activar la licencia."
    raise AppError(response.status_code, code, message)


def create_manual_request_code(db: Session, license_key: str) -> str:
    settings = get_settings()
    installation = ensure_installation(db)
    request = build_activation_request(
        license_key=license_key.strip(),
        installation_id=installation.installation_id,
        fingerprint=machine_fingerprint(),
        nonce=secrets.token_hex(16),
        app_version=settings.LICENSE_APP_VERSION,
    )
    return encode_activation_request(request)


def import_manual_response(db: Session, response_code: str) -> LocalLicense:
    try:
        document = decode_license_document(response_code)
    except LicenseError as exc:
        raise AppError(400, exc.error_code, exc.message)
    return _verify_and_store(db, document)
