"""Modelos locales del licenciamiento (instalación del supermercado).

Estas tablas viven en la base de datos del supermercado y guardan únicamente la
identidad de la instalación y el documento de licencia firmado. No contienen
secretos de firma ni datos del servicio central.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LocalInstallation(Base):
    """Identidad persistente de esta instalación (una sola fila activa)."""

    __tablename__ = "license_local_installation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    installation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128))
    machine_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LocalLicense(Base):
    """Licencia activada localmente (documento firmado + estado)."""

    __tablename__ = "license_local"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_key: Mapped[str] = mapped_column(String(64), index=True)
    license_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    plan_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_type: Mapped[str] = mapped_column(String(20))
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    max_installations: Mapped[int] = mapped_column(default=1)

    installation_id: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128))

    document_json: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    grace_days: Mapped[int] = mapped_column(default=0)
    updates_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clock_rollback: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
