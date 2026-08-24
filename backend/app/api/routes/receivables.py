from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.receivable import (
    PaginatedReceivablePayments,
    PaginatedReceivables,
    ReceivableAccountResponse,
    ReceivableCreate,
    ReceivablePaymentCreate,
    ReceivablePaymentResponse,
    VALID_RECEIVABLE_STATUSES,
)
from app.services.receivable_service import ReceivableService

router = APIRouter(prefix="/receivables", tags=["Cuentas por cobrar"])


@router.get("", response_model=PaginatedReceivables)
def list_receivables(
    _: Annotated[User, Depends(require_permission("receivables.read"))],
    db: Annotated[Session, Depends(get_db)],
    customer_id: UUID | None = None,
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(OPEN|PARTIALLY_PAID|PAID|CANCELLED)$")
    ] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedReceivables:
    assert status_filter in VALID_RECEIVABLE_STATUSES or status_filter is None
    items, total = ReceivableService(db).list_accounts(
        customer_id=customer_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        due_from=due_from,
        due_to=due_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedReceivables(
        items=[ReceivableAccountResponse.model_validate(a) for a in items],
        total=total,
    )


@router.post(
    "", response_model=ReceivableAccountResponse, status_code=status.HTTP_201_CREATED
)
def create_receivable(
    payload: ReceivableCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("receivables.create"))],
) -> ReceivableAccountResponse:
    """Puente administrativo hasta Fase 7 (las ventas crearán cuentas vía servicio)."""
    data = payload.model_dump()
    data.setdefault("reference_type", "MANUAL")
    account = ReceivableService(db).create_receivable(**data)
    return ReceivableAccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=ReceivableAccountResponse)
def get_receivable(
    account_id: UUID,
    _: Annotated[User, Depends(require_permission("receivables.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> ReceivableAccountResponse:
    account = ReceivableService(db).get_account(account_id)
    return ReceivableAccountResponse.model_validate(account)


@router.get("/{account_id}/payments", response_model=PaginatedReceivablePayments)
def list_payments(
    account_id: UUID,
    _: Annotated[User, Depends(require_permission("receivables.read"))],
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedReceivablePayments:
    items, total = ReceivableService(db).list_payments_of_account(
        account_id, skip=skip, limit=limit
    )
    return PaginatedReceivablePayments(
        items=[ReceivablePaymentResponse.model_validate(p) for p in items],
        total=total,
    )


@router.post("/{account_id}/payments", response_model=ReceivablePaymentResponse)
def register_payment(
    account_id: UUID,
    payload: ReceivablePaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("receivables.payment"))],
    response: Response,
) -> ReceivablePaymentResponse:
    """Registra un pago atómico; replay con misma idempotency_key devuelve el pago original."""
    payment, created = ReceivableService(db).register_payment(
        account_id,
        **payload.model_dump(),
        created_by=current_user.id,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED
    return ReceivablePaymentResponse.model_validate(payment)


@router.post("/{account_id}/cancel", response_model=ReceivableAccountResponse)
def cancel_receivable(
    account_id: UUID,
    _: Annotated[User, Depends(require_permission("receivables.cancel"))],
    db: Annotated[Session, Depends(get_db)],
) -> ReceivableAccountResponse:
    account = ReceivableService(db).cancel_receivable(account_id)
    return ReceivableAccountResponse.model_validate(account)
