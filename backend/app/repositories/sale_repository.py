from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.sale import Sale, SaleItem
from app.repositories.base import BaseRepository


class SaleRepository(BaseRepository[Sale]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Sale)

    def get_by_number(self, sale_number: str) -> Sale | None:
        stmt = select(Sale).where(Sale.sale_number == sale_number)
        return self.db.scalars(stmt).first()

    def get_for_update(self, sale_id: UUID) -> Sale | None:
        """Bloquea la fila de la venta (SELECT ... FOR UPDATE).

        En PostgreSQL garantiza exclusividad durante la confirmación; en
        SQLite el hint se ignora (su lock global de escritura serializa).
        """
        stmt = (
            select(Sale)
            .where(Sale.id == sale_id)
            .options(selectinload(Sale.items))
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_with_items(self, sale_id: UUID) -> Sale | None:
        stmt = (
            select(Sale)
            .where(Sale.id == sale_id)
            .options(
                selectinload(Sale.items).joinedload(SaleItem.product),
                joinedload(Sale.customer),
                joinedload(Sale.user),
            )
        )
        return self.db.scalars(stmt).first()

    def last_number_for_year(self, prefix: str) -> str | None:
        stmt = (
            select(Sale.sale_number)
            .where(Sale.sale_number.like(f"{prefix}%"))
            .order_by(desc(Sale.sale_number))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def search(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Sale], int]:
        # joinedload evita N+1 al serializar cliente/cajero en el listado.
        stmt = select(Sale).options(
            joinedload(Sale.customer), joinedload(Sale.user)
        )
        count_stmt = select(func.count()).select_from(Sale)

        conditions: list[Any] = []
        if customer_id is not None:
            conditions.append(Sale.customer_id == customer_id)
        if status is not None:
            conditions.append(Sale.status == status)
        if date_from is not None:
            if status == "CONFIRMED":
                conditions.append(Sale.confirmed_at.is_not(None))
                conditions.append(Sale.confirmed_at >= date_from)
            else:
                conditions.append(Sale.created_at >= date_from)
        if date_to is not None:
            if status == "CONFIRMED":
                conditions.append(Sale.confirmed_at.is_not(None))
                conditions.append(Sale.confirmed_at <= date_to)
            else:
                conditions.append(Sale.created_at <= date_to)
        if q:
            pattern = f"%{q.lower()}%"
            conditions.append(func.lower(Sale.sale_number).like(pattern))

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        if status == "CONFIRMED" and (date_from is not None or date_to is not None):
            stmt = stmt.order_by(Sale.confirmed_at.desc(), Sale.sale_number.desc())
        else:
            stmt = stmt.order_by(Sale.created_at.desc(), Sale.sale_number.desc())
        stmt = stmt.offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).unique().all())
        return items, total
