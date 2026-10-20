import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReturnStatuses:
    """Estado de una devolución.

    COMPLETED: devolución aplicada (inmutable salvo anulación manual).
    CANCELLED: anulación posterior (write-off administrativo); conserva el
    registro como historial, no borra nada.
    """

    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


VALID_RETURN_STATUSES = frozenset(
    {ReturnStatuses.COMPLETED, ReturnStatuses.CANCELLED}
)


class ReturnTypes:
    """Tipo de operación de devolución.

    RETURN: devolución con reembolso total/parcial al cliente.
    EXCHANGE: devolución de productos + nueva venta de reemplazo en la MISMA
    transacción (cambio); el crédito se aplica a la nueva venta y el excedente
    se reembolsa según el método elegido.
    """

    RETURN = "RETURN"
    EXCHANGE = "EXCHANGE"


VALID_RETURN_TYPES = frozenset({ReturnTypes.RETURN, ReturnTypes.EXCHANGE})


class RefundMethods:
    """Métodos de reembolso realmente implementados.

    CASH: egreso de efectivo (CASH_OUT) desde la caja abierta del usuario.
    CARD/TRANSFER: reembolso externo (la devolución del pago con tarjeta o
    transferencia ocurre fuera del sistema); se registra para trazabilidad.
    CREDIT: reduce la cuenta por cobrar de la venta original y el saldo del
    cliente; solo válido si la venta tuvo cuenta asociada y el monto no
    excede el saldo pendiente.
    """

    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    CREDIT = "CREDIT"


VALID_REFUND_METHODS = frozenset(
    {
        RefundMethods.CASH,
        RefundMethods.CARD,
        RefundMethods.TRANSFER,
        RefundMethods.CREDIT,
    }
)


class ReturnConditions:
    """Condición del producto devuelto.

    RESALE: apto para reventa → vuelve al stock vendible (movimiento RETURN).
    DAMAGED: dañado → NO vuelve al stock vendible.
    REVIEW: pendiente de revisión → NO vuelve al stock vendible.
    """

    RESALE = "RESALE"
    DAMAGED = "DAMAGED"
    REVIEW = "REVIEW"


VALID_RETURN_CONDITIONS = frozenset(
    {ReturnConditions.RESALE, ReturnConditions.DAMAGED, ReturnConditions.REVIEW}
)


class SaleReturn(Base):
    """Devolución o cambio de una venta CONFIRMED.

    La venta original nunca se modifica (es inmutable); la devolución es un
    documento aparte vinculado vía sale_id, con numeración propia
    DEV-YYYY-NNNNNN e idempotencia por clave única.
    """

    __tablename__ = "sale_returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('COMPLETED', 'CANCELLED')",
            name="ck_sale_returns_status",
        ),
        CheckConstraint(
            "return_type IN ('RETURN', 'EXCHANGE')",
            name="ck_sale_returns_type",
        ),
        CheckConstraint(
            "refund_method IN ('CASH', 'CARD', 'TRANSFER', 'CREDIT')",
            name="ck_sale_returns_refund_method",
        ),
        CheckConstraint("subtotal >= 0", name="ck_sale_returns_subtotal"),
        CheckConstraint("tax >= 0", name="ck_sale_returns_tax"),
        CheckConstraint("total >= 0", name="ck_sale_returns_total"),
        CheckConstraint(
            "credit_applied >= 0", name="ck_sale_returns_credit_applied"
        ),
        CheckConstraint(
            "refunded_amount >= 0", name="ck_sale_returns_refunded_amount"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    return_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), index=True
    )
    # Venta de reemplazo creada en un EXCHANGE (NULL en RETURN puro).
    exchange_sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ReturnStatuses.COMPLETED
    )
    return_type: Mapped[str] = mapped_column(
        String(20), default=ReturnTypes.RETURN
    )
    refund_method: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    # Monto del crédito aplicado como descuento a la venta de cambio.
    credit_applied: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    # Monto reembolsado fuera del crédito de cambio (efectivo o externo).
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sale = relationship("Sale", foreign_keys=[sale_id])
    exchange_sale = relationship("Sale", foreign_keys=[exchange_sale_id])
    user = relationship("User")
    items = relationship(
        "SaleReturnItem",
        back_populates="sale_return",
        cascade="all, delete-orphan",
        order_by="SaleReturnItem.created_at",
    )

    @property
    def created_by_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None

    @property
    def sale_number(self) -> str | None:
        if self.sale is not None:
            return self.sale.sale_number
        return None

    @property
    def exchange_sale_number(self) -> str | None:
        if self.exchange_sale is not None:
            return self.exchange_sale.sale_number
        return None


class SaleReturnItem(Base):
    """Línea de una devolución, trazada al ítem de venta original."""

    __tablename__ = "sale_return_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_return_items_qty"),
        CheckConstraint("unit_price >= 0", name="ck_sale_return_items_price"),
        CheckConstraint("discount >= 0", name="ck_sale_return_items_discount"),
        CheckConstraint("tax >= 0", name="ck_sale_return_items_tax"),
        CheckConstraint("subtotal >= 0", name="ck_sale_return_items_subtotal"),
        CheckConstraint("total >= 0", name="ck_sale_return_items_total"),
        CheckConstraint(
            "condition IN ('RESALE', 'DAMAGED', 'REVIEW')",
            name="ck_sale_return_items_condition",
        ),
        Index(
            "ux_sale_return_items_sale_item",
            "sale_return_id",
            "sale_item_id",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_return_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sale_returns.id", ondelete="CASCADE"), index=True
    )
    sale_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sale_items.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    # Snapshot histórico tomado del ítem de venta original.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    tax_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # True si la cantidad volvió al stock vendible (condition RESALE).
    restock: Mapped[bool] = mapped_column(Boolean, default=False)
    condition: Mapped[str] = mapped_column(String(20), default=ReturnConditions.RESALE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sale_return = relationship("SaleReturn", back_populates="items")
    sale_item = relationship("SaleItem")
    product = relationship("Product")

    @property
    def product_name(self) -> str | None:
        if self.product is not None:
            return self.product.name
        return None
