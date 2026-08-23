from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.purchase import VALID_PURCHASE_STATUSES
from app.models.user import User
from app.schemas.purchase import (
    PaginatedPurchases,
    PurchaseCreate,
    PurchaseDetailResponse,
    PurchaseItemResponse,
    PurchaseItemUpdate,
    PurchaseItemCreate,
    PurchaseResponse,
    PurchaseUpdate,
)
from app.services.purchase_service import PurchaseService

router = APIRouter(prefix="/purchases", tags=["Compras"])


@router.get("", response_model=PaginatedPurchases)
def list_purchases(
    _: Annotated[User, Depends(require_permission("purchases.read"))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: Annotated[str | None, Query(max_length=30)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedPurchases:
    if status_filter is not None and status_filter not in VALID_PURCHASE_STATUSES:
        raise AppError(
            status_code=422,
            error_code="INVALID_PURCHASE_STATUS",
            message=f"Estado inválido. Use uno de: {', '.join(sorted(VALID_PURCHASE_STATUSES))}",
        )
    items, total = PurchaseService(db).list_purchases(
        supplier_id=supplier_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        q=q,
        skip=skip,
        limit=limit,
    )
    return PaginatedPurchases(
        items=[PurchaseResponse.model_validate(p) for p in items],
        total=total,
    )


@router.get("/{purchase_id}", response_model=PurchaseDetailResponse)
def get_purchase(
    purchase_id: UUID,
    _: Annotated[User, Depends(require_permission("purchases.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseDetailResponse:
    purchase = PurchaseService(db).get_purchase_detail(purchase_id)
    return PurchaseDetailResponse.model_validate(purchase)


@router.post(
    "", response_model=PurchaseDetailResponse, status_code=status.HTTP_201_CREATED
)
def create_purchase(
    payload: PurchaseCreate,
    current_user: Annotated[User, Depends(require_permission("purchases.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseDetailResponse:
    purchase = PurchaseService(db).create_purchase(
        supplier_id=payload.supplier_id,
        created_by=current_user.id,
        notes=payload.notes,
        discount=payload.discount,
        tax=payload.tax,
        items=[item.model_dump() for item in payload.items],
    )
    return PurchaseDetailResponse.model_validate(purchase)


@router.patch("/{purchase_id}", response_model=PurchaseDetailResponse)
def update_purchase(
    purchase_id: UUID,
    payload: PurchaseUpdate,
    _: Annotated[User, Depends(require_permission("purchases.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseDetailResponse:
    fields = payload.model_dump(exclude_unset=True)
    purchase = PurchaseService(db).update_purchase(purchase_id, **fields)
    return PurchaseDetailResponse.model_validate(purchase)


@router.delete("/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_purchase(
    purchase_id: UUID,
    _: Annotated[User, Depends(require_permission("purchases.cancel"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    PurchaseService(db).cancel_purchase(purchase_id)


@router.post("/{purchase_id}/confirm", response_model=PurchaseDetailResponse)
def confirm_purchase(
    purchase_id: UUID,
    current_user: Annotated[User, Depends(require_permission("purchases.confirm"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseDetailResponse:
    purchase = PurchaseService(db).confirm_purchase(
        purchase_id, confirmed_by=current_user.id
    )
    return PurchaseDetailResponse.model_validate(purchase)


@router.post(
    "/{purchase_id}/items",
    response_model=PurchaseItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_purchase_item(
    purchase_id: UUID,
    payload: PurchaseItemCreate,
    _: Annotated[User, Depends(require_permission("purchases.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseItemResponse:
    item = PurchaseService(db).add_item(
        purchase_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        discount=payload.discount,
        tax=payload.tax,
    )
    return PurchaseItemResponse.model_validate(item)


@router.patch("/{purchase_id}/items/{item_id}", response_model=PurchaseItemResponse)
def update_purchase_item(
    purchase_id: UUID,
    item_id: UUID,
    payload: PurchaseItemUpdate,
    _: Annotated[User, Depends(require_permission("purchases.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseItemResponse:
    fields = payload.model_dump(exclude_unset=True)
    item = PurchaseService(db).update_item(purchase_id, item_id, **fields)
    return PurchaseItemResponse.model_validate(item)


@router.delete(
    "/{purchase_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_purchase_item(
    purchase_id: UUID,
    item_id: UUID,
    _: Annotated[User, Depends(require_permission("purchases.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    PurchaseService(db).remove_item(purchase_id, item_id)
