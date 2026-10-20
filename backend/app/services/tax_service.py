from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.tax import Tax


class TaxService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_taxes(self, include_inactive: bool = False) -> list[Tax]:
        stmt = select(Tax)
        if not include_inactive:
            stmt = stmt.where(Tax.is_active.is_(True))
        stmt = stmt.order_by(Tax.name)
        return list(self.db.scalars(stmt).all())

    def get_tax(self, tax_id: UUID) -> Tax:
        tax = self.db.get(Tax, tax_id)
        if tax is None:
            raise AppError(
                status_code=404,
                error_code="TAX_NOT_FOUND",
                message="Impuesto no encontrado",
            )
        return tax

    def _ensure_unique_name(self, name: str, exclude_id: UUID | None = None) -> None:
        existing = self.db.scalar(select(Tax).where(Tax.name == name))
        if existing is not None and existing.id != exclude_id:
            raise AppError(
                status_code=409,
                error_code="TAX_NAME_ALREADY_EXISTS",
                message="Ya existe un impuesto con ese nombre",
            )

    def _clear_other_defaults(self, keep_id: UUID | None) -> None:
        for other in self.db.scalars(select(Tax).where(Tax.is_default.is_(True))).all():
            if other.id != keep_id:
                other.is_default = False

    def create_tax(
        self,
        name: str,
        rate,
        description: str | None = None,
        is_active: bool = True,
        is_default: bool = False,
    ) -> Tax:
        clean_name = name.strip()
        self._ensure_unique_name(clean_name)
        tax = Tax(
            name=clean_name,
            rate=rate,
            description=description.strip() if description else None,
            is_active=is_active,
            is_default=is_default,
        )
        self.db.add(tax)
        self.db.flush()
        if is_default:
            self._clear_other_defaults(tax.id)
        self.db.commit()
        self.db.refresh(tax)
        return tax

    def update_tax(self, tax_id: UUID, **fields: Any) -> Tax:
        tax = self.get_tax(tax_id)
        if "name" in fields and fields["name"] is not None:
            clean = fields["name"].strip()
            self._ensure_unique_name(clean, tax.id)
            tax.name = clean
        if "rate" in fields and fields["rate"] is not None:
            tax.rate = fields["rate"]
        if "description" in fields:
            tax.description = (
                fields["description"].strip() if fields["description"] else None
            )
        if "is_active" in fields and fields["is_active"] is not None:
            tax.is_active = fields["is_active"]
        if "is_default" in fields and fields["is_default"] is not None:
            tax.is_default = fields["is_default"]
            if tax.is_default:
                self._clear_other_defaults(tax.id)
        self.db.commit()
        self.db.refresh(tax)
        return tax

    def deactivate_tax(self, tax_id: UUID) -> Tax:
        tax = self.get_tax(tax_id)
        tax.is_active = False
        tax.is_default = False
        self.db.commit()
        self.db.refresh(tax)
        return tax

    def resolve_for_product_tax_id(self, tax_id: UUID | None) -> Tax | None:
        """Impuesto efectivo de un producto/categoría (o None si no aplica)."""
        if tax_id is None:
            return None
        tax = self.db.get(Tax, tax_id)
        if tax is None or not tax.is_active:
            return None
        return tax
