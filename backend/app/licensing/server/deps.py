"""Dependencias del servicio central (firma y autenticación administrativa)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.licensing.server.db import get_license_db
from app.licensing.server.models import LicenseAdmin
from app.licensing.server.security import decode_admin_token
from app.licensing.server.signing import LicenseSigner, get_signer

oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")


def get_signer_dep() -> LicenseSigner:
    return get_signer()


def require_admin(
    token: Annotated[str, Depends(oauth2_admin_scheme)],
    db: Annotated[Session, Depends(get_license_db)],
) -> LicenseAdmin:
    payload = decode_admin_token(token)
    if payload is None:
        raise AppError(
            status_code=401,
            error_code="NOT_AUTHENTICATED",
            message="No autenticado o token administrativo inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    subject = payload.get("sub")
    try:
        admin_id = UUID(str(subject))
    except (TypeError, ValueError):
        raise AppError(401, "NOT_AUTHENTICATED", "Token administrativo inválido")

    admin = db.get(LicenseAdmin, admin_id)
    if admin is None or not admin.is_active:
        raise AppError(401, "NOT_AUTHENTICATED", "Administrador no válido")
    return admin
