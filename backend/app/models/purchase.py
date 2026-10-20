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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseStatuses:
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


VALID_PURCHASE_STATUSES = frozenset(
    {PurchaseStatuses.DRAFT, PurchaseStatuses.CONFIRMED,
     PurchaseStatuses.CANCELLED}
)


class MovementReferences:
    """Tipos de entidad que pueden referenciar movimientos de inventario.

    reference_type + reference_id permiten trazar cada movimiento hasta su
    documento origen (compra, venta, ajuste manual).
    """

    PURCHASE = "PURCHASE"
    SALE = "SALE"
    SALE_RETURN = "SALE_RETURN"


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'CANCELLED')",
            name="ck_purchases_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_purchases_subtotal"),
        CheckConstraint("discount >= 0", name="ck_purchases_discount"),
        CheckConstraint("tax >= 0", name="ck_purchases_tax"),
        CheckConstraint("total >= 0", name="ck_purchases_total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    purchase_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=PurchaseStatuses.DRAFT)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    supplier = relationship("Supplier")
    user = relationship("User")
    items = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseItem.created_at",
    )

    @property
    def created_by_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_items_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_purchase_items_unit_cost"),
        CheckConstraint("discount >= 0", name="ck_purchase_items_discount"),
        CheckConstraint("tax >= 0", name="ck_purchase_items_tax"),
        CheckConstraint("subtotal >= 0", name="ck_purchase_items_subtotal"),
        CheckConstraint("total >= 0", name="ck_purchase_items_total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchases.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")

    @property
    def product_name(self) -> str | None:
        if self.product is not None:
            return self.product.name
        return None
