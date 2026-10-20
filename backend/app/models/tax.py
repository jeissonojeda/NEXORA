import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tax(Base):
    """Impuesto configurable (p. ej. IVA 19%).

    Se puede vincular a categorías (impuesto por defecto de la categoría) y a
    productos (override opcional). En las ventas se guarda el porcentaje
    aplicado como snapshot, por lo que cambiar un impuesto no altera el
    histórico.
    """

    __tablename__ = "taxes"
    __table_args__ = (
        CheckConstraint("rate >= 0", name="ck_taxes_rate_non_negative"),
        CheckConstraint("rate <= 100", name="ck_taxes_rate_max"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
