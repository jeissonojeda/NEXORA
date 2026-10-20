"""Modelos del servicio central de licencias.

Estas tablas viven SOLO en la base de datos del servicio central. No contienen
datos de negocio del supermercado (ventas, clientes, inventario): la activación
solo intercambia la información estrictamente necesaria.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.licensing.server.db import LicenseBase


class LicenseCustomer(LicenseBase):
    __tablename__ = "license_customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    licenses = relationship("License", back_populates="customer", lazy="selectin")


class LicensePlan(LicenseBase):
    __tablename__ = "license_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    license_type: Mapped[str] = mapped_column(String(20))
    default_max_installations: Mapped[int] = mapped_column(Integer, default=1)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    licenses = relationship("License", back_populates="plan", lazy="selectin")


class License(LicenseBase):
    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("license_customers.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("license_plans.id", ondelete="SET NULL"), nullable=True
    )
    license_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    max_installations: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    grace_days: Mapped[int] = mapped_column(Integer, default=0)
    updates_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    min_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    max_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("LicenseCustomer", back_populates="licenses")
    plan = relationship("LicensePlan", back_populates="licenses")
    installations = relationship(
        "LicenseInstallation", back_populates="license", lazy="selectin"
    )


class LicenseInstallation(LicenseBase):
    __tablename__ = "license_installations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    installation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128), index=True)
    machine_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    license = relationship("License", back_populates="installations")


class LicenseActivationRequest(LicenseBase):
    """Solicitud de activación manual (código de solicitud/respuesta)."""

    __tablename__ = "license_activation_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    license_key: Mapped[str] = mapped_column(String(64), index=True)
    license_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True
    )
    installation_id: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(64))
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    response_document_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LicenseTransfer(LicenseBase):
    __tablename__ = "license_transfers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    from_installation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    to_installation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LicenseAuditEvent(LicenseBase):
    __tablename__ = "license_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    license_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True
    )
    installation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class LicenseAdmin(LicenseBase):
    """Administrador global del producto (propietario de NEXORA).

    Es independiente de los usuarios ADMIN de cada supermercado.
    """

    __tablename__ = "license_admins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
