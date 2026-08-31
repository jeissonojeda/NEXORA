"""Modelos de auditoría de IA operativa (Fase 12 - NEXORA AI Operativo).

Registran de forma inmutable:
  - ``AIActionHistory``: cada acción propuesta/confirmada/rechazada por la IA,
    con quién, qué arguments, resultado y claves de idempotencia.
  - ``AIInvoiceScan``: cada factura escaneada (Gemini Vision), útil para
    detección de duplicados y trazabilidad de proveedores/facturas.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIActionStatuses:
    PREVIEW = "PREVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AIActionHistory(Base):
    __tablename__ = "ai_action_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), index=True)
    action_name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), index=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIInvoiceScan(Base):
    __tablename__ = "ai_invoice_scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    scan_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_invoice_scans.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
