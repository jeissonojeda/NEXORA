from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.role import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.rbac_service import RbacService


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.rbac = RbacService(db)

    @staticmethod
    def _normalize_username(username: str) -> str:
        return username.strip().lower()

    def _ensure_unique_credentials(
        self,
        username: str,
        email: str,
        exclude_user_id: UUID | None = None,
    ) -> None:
        by_username = self.users.get_by_username(username)
        if by_username is not None and by_username.id != exclude_user_id:
            raise AppError(
                status_code=409,
                error_code="USERNAME_ALREADY_EXISTS",
                message="El nombre de usuario ya está en uso",
            )
        by_email = self.users.get_by_email(email)
        if by_email is not None and by_email.id != exclude_user_id:
            raise AppError(
                status_code=409,
                error_code="EMAIL_ALREADY_EXISTS",
                message="El email ya está registrado",
            )

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role_name: str | None = None,
    ) -> User:
        username = self._normalize_username(username)
        email = email.strip().lower()
        self._ensure_unique_credentials(username, email)

        roles: list[Role] = []
        if role_name is not None:
            roles = [self.rbac.get_by_name(role_name)]

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_active=True,
            roles=roles,
        )
        created = self.users.add(user)
        self.db.commit()
        self.db.refresh(created)
        return created

    def authenticate(self, identifier: str, password: str) -> User:
        user = self.users.get_by_username_or_email(identifier)

        if user is None or not verify_password(password, user.password_hash):
            raise AppError(
                status_code=401,
                error_code="INVALID_CREDENTIALS",
                message="Usuario o contraseña incorrectos",
            )
        if not user.is_active:
            raise AppError(
                status_code=403,
                error_code="USER_INACTIVE",
                message="El usuario está desactivado",
            )

        user.last_login = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: UUID) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise AppError(
                status_code=404,
                error_code="USER_NOT_FOUND",
                message="Usuario no encontrado",
            )
        return user

    def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return self.users.list_paginated(skip=skip, limit=limit)

    def update_user(self, user_id: UUID, **fields: object) -> User:
        user = self.get_user(user_id)

        new_username = fields.get("username")
        new_email = fields.get("email")
        if new_username is not None:
            new_username = self._normalize_username(str(new_username))
        if new_email is not None:
            new_email = str(new_email).strip().lower()

        if new_username or new_email:
            self._ensure_unique_credentials(
                username=new_username or user.username,
                email=new_email or user.email,
                exclude_user_id=user.id,
            )

        password = fields.get("password")
        if isinstance(password, str) and password:
            user.password_hash = hash_password(password)

        for field in ("first_name", "last_name", "is_active"):
            value = fields.get(field)
            if value is not None:
                setattr(user, field, value)
        if new_username:
            user.username = new_username
        if new_email:
            user.email = new_email

        role_name = fields.get("role_name")
        if role_name is not None:
            role = self.rbac.get_by_name(str(role_name))
            user.roles = [role]

        self.db.commit()
        self.db.refresh(user)
        return user

    def deactivate_user(
        self, user_id: UUID, acting_user_id: UUID | None = None
    ) -> User:
        user = self.get_user(user_id)
        if acting_user_id is not None and user.id == acting_user_id:
            raise AppError(
                status_code=409,
                error_code="CANNOT_DEACTIVATE_SELF",
                message="No puedes desactivar tu propia cuenta",
            )
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user
