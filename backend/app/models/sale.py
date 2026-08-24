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


class SaleStatuses:
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


VALID_SALE_STATUSES = frozenset(
    {SaleStatuses.DRAFT, SaleStatuses.CONFIRMED, SaleStatuses.CANCELLED}
)


class PaymentMethods:
    """Métodos de pago de una venta.

    CREDIT registra la venta a crédito: al confirmar se genera una
    ReceivableAccount por el total y el saldo del cliente sube vía
    CustomerCreditService. La estructura es extensible: nuevos métodos
    requieren agregar el valor al CHECK de BD, este bloque y el literal
    del schema.
    """

    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    CREDIT = "CREDIT"


VALID_PAYMENT_METHODS = frozenset(
    {
        PaymentMethods.CASH,
        PaymentMethods.CARD,
        PaymentMethods.TRANSFER,
        PaymentMethods.CREDIT,
    }
)

# Métodos que pagan el total al momento de la venta (a diferencia de CASH,
# donde el cliente puede entregar más y recibir vuelto).
FULL_PAYMENT_METHODS = frozenset({PaymentMethods.CARD, PaymentMethods.TRANSFER})


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'CANCELLED')",
            name="ck_sales_status",
        ),
        CheckConstraint(
            "payment_method IN ('CASH', 'CARD', 'TRANSFER', 'CREDIT')",
            name="ck_sales_payment_method",
        ),
        CheckConstraint("subtotal >= 0", name="ck_sales_subtotal"),
        CheckConstraint("discount >= 0", name="ck_sales_discount"),
        CheckConstraint("tax >= 0", name="ck_sales_tax"),
        CheckConstraint("total >= 0", name="ck_sales_total"),
        CheckConstraint("amount_paid >= 0", name="ck_sales_amount_paid"),
        CheckConstraint("change_due >= 0", name="ck_sales_change_due"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=SaleStatuses.DRAFT)
    # Venta sin cliente permitida (consumidor final); obligatoria para CREDIT.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    payment_method: Mapped[str] = mapped_column(String(20))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    change_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
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

    customer = relationship("Customer")
    user = relationship("User")
    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.created_at",
    )

    @property
    def created_by_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None

    @property
    def customer_name(self) -> str | None:
        if self.customer is not None:
            return self.customer.name
        return None


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sale_items_unit_price"),
        CheckConstraint("discount >= 0", name="ck_sale_items_discount"),
        CheckConstraint("tax >= 0", name="ck_sale_items_tax"),
        CheckConstraint("subtotal >= 0", name="ck_sale_items_subtotal"),
        CheckConstraint("total >= 0", name="ck_sale_items_total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    # Snapshot histórico del precio de venta; cambiar Product.sale_price
    # nunca recalcula ventas pasadas.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")

    @property
    def product_name(self) -> str | None:
        if self.product is not None:
            return self.product.name
        return None
