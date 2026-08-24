from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.customer import CustomerResponse

Money = Decimal

VALID_RECEIVABLE_STATUSES = ("OPEN", "PARTIALLY_PAID", "PAID", "CANCELLED")
PaymentMethodLiteral = Literal["CASH", "CARD", "TRANSFER", "OTHER"]


DEFAULT_ACCOUNTS_LIMIT = 20
DEFAULT_PAYMENTS_LIMIT = 20


class ReceivableCreate(BaseModel):
    """Puente administrativo temporal hasta Fase 7 (ventas).

    En producción las cuentas por cobrar se originarán desde SalesService
    vía CustomerCreditService.create_receivable(); este endpoint existe
    solo para administración y pruebas del módulo de crédito.
    """

    customer_id: UUID
    original_amount: Money = Field(gt=0, max_digits=14, decimal_places=2)
    description: str | None = Field(default=None, max_length=500)
    due_date: date | None = None


class ReceivablePaymentCreate(BaseModel):
    amount: Money = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: PaymentMethodLiteral
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=100)


class CustomerBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ReceivableAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    customer: CustomerBriefResponse
    reference_type: str
    reference_id: str | None
    description: str | None
    original_amount: Money
    paid_amount: Money
    balance: Money
    due_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class PaginatedReceivables(BaseModel):
    items: list[ReceivableAccountResponse]
    total: int


class ReceivablePaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    receivable_account_id: UUID
    amount: Money
    payment_method: str
    reference: str | None
    notes: str | None
    idempotency_key: str | None
    created_by: UUID
    created_by_username: str | None
    created_at: datetime


class PaginatedReceivablePayments(BaseModel):
    items: list[ReceivablePaymentResponse]
    total: int


class CreditSummary(BaseModel):
    credit_enabled: bool
    credit_limit: Money
    current_balance: Money
    credit_available: Money


class ReceivableStatusCounts(BaseModel):
    open_count: int = 0
    partially_paid_count: int = 0
    paid_count: int = 0
    cancelled_count: int = 0
    total_balance: Money = Decimal("0")


class CustomerStatementResponse(BaseModel):
    customer: CustomerResponse
    credit: CreditSummary
    summary: ReceivableStatusCounts
    accounts: PaginatedReceivables
    payments: PaginatedReceivablePayments
