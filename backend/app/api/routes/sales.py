from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.sale import VALID_SALE_STATUSES
from app.models.user import User
from app.schemas.sale import (
    PaginatedSales,
    SaleCreate,
    SaleDetailResponse,
    SaleItemCreate,
    SaleItemResponse,
    SaleItemUpdate,
    SaleResponse,
    SaleUpdate,
)
from app.services.sale_service import SaleService

router = APIRouter(prefix="/sales", tags=["Ventas"])


@router.get("", response_model=PaginatedSales)
def list_sales(
    _: Annotated[User, Depends(require_permission("sales.read"))],
    db: Annotated[Session, Depends(get_db)],
    customer_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: Annotated[str | None, Query(max_length=30)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedSales:
    if status_filter is not None and status_filter not in VALID_SALE_STATUSES:
        raise AppError(
            status_code=422,
            error_code="INVALID_SALE_STATUS",
            message=f"Estado inválido. Use uno de: {', '.join(sorted(VALID_SALE_STATUSES))}",
        )
    items, total = SaleService(db).list_sales(
        customer_id=customer_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        q=q,
        skip=skip,
        limit=limit,
    )
    return PaginatedSales(
        items=[SaleResponse.model_validate(s) for s in items],
        total=total,
    )


@router.get("/{sale_id}", response_model=SaleDetailResponse)
def get_sale(
    sale_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleDetailResponse:
    sale = SaleService(db).get_sale_detail(sale_id)
    return SaleDetailResponse.model_validate(sale)


@router.post(
    "", response_model=SaleDetailResponse, status_code=status.HTTP_201_CREATED
)
def create_sale(
    payload: SaleCreate,
    current_user: Annotated[User, Depends(require_permission("sales.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleDetailResponse:
    sale = SaleService(db).create_sale(
        created_by=current_user.id,
        customer_id=payload.customer_id,
        payment_method=payload.payment_method,
        amount_paid=payload.amount_paid,
        notes=payload.notes,
        discount=payload.discount,
        tax=payload.tax,
        items=[item.model_dump() for item in payload.items],
    )
    return SaleDetailResponse.model_validate(sale)


@router.patch("/{sale_id}", response_model=SaleDetailResponse)
def update_sale(
    sale_id: UUID,
    payload: SaleUpdate,
    _: Annotated[User, Depends(require_permission("sales.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleDetailResponse:
    fields = payload.model_dump(exclude_unset=True)
    sale = SaleService(db).update_sale(sale_id, **fields)
    return SaleDetailResponse.model_validate(sale)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_sale(
    sale_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.cancel"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    SaleService(db).cancel_sale(sale_id)


@router.post("/{sale_id}/confirm", response_model=SaleDetailResponse)
def confirm_sale(
    sale_id: UUID,
    current_user: Annotated[User, Depends(require_permission("sales.confirm"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleDetailResponse:
    sale = SaleService(db).confirm_sale(sale_id, confirmed_by=current_user.id)
    return SaleDetailResponse.model_validate(sale)


@router.post(
    "/{sale_id}/items",
    response_model=SaleItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_sale_item(
    sale_id: UUID,
    payload: SaleItemCreate,
    _: Annotated[User, Depends(require_permission("sales.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleItemResponse:
    item = SaleService(db).add_item(
        sale_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        discount=payload.discount,
        tax=payload.tax,
    )
    return SaleItemResponse.model_validate(item)


@router.patch("/{sale_id}/items/{item_id}", response_model=SaleItemResponse)
def update_sale_item(
    sale_id: UUID,
    item_id: UUID,
    payload: SaleItemUpdate,
    _: Annotated[User, Depends(require_permission("sales.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleItemResponse:
    fields = payload.model_dump(exclude_unset=True)
    item = SaleService(db).update_item(sale_id, item_id, **fields)
    return SaleItemResponse.model_validate(item)


@router.delete("/{sale_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_sale_item(
    sale_id: UUID,
    item_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    SaleService(db).remove_item(sale_id, item_id)
