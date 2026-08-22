from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.rbac_service import RbacService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_CREDENTIALS_ERROR = AppError(
    status_code=401,
    error_code="NOT_AUTHENTICATED",
    message="No autenticado o token inválido",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise _CREDENTIALS_ERROR

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _CREDENTIALS_ERROR

    try:
        user_id = UUID(subject)
    except ValueError:
        raise _CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise AppError(
            status_code=403,
            error_code="USER_INACTIVE",
            message="El usuario está desactivado",
        )
    return current_user


def require_permission(permission_code: str) -> Callable[..., User]:
    def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        rbac = RbacService(db)
        if not rbac.user_has_permission(current_user, permission_code):
            raise AppError(
                status_code=403,
                error_code="PERMISSION_DENIED",
                message=f"No tiene el permiso requerido: {permission_code}",
            )
        return current_user

    return permission_checker


def require_role(*role_names: str) -> Callable[..., User]:
    def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        rbac = RbacService(db)
        if not rbac.user_has_any_role(current_user, set(role_names)):
            raise AppError(
                status_code=403,
                error_code="ROLE_REQUIRED",
                message=f"Se requiere uno de los roles: {', '.join(role_names)}",
            )
        return current_user

    return role_checker
