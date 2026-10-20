from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Decimal

RefundMethod = Literal["CASH", "CARD", "TRANSFER", "CREDIT"]
ReturnCondition = Literal["RESALE", "DAMAGED", "REVIEW"]


class SaleReturnItemRequest(BaseModel):
    """Línea de devolución: traza al ítem de venta original."""

    sale_item_id: UUID
    quantity: int = Field(gt=0)
    # RESALE vuelve al stock vendible; DAMAGED/REVIEW no.
    condition: ReturnCondition = "RESALE"


class ExchangeItemRequest(BaseModel):
    """Producto de reemplazo en un cambio."""

    product_id: UUID
    quantity: int = Field(gt=0)
    # Snapshot opcional; si se omite usa el precio actual del producto.
    unit_price: (
        Money | None
    ) = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount: Money = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    tax_rate: Money | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )


class SaleReturnCreate(BaseModel):
    """Devolución total/parcial de una venta CONFIRMED, o cambio."""

    refund_method: RefundMethod
    reason: str | None = Field(default=None, max_length=2000)
    items: list[SaleReturnItemRequest] = Field(min_length=1)
    # Clave de idempotencia: repetir la misma clave retorna la devolución
    # original sin aplicar efectos.
    idempotency_key: str | None = Field(default=None, max_length=100)
    # Cambio: productos de reemplazo en la MISMA transacción; el crédito de
    # lo devuelto se aplica como descuento de la nueva venta y el excedente
    # se reembolsa por refund_method.
    exchange_items: list[ExchangeItemRequest] = Field(default_factory=list)
    # Método de pago de la venta de cambio (default: el de la venta original).
    exchange_payment_method: (
        Literal["CASH", "CARD", "TRANSFER", "CREDIT"] | None
    ) = None

    @model_validator(mode="after")
    def _validate_exchange(self):
        if self.exchange_payment_method == "CREDIT" and not self.exchange_items:
            raise ValueError(
                "exchange_payment_method CREDIT requiere exchange_items"
            )
        return self


class SaleReturnItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_return_id: UUID
    sale_item_id: UUID
    product_id: UUID
    product_name: str | None
    quantity: int
    unit_price: Money
    discount: Money
    tax: Money
    tax_rate: Money
    tax_name: str | None
    subtotal: Money
    total: Money
    restock: bool
    condition: str
    created_at: datetime


class SaleReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    return_number: str
    sale_id: UUID
    sale_number: str | None
    exchange_sale_id: UUID | None
    exchange_sale_number: str | None
    status: str
    return_type: str
    refund_method: str
    reason: str | None
    subtotal: Money
    tax: Money
    total: Money
    credit_applied: Money
    refunded_amount: Money
    created_by: UUID
    created_by_username: str | None
    created_at: datetime
    items: list[SaleReturnItemResponse] = Field(default_factory=list)


class PaginatedSaleReturns(BaseModel):
    items: list[SaleReturnResponse]
    total: int
