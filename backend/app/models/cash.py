import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RegisterStatuses:
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


VALID_REGISTER_STATUSES = frozenset(
    {RegisterStatuses.OPEN, RegisterStatuses.CLOSED,
     RegisterStatuses.CANCELLED}
)


class MovementTypes:
    """Tipos de movimiento de caja.

    Efectivo físico: OPENING (+), SALE con CASH (+), RECEIVABLE_PAYMENT
    con CASH (+), CASH_IN (+), CASH_OUT (-). CARD/TRANSFER se registran
    para trazabilidad pero NO mueven el efectivo esperado. ADJUSTMENT
    queda reservado para correcciones futuras de cierre.
    """

    OPENING = "OPENING"
    SALE = "SALE"
    RECEIVABLE_PAYMENT = "RECEIVABLE_PAYMENT"
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    ADJUSTMENT = "ADJUSTMENT"


VALID_MOVEMENT_TYPES = frozenset(
    {
        MovementTypes.OPENING,
        MovementTypes.SALE,
        MovementTypes.RECEIVABLE_PAYMENT,
        MovementTypes.CASH_IN,
        MovementTypes.CASH_OUT,
        MovementTypes.ADJUSTMENT,
    }
)

# Tipos que suman efectivo (con payment_method CASH cuando aplique).
CASH_INFLOW_TYPES = frozenset(
    {MovementTypes.OPENING, MovementTypes.CASH_IN}
)
# Tipos que restan efectivo.
CASH_OUTFLOW_TYPES = frozenset({MovementTypes.CASH_OUT})
# Tipos cuyo efecto depende del método de pago.
METHOD_DEPENDENT_TYPES = frozenset(
    {MovementTypes.SALE, MovementTypes.RECEIVABLE_PAYMENT}
)


def cash_delta(movement_type: str, payment_method: str | None) -> Decimal:
    """Efecto de un movimiento sobre el efectivo esperado de la caja."""
    if movement_type in CASH_INFLOW_TYPES:
        return Decimal("1")
    if movement_type in CASH_OUTFLOW_TYPES:
        return Decimal("-1")
    if movement_type in METHOD_DEPENDENT_TYPES:
        if payment_method == "CASH":
            return Decimal("1")
        # CARD/TRANSFER/otros medios: trazabilidad sin efectivo físico.
        return Decimal("0")
    return Decimal("0")


class CashReferenceTypes:
    """Orígenes externos de un movimiento de caja."""

    SALE = "SALE"
    RECEIVABLE_PAYMENT = "RECEIVABLE_PAYMENT"
    SALE_RETURN = "SALE_RETURN"


class CashRegister(Base):
    __tablename__ = "cash_registers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'CANCELLED')",
            name="ck_cash_registers_status",
        ),
        CheckConstraint(
            "opening_amount >= 0", name="ck_cash_registers_opening_non_negative"
        ),
        CheckConstraint(
            "expected_amount IS NULL OR expected_amount >= 0",
            name="ck_cash_registers_expected_non_negative",
        ),
        CheckConstraint(
            "counted_amount IS NULL OR counted_amount >= 0",
            name="ck_cash_registers_counted_non_negative",
        ),
        # Un solo turno abierto por cajero (índice parcial en PG y SQLite).
        Index(
            "ux_cash_registers_user_open",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'OPEN'"),
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Cajero responsable del turno (quien abre la caja).
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=RegisterStatuses.OPEN
    )
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Quien ejecuta el cierre (normalmente el mismo cajero).
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    expected_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    counted_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    difference: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    user = relationship("User", foreign_keys=[user_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    movements = relationship(
        "CashMovement",
        back_populates="register",
        cascade="all, delete-orphan",
        order_by="CashMovement.created_at",
    )

    @property
    def user_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None

    @property
    def closed_by_username(self) -> str | None:
        if self.closed_by is not None:
            return self.closed_by.username
        return None


class CashMovement(Base):
    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('OPENING', 'SALE', 'RECEIVABLE_PAYMENT',"
            " 'CASH_IN', 'CASH_OUT', 'ADJUSTMENT')",
            name="ck_cash_movements_type",
        ),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN"
            " ('CASH', 'CARD', 'TRANSFER')",
            name="ck_cash_movements_method",
        ),
        CheckConstraint(
            "(movement_type = 'OPENING' AND amount >= 0)"
            " OR (movement_type <> 'OPENING' AND amount > 0)",
            name="ck_cash_movements_amount_positive",
        ),
        # Un movimiento por referencia externa (venta / pago de cuenta):
        # idempotencia estructural ante reintentos o carreras.
        Index(
            "ux_cash_movements_reference",
            "reference_type",
            "reference_id",
            unique=True,
            sqlite_where=text("reference_id IS NOT NULL"),
            postgresql_where=text("reference_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    register_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_registers.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    movement_type: Mapped[str] = mapped_column(String(30))
    # Método del medio de pago original (ventas y abonos); NULL en manuales.
    payment_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(String(500))
    reference_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    register = relationship("CashRegister", back_populates="movements")
    user = relationship("User")

    @property
    def user_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None
