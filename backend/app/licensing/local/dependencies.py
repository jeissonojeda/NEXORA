"""Dependencia de aplicación que exige una licencia válida.

Se aplica a los routers de negocio. Está **desactivada por defecto** para no
afectar los entornos de desarrollo/pruebas: solo se activa en producción o si se
define ``LICENSE_ENFORCEMENT_ENABLED=true``.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.session import get_db
from app.licensing.constants import LocalLicenseStatus
from app.licensing.local import service

_ALLOWED = {LocalLicenseStatus.ACTIVE.value, LocalLicenseStatus.GRACE.value}

_BLOCK_MESSAGES = {
    LocalLicenseStatus.NOT_ACTIVATED.value: "El sistema no tiene una licencia activada.",
    LocalLicenseStatus.EXPIRED.value: "La licencia ha caducado. Reactívela para continuar.",
    LocalLicenseStatus.REVOKED.value: "La licencia fue revocada.",
    LocalLicenseStatus.INVALID.value: "La licencia no es válida.",
    LocalLicenseStatus.CLOCK_ROLLBACK.value: "Se detectó un retroceso del reloj del sistema.",
}


def require_license(db: Annotated[Session, Depends(get_db)]) -> None:
    if not service.is_enforcement_enabled():
        return

    license = service.refresh_state(db)
    if license is None:
        raise AppError(
            402,
            "LICENSE_NOT_ACTIVATED",
            _BLOCK_MESSAGES[LocalLicenseStatus.NOT_ACTIVATED.value],
        )

    if license.status in _ALLOWED:
        return

    message = _BLOCK_MESSAGES.get(license.status, "La licencia no permite esta operación.")
    http_status = 403 if license.status in {
        LocalLicenseStatus.REVOKED.value,
        LocalLicenseStatus.CLOCK_ROLLBACK.value,
        LocalLicenseStatus.INVALID.value,
    } else 402
    raise AppError(http_status, f"LICENSE_{license.status}", message)
