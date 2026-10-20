from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.category import Category
from app.models.tax import Tax
from app.repositories.category_repository import CategoryRepository


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)

    def _validate_tax(self, tax_id: UUID | None) -> None:
        if tax_id is None:
            return
        if self.db.get(Tax, tax_id) is None:
            raise AppError(
                status_code=400,
                error_code="INVALID_TAX",
                message="El impuesto indicado no existe",
            )

    def create_category(
        self,
        name: str,
        description: str | None = None,
        tax_id: UUID | None = None,
    ) -> Category:
        name = name.strip()
        if self.categories.get_by_name(name) is not None:
            raise AppError(
                status_code=409,
                error_code="CATEGORY_NAME_ALREADY_EXISTS",
                message="Ya existe una categoría con ese nombre",
            )
        self._validate_tax(tax_id)
        category = Category(
            name=name, description=description, tax_id=tax_id, is_active=True
        )
        created = self.categories.add(category)
        self.db.commit()
        self.db.refresh(created)
        return created

    def get_category(self, category_id) -> Category:
        category = self.categories.get_by_id(category_id)
        if category is None:
            raise AppError(
                status_code=404,
                error_code="CATEGORY_NOT_FOUND",
                message="Categoría no encontrada",
            )
        return category

    def list_categories(
        self, skip: int = 0, limit: int = 100, include_inactive: bool = True
    ) -> list[tuple[Category, int]]:
        return self.categories.list_with_counts(skip=skip, limit=limit)

    def update_category(self, category_id, **fields: object) -> Category:
        category = self.get_category(category_id)

        new_name = fields.get("name")
        if new_name is not None:
            new_name = str(new_name).strip()
            existing = self.categories.get_by_name(new_name)
            if existing is not None and existing.id != category.id:
                raise AppError(
                    status_code=409,
                    error_code="CATEGORY_NAME_ALREADY_EXISTS",
                    message="Ya existe una categoría con ese nombre",
                )
            category.name = new_name

        description = fields.get("description")
        if "description" in fields:
            category.description = description

        if "tax_id" in fields:
            tax_id = fields.get("tax_id")
            self._validate_tax(tax_id)
            category.tax_id = tax_id

        is_active = fields.get("is_active")
        if is_active is not None:
            category.is_active = bool(is_active)

        self.db.commit()
        self.db.refresh(category)
        return category

    def deactivate_category(self, category_id) -> Category:
        category = self.get_category(category_id)
        if self.categories.has_products(category_id):
            raise AppError(
                status_code=409,
                error_code="CATEGORY_IN_USE",
                message=(
                    "La categoría tiene productos asociados; "
                    "use desactivación lógica (PATCH)"
                ),
            )
        category.is_active = False
        self.db.commit()
        self.db.refresh(category)
        return category
