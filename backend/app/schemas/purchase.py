from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Decimal

PURCHASE_STATUSES = ("DRAFT", "CONFIRMED", "CANCELLED")


class PurchaseItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    unit_cost: Money = Field(ge=0, max_digits=12, decimal_places=2)
    discount: Money = Field(default=Decimal("0"), ge=0, max_digits=12,
                            decimal_places=2)
    tax: Money = Field(default=Decimal("0"), ge=0, max_digits=12,
                       decimal_places=2)


class PurchaseItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    unit_cost: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax: Money | None = Field(default=None, ge=0, max_digits=12,
                              decimal_places=2)


class PurchaseItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_id: UUID
    product_id: UUID
    product_name: str | None
    quantity: int
    unit_cost: Money
    discount: Money
    tax: Money
    subtotal: Money
    total: Money
    created_at: datetime


class PurchaseCreate(BaseModel):
    supplier_id: UUID
    notes: str | None = Field(default=None, max_length=2000)
    discount: Money = Field(default=Decimal("0"), ge=0, max_digits=14,
                            decimal_places=2)
    tax: Money = Field(default=Decimal("0"), ge=0, max_digits=14,
                       decimal_places=2)
    items: list[PurchaseItemCreate] = Field(default_factory=list)


class PurchaseUpdate(BaseModel):
    supplier_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    discount: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    tax: Money | None = Field(default=None, ge=0, max_digits=14,
                              decimal_places=2)


class SupplierBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_number: str
    status: str
    supplier_id: UUID
    supplier: SupplierBriefResponse
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


class PurchaseDetailResponse(PurchaseResponse):
    items: list[PurchaseItemResponse]


class PaginatedPurchases(BaseModel):
    items: list[PurchaseResponse]
    total: int
