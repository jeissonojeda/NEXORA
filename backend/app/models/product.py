import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("purchase_price >= 0", name="ck_products_purchase_price"),
        CheckConstraint("sale_price >= 0", name="ck_products_sale_price"),
        CheckConstraint("profit_percent >= 0", name="ck_products_profit_percent"),
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("minimum_stock >= 0", name="ck_products_minimum_stock"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), index=True)
    barcode: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Porcentaje de utilidad aplicado sobre el costo de compra.
    profit_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Override del impuesto; si es NULL se usa el impuesto de la categoría.
    tax_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxes.id", ondelete="SET NULL"), nullable=True
    )
    stock: Mapped[int] = mapped_column(Integer, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category = relationship("Category", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    tax = relationship("Tax")

    @property
    def effective_tax(self) -> "object | None":
        """Impuesto efectivo: el del producto o, si no tiene, el de su categoría."""
        if self.tax is not None:
            return self.tax
        category = self.category
        if category is not None:
            return category.tax
        return None
