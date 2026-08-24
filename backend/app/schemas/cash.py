from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Decimal

REGISTER_STATUSES = ("OPEN", "CLOSED", "CANCELLED")

ManualMovementType = Literal["CASH_IN", "CASH_OUT"]


class RegisterOpenRequest(BaseModel):
    opening_amount: Money = Field(ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class RegisterCloseRequest(BaseModel):
    counted_amount: Money = Field(ge=0, max_digits=14, decimal_places=2)


class ManualMovementCreate(BaseModel):
    movement_type: ManualMovementType
    amount: Money = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(min_length=3, max_length=500)


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    register_id: UUID
    user_id: UUID
    user_username: str | None
    movement_type: str
    payment_method: str | None
    amount: Money
    description: str
    reference_type: str | None
    reference_id: str | None
    created_at: datetime


class CashSummaryResponse(BaseModel):
    opening_total: Money
    cash_in_total: Money
    cash_out_total: Money
    cash_sales_total: Money
    card_sales_total: Money
    transfer_sales_total: Money
    credit_sales_count: int
    cash_receivable_payments_total: Money
    card_receivable_payments_total: Money
    transfer_receivable_payments_total: Money
    movement_count: int
    expected_cash: Money


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_username: str | None
    status: str
    opening_amount: Money
    notes: str | None
    opened_at: datetime
    closed_at: datetime | None
    closed_by_id: UUID | None
    closed_by_username: str | None
    expected_amount: Money | None
    counted_amount: Money | None
    difference: Money | None


class RegisterDetailResponse(RegisterResponse):
    summary: CashSummaryResponse


class PaginatedRegisters(BaseModel):
    items: list[RegisterResponse]
    total: int


class PaginatedMovements(BaseModel):
    items: list[MovementResponse]
    total: int
