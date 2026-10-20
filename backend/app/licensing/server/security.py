"""Autenticación del panel administrativo global.

Separada del JWT de los usuarios del supermercado: usa otro secreto
(``LICENSE_JWT_SECRET``) y otro alcance (``license-admin``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.security import hash_password, verify_password  # reutilizadas
from app.licensing.server.config import get_license_settings

ADMIN_SCOPE = "license-admin"

__all__ = [
    "hash_password",
    "verify_password",
    "create_admin_token",
    "decode_admin_token",
]


def create_admin_token(admin_id: str) -> str:
    settings = get_license_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.LICENSE_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": admin_id, "scope": ADMIN_SCOPE, "exp": expire}
    return jwt.encode(
        payload,
        settings.LICENSE_JWT_SECRET,
        algorithm=settings.LICENSE_ALGORITHM,
    )


def decode_admin_token(token: str) -> dict[str, Any] | None:
    settings = get_license_settings()
    try:
        payload = jwt.decode(
            token,
            settings.LICENSE_JWT_SECRET,
            algorithms=[settings.LICENSE_ALGORITHM],
        )
    except JWTError:
        return None
    if payload.get("scope") != ADMIN_SCOPE:
        return None
    return payload
