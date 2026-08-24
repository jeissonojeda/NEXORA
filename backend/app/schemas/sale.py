from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Decimal

SALE_STATUSES = ("DRAFT", "CONFIRMED", "CANCELLED")

PaymentMethod = Literal["CASH", "CARD", "TRANSFER", "CREDIT"]


class SaleItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    # Snapshot opcional del precio de venta; si se omite se toma el precio
    # actual del producto al momento de agregar el ítem.
    unit_price: Money | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    discount: Money = Field(default=Decimal("0"), ge=0, max_digits=12,
                             decimal_places=2)
    tax: Money = Field(default=Decimal("0"), ge=0, max_digits=12,
                        decimal_places=2)


class SaleItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    unit_price: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax: Money | None = Field(default=None, ge=0, max_digits=12,
                              decimal_places=2)


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_id: UUID
    product_id: UUID
    product_name: str | None
    quantity: int
    unit_price: Money
    discount: Money
    tax: Money
    subtotal: Money
    total: Money
    created_at: datetime


class SaleCreate(BaseModel):
    # Venta sin cliente permitida (consumidor final); obligatoria para CREDIT.
    customer_id: UUID | None = None
    payment_method: PaymentMethod
    amount_paid: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    discount: Money = Field(default=Decimal("0"), ge=0, max_digits=14,
                            decimal_places=2)
    tax: Money = Field(default=Decimal("0"), ge=0, max_digits=14,
                       decimal_places=2)
    items: list[SaleItemCreate] = Field(default_factory=list)


class SaleUpdate(BaseModel):
    customer_id: UUID | None = None
    payment_method: PaymentMethod | None = None
    amount_paid: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    discount: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    tax: Money | None = Field(default=None, ge=0, max_digits=14,
                              decimal_places=2)


class CustomerBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class UserBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_number: str
    status: str
    customer_id: UUID | None
    customer: CustomerBriefResponse | None
    payment_method: str
    amount_paid: Money
    change_due: Money
    subtotal: Money
    discount: Money
    tax: Money
    total: Money
    notes: str | None
    created_by: UUID
    created_by_username: str | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None


class SaleDetailResponse(SaleResponse):
    items: list[SaleItemResponse]


class PaginatedSales(BaseModel):
    items: list[SaleResponse]
    total: int
