from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.sale_return import SaleReturn, SaleReturnItem
from app.repositories.base import BaseRepository


class SaleReturnRepository(BaseRepository[SaleReturn]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, SaleReturn)

    def get_by_number(self, return_number: str) -> SaleReturn | None:
        stmt = select(SaleReturn).where(
            SaleReturn.return_number == return_number
        )
        return self.db.scalars(stmt).first()

    def get_for_update(self, return_id: UUID) -> SaleReturn | None:
        """Bloquea la fila de la devolución (SELECT ... FOR UPDATE)."""
        stmt = (
            select(SaleReturn)
            .where(SaleReturn.id == return_id)
            .options(selectinload(SaleReturn.items))
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_with_items(self, return_id: UUID) -> SaleReturn | None:
        stmt = (
            select(SaleReturn)
            .where(SaleReturn.id == return_id)
            .options(
                selectinload(SaleReturn.items).joinedload(
                    SaleReturnItem.product
                ),
                joinedload(SaleReturn.sale),
                joinedload(SaleReturn.exchange_sale),
                joinedload(SaleReturn.user),
            )
        )
        return self.db.scalars(stmt).first()

    def get_by_idempotency_key(self, key: str) -> SaleReturn | None:
        stmt = select(SaleReturn).where(SaleReturn.idempotency_key == key)
        return self.db.scalars(stmt).first()

    def last_number_for_year(self, prefix: str) -> str | None:
        stmt = (
            select(SaleReturn.return_number)
            .where(SaleReturn.return_number.like(f"{prefix}%"))
            .order_by(desc(SaleReturn.return_number))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def search_for_sale(
        self, sale_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[SaleReturn], int]:
        base = select(SaleReturn).where(SaleReturn.sale_id == sale_id)
        count_stmt = (
            select(func.count())
            .select_from(SaleReturn)
            .where(SaleReturn.sale_id == sale_id)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            base.options(
                joinedload(SaleReturn.user),
                selectinload(SaleReturn.items),
            )
            .order_by(SaleReturn.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total

    def sum_returned_quantity_for_item(
        self, sale_item_id: UUID
    ) -> int:
        """Cantidad ya devuelta de un ítem de venta (devoluciones activas)."""
        stmt = (
            select(func.coalesce(func.sum(SaleReturnItem.quantity), 0))
            .select_from(SaleReturnItem)
            .join(SaleReturn, SaleReturnItem.sale_return_id == SaleReturn.id)
            .where(
                SaleReturnItem.sale_item_id == sale_item_id,
                SaleReturn.status == "COMPLETED",
            )
        )
        return int(self.db.scalar(stmt) or 0)

    def sum_returned_quantity_for_sale(
        self, sale_id: UUID
    ) -> dict[UUID, int]:
        """Mapa sale_item_id -> cantidad devuelta (devoluciones activas)."""
        stmt = (
            select(
                SaleReturnItem.sale_item_id,
                func.coalesce(func.sum(SaleReturnItem.quantity), 0),
            )
            .select_from(SaleReturnItem)
            .join(SaleReturn, SaleReturnItem.sale_return_id == SaleReturn.id)
            .where(
                SaleReturn.sale_id == sale_id,
                SaleReturn.status == "COMPLETED",
            )
            .group_by(SaleReturnItem.sale_item_id)
        )
        return {row[0]: int(row[1]) for row in self.db.execute(stmt).all()}
