from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tax import TaxBrief

Money = Decimal


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SupplierBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    barcode: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)


class ProductCreate(ProductBase):
    purchase_price: Money = Field(ge=0, max_digits=12, decimal_places=2, default=0)
    # Opcional: si no se envía, el backend lo calcula a partir de
    # purchase_price + profit_percent (utilidad sobre el costo).
    sale_price: Money | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    profit_percent: Money = Field(
        default=Decimal("0"), ge=0, max_digits=5, decimal_places=2
    )
    unit: str | None = Field(default=None, max_length=20)
    category_id: UUID
    supplier_id: UUID | None = None
    tax_id: UUID | None = None
    stock: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    barcode: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    purchase_price: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    sale_price: Money | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    profit_percent: Money | None = Field(
        default=None, ge=0, max_digits=5, decimal_places=2
    )
    unit: str | None = Field(default=None, max_length=20)
    category_id: UUID | None = None
    supplier_id: UUID | None = None
    tax_id: UUID | None = None
    minimum_stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    barcode: str | None
    description: str | None
    purchase_price: Money
    sale_price: Money
    profit_percent: Money
    unit: str | None
    category: CategoryBrief
    supplier: SupplierBrief | None
    tax: TaxBrief | None
    effective_tax: TaxBrief | None
    stock: int
    minimum_stock: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
