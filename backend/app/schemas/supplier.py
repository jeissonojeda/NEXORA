from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    identification: str | None = Field(default=None, max_length=50)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    identification: str | None = Field(default=None, max_length=50)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    identification: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierDetailResponse(SupplierResponse):
    products_count: int


class PaginatedSuppliers(BaseModel):
    items: list[SupplierDetailResponse]
    total: int


SUPPLIER_SORT_FIELDS = {"name", "created_at", "updated_at"}
