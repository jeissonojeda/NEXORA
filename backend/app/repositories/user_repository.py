from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return self.db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalars(stmt).first()

    def get_by_username_or_email(self, identifier: str) -> User | None:
        stmt = select(User).where(
            (User.username == identifier.lower())
            | (func.lower(User.email) == identifier.lower())
        )
        return self.db.scalars(stmt).first()

    def count_admins(self) -> int:
        from app.core.rbac import Roles
        from app.models.role import Role, user_roles

        stmt = (
            select(func.count())
            .select_from(User)
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.name == Roles.ADMIN)
        )
        return int(self.db.scalar(stmt) or 0)
