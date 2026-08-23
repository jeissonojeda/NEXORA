from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryMovement
from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Product)

    def get_by_barcode(self, barcode: str) -> Product | None:
        stmt = select(Product).where(Product.barcode == barcode)
        return self.db.scalars(stmt).first()

    def search(
        self,
        q: str | None = None,
        category_id: UUID | None = None,
        is_active: bool | None = None,
        low_stock: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        stmt = select(Product)
        count_stmt = select(func.count()).select_from(Product)

        conditions: list[Any] = []
        if q:
            pattern = f"%{q.lower()}%"
            conditions.append(
                (func.lower(Product.name).like(pattern))
                | (func.lower(Product.barcode).like(pattern))
            )
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        if is_active is not None:
            conditions.append(Product.is_active == is_active)
        if low_stock:
            conditions.append(Product.stock <= Product.minimum_stock)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(Product.name)
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def low_stock_products(self) -> list[Product]:
        stmt = (
            select(Product)
            .where(
                (Product.stock <= Product.minimum_stock) & (Product.is_active == True)  # noqa: E712
            )
            .order_by((Product.stock - Product.minimum_stock), Product.name)
        )
        return list(self.db.scalars(stmt).all())


class InventoryMovementRepository(BaseRepository[InventoryMovement]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, InventoryMovement)

    def search(
        self,
        product_id: UUID | None = None,
        movement_type: str | None = None,
        created_by: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[InventoryMovement], int]:
        stmt = select(InventoryMovement)
        count_stmt = select(func.count()).select_from(InventoryMovement)

        conditions: list[Any] = []
        if product_id is not None:
            conditions.append(InventoryMovement.product_id == product_id)
        if movement_type is not None:
            conditions.append(InventoryMovement.movement_type == movement_type)
        if created_by is not None:
            conditions.append(InventoryMovement.created_by == created_by)
        if date_from is not None:
            conditions.append(InventoryMovement.created_at >= date_from)
        if date_to is not None:
            conditions.append(InventoryMovement.created_at <= date_to)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(InventoryMovement.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total
