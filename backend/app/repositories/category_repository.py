from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Category)

    def get_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        return self.db.scalars(stmt).first()

    def has_products(self, category_id) -> bool:
        from app.models.product import Product

        stmt = select(Product.id).where(Product.category_id == category_id).limit(1)
        return self.db.scalar(stmt) is not None
