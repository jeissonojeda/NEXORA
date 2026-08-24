import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "credit_limit >= 0", name="ck_customers_credit_limit"
        ),
        CheckConstraint(
            "current_balance >= 0", name="ck_customers_current_balance"
        ),
        CheckConstraint(
            "NOT credit_enabled OR current_balance <= credit_limit",
            name="ck_customers_balance_within_limit",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identification: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    credit_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    receivables = relationship(
        "ReceivableAccount",
        back_populates="customer",
        order_by="ReceivableAccount.created_at.desc()",
    )

    @property
    def credit_available(self) -> Decimal:
        """Crédito disponible; siempre escala 2 y nunca negativo."""
        if not self.credit_enabled:
            return Decimal("0.00")
        available = (self.credit_limit - self.current_balance).quantize(
            Decimal("0.01")
        )
        return available if available > Decimal("0") else Decimal("0.00")


class ReceivableAccountStatuses:
    OPEN = "OPEN"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


VALID_RECEIVABLE_STATUSES = frozenset(
    {
        ReceivableAccountStatuses.OPEN,
        ReceivableAccountStatuses.PARTIALLY_PAID,
        ReceivableAccountStatuses.PAID,
        ReceivableAccountStatuses.CANCELLED,
    }
)


class ReceivableReferenceTypes:
    """Orígenes de una cuenta por cobrar.

    SALE se usará cuando exista el módulo de ventas (Fase 7);
    MANUAL es el puente administrativo temporal.
    """

    MANUAL = "MANUAL"
    SALE = "SALE"


class PaymentMethods:
    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    OTHER = "OTHER"


VALID_PAYMENT_METHODS = frozenset(
    {
        PaymentMethods.CASH,
        PaymentMethods.CARD,
        PaymentMethods.TRANSFER,
        PaymentMethods.OTHER,
    }
)


class ReceivableAccount(Base):
    __tablename__ = "receivable_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')",
            name="ck_receivable_accounts_status",
        ),
        CheckConstraint(
            "original_amount > 0", name="ck_receivable_accounts_original_positive"
        ),
        CheckConstraint(
            "paid_amount >= 0", name="ck_receivable_accounts_paid_non_negative"
        ),
        CheckConstraint(
            "paid_amount <= original_amount",
            name="ck_receivable_accounts_paid_within_original",
        ),
        CheckConstraint(
            "balance = original_amount - paid_amount",
            name="ck_receivable_accounts_balance_math",
        ),
        CheckConstraint(
            "balance >= 0", name="ck_receivable_accounts_balance_non_negative"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    reference_type: Mapped[str] = mapped_column(String(30), default="MANUAL")
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0")
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ReceivableAccountStatuses.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("Customer", back_populates="receivables")
    payments = relationship(
        "ReceivablePayment",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="ReceivablePayment.created_at",
    )


class ReceivablePayment(Base):
    __tablename__ = "receivable_payments"
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('CASH', 'CARD', 'TRANSFER', 'OTHER')",
            name="ck_receivable_payments_method",
        ),
        CheckConstraint(
            "amount > 0", name="ck_receivable_payments_amount_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receivable_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("receivable_accounts.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_method: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    account = relationship(
        "ReceivableAccount", back_populates="payments"
    )
    user = relationship("User")

    @property
    def created_by_username(self) -> str | None:
        if self.user is not None:
            return self.user.username
        return None
