from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    SORTABLE_FIELDS = {
        "name": Customer.name,
        "created_at": Customer.created_at,
        "current_balance": Customer.current_balance,
        "credit_limit": Customer.credit_limit,
    }

    def __init__(self, db: Session) -> None:
        super().__init__(db, Customer)

    def get_by_identification(self, identification: str) -> Customer | None:
        stmt = select(Customer).where(Customer.identification == identification)
        return self.db.scalars(stmt).first()

    def get_for_update(self, customer_id: UUID) -> Customer | None:
        """Bloquea la fila del cliente (SELECT ... FOR UPDATE).

        Garantiza exclusividad al mover current_balance; en PostgreSQL el
        hint se aplica y en SQLite lo resuelve su lock global de escritura.
        """
        stmt = (
            select(Customer)
            .where(Customer.id == customer_id)
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def search(
        self,
        q: str | None = None,
        is_active: bool | None = None,
        credit_enabled: bool | None = None,
        order_by: str = "name",
        order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        stmt = select(Customer)
        count_stmt = select(func.count()).select_from(Customer)

        conditions: list[Any] = []
        if q:
            pattern = f"%{q.lower()}%"
            conditions.append(
                (func.lower(Customer.name).like(pattern))
                | (func.lower(Customer.identification).like(pattern))
                | (func.lower(Customer.email).like(pattern))
                | (func.lower(Customer.phone).like(pattern))
            )
        if is_active is not None:
            conditions.append(Customer.is_active == is_active)
        if credit_enabled is not None:
            conditions.append(Customer.credit_enabled == credit_enabled)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        column = self.SORTABLE_FIELDS.get(order_by, Customer.name)
        direction = desc if order == "desc" else asc
        stmt = (
            stmt.order_by(direction(column), Customer.name)
            .offset(skip)
            .limit(limit)
        )

        total = int(self.db.scalar(count_stmt) or 0)
        items = list(self.db.scalars(stmt).all())
        return items, total
