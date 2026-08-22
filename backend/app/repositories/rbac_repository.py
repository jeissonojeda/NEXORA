from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Permission, Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Role)

    def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        return self.db.scalars(stmt).first()

    def get_all(self) -> list[Role]:
        stmt = select(Role).order_by(Role.name)
        return list(self.db.scalars(stmt).all())

    def get_by_names(self, names: set[str]) -> list[Role]:
        if not names:
            return []
        stmt = select(Role).where(Role.name.in_(names))
        return list(self.db.scalars(stmt).all())


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Permission)

    def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        return self.db.scalars(stmt).first()

    def get_by_codes(self, codes: set[str]) -> list[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list(self.db.scalars(stmt).all())
