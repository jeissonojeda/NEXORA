from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.purchase import Purchase, PurchaseItem
from app.repositories.base import BaseRepository


class PurchaseRepository(BaseRepository[Purchase]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Purchase)

    def get_by_number(self, purchase_number: str) -> Purchase | None:
        stmt = select(Purchase).where(Purchase.purchase_number == purchase_number)
        return self.db.scalars(stmt).first()

    def get_for_update(self, purchase_id: UUID) -> Purchase | None:
        """Bloquea la fila de la compra (SELECT ... FOR UPDATE).

        En PostgreSQL garantiza exclusividad durante la confirmación; en
        SQLite el hint se ignora (su lock global de escritura serializa).
        """
        stmt = (
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(selectinload(Purchase.items))
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_with_items(self, purchase_id: UUID) -> Purchase | None:
        stmt = (
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(
                selectinload(Purchase.items).joinedload(PurchaseItem.product),
                joinedload(Purchase.supplier),
                joinedload(Purchase.user),
            )
        )
        return self.db.scalars(stmt).first()

    def last_number_for_year(self, prefix: str) -> str | None:
        stmt = (
            select(Purchase.purchase_number)
            .where(Purchase.purchase_number.like(f"{prefix}%"))
            .order_by(desc(Purchase.purchase_number))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def search(
        self,
        supplier_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        # joinedload evita N+1 al serializar el proveedor en el listado.
        stmt = select(Purchase).options(joinedload(Purchase.supplier))
        count_stmt = select(func.count()).select_from(Purchase)

        conditions: list[Any] = []
        if supplier_id is not None:
            conditions.append(Purchase.supplier_id == supplier_id)
        if status is not None:
            conditions.append(Purchase.status == status)
        if date_from is not None:
            conditions.append(Purchase.created_at >= date_from)
        if date_to is not None:
            conditions.append(Purchase.created_at <= date_to)
        if q:
            pattern = f"%{q.lower()}%"
            conditions.append(func.lower(Purchase.purchase_number).like(pattern))

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(Purchase.created_at.desc(), Purchase.purchase_number.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total
