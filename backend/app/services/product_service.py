from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.product import Product
from app.models.supplier import Supplier
from app.repositories.category_repository import CategoryRepository
from app.repositories.product_repository import ProductRepository


def _normalize_barcode(barcode: str | None) -> str | None:
    if barcode is None:
        return None
    cleaned = barcode.strip()
    return cleaned or None


class ProductService:
    NULLABLE_FIELDS = ("barcode", "description", "supplier_id")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)

    def _ensure_unique_barcode(
        self, barcode: str | None, exclude_product_id: UUID | None = None
    ) -> None:
        if barcode is None:
            return
        existing = self.products.get_by_barcode(barcode)
        if existing is not None and existing.id != exclude_product_id:
            raise AppError(
                status_code=409,
                error_code="BARCODE_ALREADY_EXISTS",
                message="El código de barras ya está registrado",
            )

    def _validate_category(self, category_id: UUID):
        category = self.categories.get_by_id(category_id)
        if category is None:
            raise AppError(
                status_code=400,
                error_code="INVALID_CATEGORY",
                message="La categoría especificada no existe",
            )
        return category

    def _validate_supplier(
        self, supplier_id: UUID, require_active: bool = True
    ) -> Supplier:
        supplier = self.db.get(Supplier, supplier_id)
        if supplier is None:
            raise AppError(
                status_code=400,
                error_code="INVALID_SUPPLIER",
                message="El proveedor especificado no existe",
            )
        if require_active and not supplier.is_active:
            raise AppError(
                status_code=409,
                error_code="SUPPLIER_INACTIVE",
                message="El proveedor está inactivo; no puede asignarse a un producto activo",
            )
        return supplier

    def create_product(
        self,
        name: str,
        sale_price,
        category_id: UUID,
        purchase_price=None,
        barcode: str | None = None,
        description: str | None = None,
        supplier_id: UUID | None = None,
        stock: int = 0,
        minimum_stock: int = 0,
    ) -> Product:
        barcode = _normalize_barcode(barcode)
        self._ensure_unique_barcode(barcode)
        self._validate_category(category_id)
        if supplier_id is not None:
            self._validate_supplier(supplier_id)

        product = Product(
            name=name.strip(),
            barcode=barcode,
            description=description,
            purchase_price=purchase_price,
            sale_price=sale_price,
            category_id=category_id,
            supplier_id=supplier_id,
            stock=stock,
            minimum_stock=minimum_stock,
            is_active=True,
        )
        created = self.products.add(product)
        self.db.commit()
        self.db.refresh(created)
        return created

    def get_product(self, product_id: UUID) -> Product:
        product = self.products.get_by_id(product_id)
        if product is None:
            raise AppError(
                status_code=404,
                error_code="PRODUCT_NOT_FOUND",
                message="Producto no encontrado",
            )
        return product

    def get_active_product_by_barcode(self, barcode: str) -> Product:
        product = self.products.get_by_barcode(_normalize_barcode(barcode))
        if (
            product is None
            or not product.is_active
            or not product.category.is_active
        ):
            raise AppError(
                status_code=404,
                error_code="PRODUCT_NOT_FOUND",
                message="No existe un producto activo con ese código de barras",
            )
        return product

    def search_products(self, **filters: Any) -> tuple[list[Product], int]:
        return self.products.search(**filters)

    def low_stock_products(self) -> list[Product]:
        return self.products.low_stock_products()

    def update_product(self, product_id: UUID, **fields) -> Product:
        product = self.get_product(product_id)

        if "barcode" in fields:
            fields["barcode"] = _normalize_barcode(fields.get("barcode"))
        self._ensure_unique_barcode(fields.get("barcode"), product.id)

        new_category_id = fields.get("category_id")
        if new_category_id is not None and new_category_id != product.category_id:
            self._validate_category(new_category_id)

        new_supplier_id = fields.get("supplier_id")
        if new_supplier_id is not None:
            self._validate_supplier(new_supplier_id, require_active=False)

        # Estado combinado producto↔proveedor: un producto activo no puede
        # quedar asociado a un proveedor inactivo ni a uno inexistente.
        if "supplier_id" in fields or "is_active" in fields:
            effective_supplier_id = (
                fields["supplier_id"] if "supplier_id" in fields else product.supplier_id
            )
            effective_is_active = (
                fields["is_active"] if "is_active" in fields else product.is_active
            )
            if effective_is_active and effective_supplier_id is not None:
                self._validate_supplier(effective_supplier_id)

        for field in (
            "name",
            "barcode",
            "description",
            "purchase_price",
            "sale_price",
            "category_id",
            "supplier_id",
            "minimum_stock",
            "is_active",
        ):
            if field not in fields:
                continue
            value = fields[field]
            if field not in self.NULLABLE_FIELDS and value is None:
                continue
            if field == "name":
                value = value.strip()
            setattr(product, field, value)

        self.db.commit()
        self.db.refresh(product)
        return product

    def deactivate_product(self, product_id: UUID) -> Product:
        product = self.get_product(product_id)
        product.is_active = False
        self.db.commit()
        self.db.refresh(product)
        return product
