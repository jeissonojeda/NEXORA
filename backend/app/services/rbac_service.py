from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.role import Role
from app.models.user import User
from app.repositories.rbac_repository import RoleRepository

ADMIN_ROLE = "ADMIN"


class RbacService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.roles = RoleRepository(db)

    def list_roles(self) -> list[Role]:
        return self.roles.get_all()

    def get_by_name(self, name: str) -> Role:
        role = self.roles.get_by_name(name)
        if role is None:
            raise AppError(
                status_code=400,
                error_code="INVALID_ROLE",
                message=f"El rol '{name}' no existe",
            )
        return role

    def user_has_permission(self, user: User, code: str) -> bool:
        if any(role.name == ADMIN_ROLE for role in user.roles):
            return True
        return any(
            any(permission.code == code for permission in role.permissions)
            for role in user.roles
        )

    def user_has_any_role(self, user: User, names: set[str]) -> bool:
        return any(role.name in names for role in user.roles)
