"""Esquemas Pydantic del servicio central de licencias.

No exponen directamente los modelos SQLAlchemy.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ----------------------------------------------------------------------
# Autenticación administrativa
# ----------------------------------------------------------------------
class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    email: str
    is_active: bool


# ----------------------------------------------------------------------
# Clientes
# ----------------------------------------------------------------------
class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    email: str | None = Field(None, max_length=255)
    identification: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str | None = None
    identification: str | None = None
    phone: str | None = None
    is_active: bool
    created_at: datetime


# ----------------------------------------------------------------------
# Planes
# ----------------------------------------------------------------------
class PlanCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    license_type: str = Field(..., pattern="^(PERPETUAL|MONTHLY|ANNUAL)$")
    default_max_installations: int = Field(1, ge=1, le=1000)
    duration_days: int | None = Field(None, ge=1, le=36500)
    features: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    license_type: str
    default_max_installations: int
    duration_days: int | None = None
    features: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime


# ----------------------------------------------------------------------
# Licencias
# ----------------------------------------------------------------------
class LicenseCreate(BaseModel):
    customer_id: UUID
    plan_id: UUID | None = None
    license_type: str = Field(..., pattern="^(PERPETUAL|MONTHLY|ANNUAL)$")
    max_installations: int = Field(1, ge=1, le=1000)
    features: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    grace_days: int = Field(0, ge=0, le=3650)
    updates_until: datetime | None = None
    min_version: str | None = Field(None, max_length=32)
    max_version: str | None = Field(None, max_length=32)
    license_key: str | None = Field(
        None, max_length=64, description="Código público; se genera si se omite"
    )


class LicenseStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|SUSPENDED|REVOKED)$")
    reason: str | None = Field(None, max_length=255)


class InstallationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    installation_id: str
    machine_label: str | None = None
    app_version: str | None = None
    status: str
    activated_at: datetime
    last_seen_at: datetime | None = None
    released_at: datetime | None = None
    release_reason: str | None = None


class LicenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    license_key: str
    customer_id: UUID
    customer_name: str | None = None
    plan_id: UUID | None = None
    license_type: str
    status: str
    features: list[str] = Field(default_factory=list)
    max_installations: int
    active_installations: int = 0
    expires_at: datetime | None = None
    grace_days: int
    updates_until: datetime | None = None
    min_version: str | None = None
    max_version: str | None = None
    activated_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    created_at: datetime


# ----------------------------------------------------------------------
# Instalaciones / transferencias
# ----------------------------------------------------------------------
class ReleaseInstallationRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


class TransferCreate(BaseModel):
    license_id: UUID
    to_installation_id: str | None = Field(None, max_length=64)
    from_installation_id: str | None = Field(None, max_length=64)
    reason: str = Field(..., min_length=1, max_length=255)


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    license_id: UUID
    from_installation_id: str | None = None
    to_installation_id: str | None = None
    reason: str
    status: str
    resolved_by: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


# ----------------------------------------------------------------------
# Activación (público)
# ----------------------------------------------------------------------
class PublicActivationRequest(BaseModel):
    license_key: str = Field(..., min_length=4, max_length=64)
    installation_id: str = Field(..., min_length=4, max_length=64)
    fingerprint: str = Field(..., min_length=4, max_length=256)
    app_version: str | None = Field(None, max_length=32)
    machine_label: str | None = Field(None, max_length=120)
    nonce: str | None = Field(None, max_length=64)


class PublicActivationResponse(BaseModel):
    status: str
    document: dict[str, Any]


class PublicLicenseStatus(BaseModel):
    license_key: str
    status: str
    license_type: str
    expires_at: datetime | None = None
    max_installations: int
    active_installations: int


# ----------------------------------------------------------------------
# Activación manual (administración)
# ----------------------------------------------------------------------
class ManualRequestPublic(BaseModel):
    request_code: str = Field(..., min_length=8, max_length=8192)


class ManualRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    license_key: str
    installation_id: str
    app_version: str | None = None
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None


class ManualAuthorizeResponse(BaseModel):
    status: str
    request_id: UUID
    response_document: dict[str, Any] | None = None


# ----------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------
class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor: str | None = None
    action: str
    license_id: UUID | None = None
    installation_id: str | None = None
    result: str
    reason: str | None = None
    created_at: datetime
