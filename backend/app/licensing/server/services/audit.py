"""Registro de auditoría del servicio central."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.licensing.server.models import LicenseAuditEvent
from app.licensing.server.utils import dumps


def record_event(
    db: Session,
    *,
    action: str,
    actor: str | None = None,
    license_id: UUID | None = None,
    installation_id: str | None = None,
    result: str = "SUCCESS",
    reason: str | None = None,
    detail: dict | None = None,
) -> LicenseAuditEvent:
    """Añade un evento de auditoría a la sesión (no hace commit).

    Nunca se registran códigos de licencia completos ni secretos: ``detail``
    debe contener solo metadatos.
    """

    event = LicenseAuditEvent(
        actor=actor,
        action=action,
        license_id=license_id,
        installation_id=installation_id,
        result=result,
        reason=reason,
        detail_json=dumps(detail) if detail is not None else None,
    )
    db.add(event)
    return event
