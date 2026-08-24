from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Money = Decimal


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    identification: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    credit_enabled: bool = False
    credit_limit: Money = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=2
    )


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    identification: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    credit_enabled: bool | None = None
    credit_limit: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    identification: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    notes: str | None
    is_active: bool
    credit_enabled: bool
    credit_limit: Money
    current_balance: Money
    credit_available: Money
    created_at: datetime
    updated_at: datetime


class PaginatedCustomers(BaseModel):
    items: list[CustomerResponse]
    total: int


CUSTOMER_SORT_FIELDS = {"name", "created_at", "current_balance", "credit_limit"}
