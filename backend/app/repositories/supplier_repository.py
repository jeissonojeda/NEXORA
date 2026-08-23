from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    SORTABLE_FIELDS = {
        "name": Supplier.name,
        "created_at": Supplier.created_at,
        "updated_at": Supplier.updated_at,
    }

    def __init__(self, db: Session) -> None:
        super().__init__(db, Supplier)

    def get_by_name(self, name: str) -> Supplier | None:
        stmt = select(Supplier).where(Supplier.name == name)
        return self.db.scalars(stmt).first()

    def get_by_identification(self, identification: str) -> Supplier | None:
        stmt = select(Supplier).where(Supplier.identification == identification)
        return self.db.scalars(stmt).first()

    def search(
        self,
        q: str | None = None,
        is_active: bool | None = None,
        order_by: str = "name",
        order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[Supplier, int]], int]:
        stmt = select(Supplier)
        count_stmt = select(func.count()).select_from(Supplier)

        conditions: list[Any] = []
        if q:
            pattern = f"%{q.lower()}%"
            conditions.append(
                (func.lower(Supplier.name).like(pattern))
                | (func.lower(Supplier.identification).like(pattern))
                | (func.lower(Supplier.email).like(pattern))
                | (func.lower(Supplier.phone).like(pattern))
            )
        if is_active is not None:
            conditions.append(Supplier.is_active == is_active)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        # Conteo de productos por proveedor en una sola consulta (sin N+1).
        product_counts = (
            select(
                Product.supplier_id.label("supplier_id"),
                func.count(Product.id).label("products_count"),
            )
            .group_by(Product.supplier_id)
            .subquery()
        )
        stmt = stmt.add_columns(func.coalesce(product_counts.c.products_count, 0))
        stmt = stmt.outerjoin(product_counts, product_counts.c.supplier_id == Supplier.id)

        column = self.SORTABLE_FIELDS.get(order_by, Supplier.name)
        direction = desc if order == "desc" else asc
        stmt = stmt.order_by(direction(column), Supplier.name).offset(skip).limit(limit)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = self.db.execute(stmt).all()
        items = [(row[0], int(row[1])) for row in rows]
        return items, total

    def count_products(self, supplier_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Product)
            .where(Product.supplier_id == supplier_id)
        )
        return int(self.db.scalar(stmt) or 0)

    def has_products(self, supplier_id: UUID) -> bool:
        stmt = select(Product.id).where(Product.supplier_id == supplier_id).limit(1)
        return self.db.scalar(stmt) is not None
