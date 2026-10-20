from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Category)

    def get_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        return self.db.scalars(stmt).first()

    def list_with_counts(
        self, skip: int = 0, limit: int = 100
    ) -> list[tuple[Category, int]]:
        """Lista categorías junto con su número de productos (incluye inactivos)."""
        stmt = (
            select(Category, func.count(Product.id))
            .outerjoin(Product, Product.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.name)
            .offset(skip)
            .limit(limit)
        )
        return [
            (category, int(products_count))
            for category, products_count in self.db.execute(stmt).all()
        ]

    def has_products(self, category_id) -> bool:
        from app.models.product import Product

        stmt = select(Product.id).where(Product.category_id == category_id).limit(1)
        return self.db.scalar(stmt) is not None
