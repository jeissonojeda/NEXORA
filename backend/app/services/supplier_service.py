from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.supplier import Supplier
from app.repositories.supplier_repository import SupplierRepository

NULLABLE_FIELDS = (
    "identification",
    "contact_name",
    "phone",
    "email",
    "address",
    "city",
    "notes",
)


def _normalize_optional(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.suppliers = SupplierRepository(db)

    def _ensure_unique_identification(
        self, identification: str | None, exclude_supplier_id: UUID | None = None
    ) -> None:
        if identification is None:
            return
        existing = self.suppliers.get_by_identification(identification)
        if existing is not None and existing.id != exclude_supplier_id:
            raise AppError(
                status_code=409,
                error_code="SUPPLIER_IDENTIFICATION_ALREADY_EXISTS",
                message="Ya existe un proveedor con esa identificación",
            )

    def _ensure_unique_name(
        self, name: str, exclude_supplier_id: UUID | None = None
    ) -> None:
        existing = self.suppliers.get_by_name(name)
        if existing is not None and existing.id != exclude_supplier_id:
            raise AppError(
                status_code=409,
                error_code="SUPPLIER_NAME_ALREADY_EXISTS",
                message="Ya existe un proveedor con ese nombre",
            )

    def create_supplier(
        self,
        name: str,
        identification: str | None = None,
        contact_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        notes: str | None = None,
    ) -> Supplier:
        name = name.strip()
        identification = _normalize_optional(identification)
        self._ensure_unique_name(name)
        self._ensure_unique_identification(identification)

        supplier = Supplier(
            name=name,
            identification=identification,
            contact_name=_normalize_optional(contact_name),
            phone=_normalize_optional(phone),
            email=_normalize_optional(email),
            address=_normalize_optional(address),
            city=_normalize_optional(city),
            notes=_normalize_optional(notes),
            is_active=True,
        )
        created = self.suppliers.add(supplier)
        self.db.commit()
        self.db.refresh(created)
        return created

    def get_supplier(self, supplier_id: UUID) -> Supplier:
        supplier = self.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise AppError(
                status_code=404,
                error_code="SUPPLIER_NOT_FOUND",
                message="Proveedor no encontrado",
            )
        return supplier

    def get_supplier_detail(self, supplier_id: UUID) -> dict[str, Any]:
        supplier = self.get_supplier(supplier_id)
        products_count = self.suppliers.count_products(supplier.id)
        return {
            "supplier": supplier,
            "products_count": products_count,
        }

    def list_suppliers(
        self,
        q: str | None = None,
        is_active: bool | None = None,
        order_by: str = "name",
        order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[Supplier, int]], int]:
        """Retorna ([(proveedor, cantidad_productos), ...], total)."""
        return self.suppliers.search(
            q=q,
            is_active=is_active,
            order_by=order_by,
            order=order,
            skip=skip,
            limit=limit,
        )

    def products_of_supplier(
        self,
        supplier_id: UUID,
        q: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        # Valida existencia del proveedor antes de listar sus productos.
        supplier = self.get_supplier(supplier_id)
        from app.repositories.product_repository import ProductRepository

        items, total = ProductRepository(self.db).search(
            q=q,
            supplier_id=supplier.id,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        return items, total

    def update_supplier(self, supplier_id: UUID, **fields: Any) -> Supplier:
        supplier = self.get_supplier(supplier_id)

        new_name = fields.get("name")
        if new_name is not None:
            new_name = str(new_name).strip()
            self._ensure_unique_name(new_name, exclude_supplier_id=supplier.id)
            supplier.name = new_name

        if "identification" in fields:
            new_identification = _normalize_optional(fields.get("identification"))
            self._ensure_unique_identification(
                new_identification, exclude_supplier_id=supplier.id
            )
            supplier.identification = new_identification

        for field in NULLABLE_FIELDS:
            if field == "identification" or field not in fields:
                continue
            setattr(supplier, field, _normalize_optional(fields.get(field)))

        is_active = fields.get("is_active")
        if is_active is not None:
            supplier.is_active = bool(is_active)

        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def deactivate_supplier(self, supplier_id: UUID) -> Supplier:
        """Borrado lógico: los proveedores nunca se eliminan físicamente."""
        supplier = self.get_supplier(supplier_id)
        supplier.is_active = False
        self.db.commit()
        self.db.refresh(supplier)
        return supplier
