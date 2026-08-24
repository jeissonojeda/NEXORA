from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.customer import (
    CUSTOMER_SORT_FIELDS,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    PaginatedCustomers,
)
from app.schemas.receivable import (
    CustomerStatementResponse,
    DEFAULT_ACCOUNTS_LIMIT,
    DEFAULT_PAYMENTS_LIMIT,
)
from app.services.customer_service import CustomerService
from app.services.receivable_service import ReceivableService

router = APIRouter(prefix="/customers", tags=["Clientes"])


@router.get("", response_model=PaginatedCustomers)
def list_customers(
    _: Annotated[User, Depends(require_permission("customers.read"))],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    credit_enabled: bool | None = None,
    order_by: Annotated[
        str, Query(pattern="^(name|created_at|current_balance|credit_limit)$")
    ] = "name",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedCustomers:
    assert order_by in CUSTOMER_SORT_FIELDS  # ordenamiento seguro (whitelist)
    items, total = CustomerService(db).list_customers(
        q=q,
        is_active=is_active,
        credit_enabled=credit_enabled,
        order_by=order_by,
        order=order,
        skip=skip,
        limit=limit,
    )
    return PaginatedCustomers(
        items=[CustomerResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: UUID,
    _: Annotated[User, Depends(require_permission("customers.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    customer = CustomerService(db).get_customer(customer_id)
    return CustomerResponse.model_validate(customer)


@router.post(
    "", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED
)
def create_customer(
    payload: CustomerCreate,
    _: Annotated[User, Depends(require_permission("customers.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    customer = CustomerService(db).create_customer(**payload.model_dump())
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    _: Annotated[User, Depends(require_permission("customers.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    fields = payload.model_dump(exclude_unset=True)
    customer = CustomerService(db).update_customer(customer_id, **fields)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_customer(
    customer_id: UUID,
    _: Annotated[User, Depends(require_permission("customers.delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Desactivación lógica; nunca elimina historial financiero."""
    CustomerService(db).deactivate_customer(customer_id)


@router.get("/{customer_id}/statement", response_model=CustomerStatementResponse)
def get_statement(
    customer_id: UUID,
    _: Annotated[User, Depends(require_permission("receivables.read"))],
    db: Annotated[Session, Depends(get_db)],
    accounts_skip: Annotated[int, Query(ge=0)] = 0,
    accounts_limit: Annotated[int, Query(ge=1, le=200)] = DEFAULT_ACCOUNTS_LIMIT,
    payments_skip: Annotated[int, Query(ge=0)] = 0,
    payments_limit: Annotated[int, Query(ge=1, le=200)] = DEFAULT_PAYMENTS_LIMIT,
) -> CustomerStatementResponse:
    """Estado de cuenta del cliente (cuentas + pagos paginados)."""
    statement = ReceivableService(db).statement(
        customer_id,
        accounts_skip=accounts_skip,
        accounts_limit=accounts_limit,
        payments_skip=payments_skip,
        payments_limit=payments_limit,
    )
    return CustomerStatementResponse.model_validate(statement)
