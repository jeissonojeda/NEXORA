from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.sale_return import (
    PaginatedSaleReturns,
    SaleReturnCreate,
    SaleReturnResponse,
)
from app.services.sale_return_service import SaleReturnService

router = APIRouter(prefix="/sales", tags=["Devoluciones de ventas"])


@router.post(
    "/{sale_id}/returns",
    response_model=SaleReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sale_return(
    sale_id: UUID,
    payload: SaleReturnCreate,
    current_user: Annotated[User, Depends(require_permission("sales.returns"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleReturnResponse:
    """Registra una devolución total/parcial o un cambio de una venta.

    Transaccional: devolución + reingreso de stock + reembolso (o nueva
    venta de cambio) ocurren en un único COMMIT. Idempotente por
    ``idempotency_key``.
    """
    sale_return = SaleReturnService(db).create_return(
        sale_id=sale_id,
        created_by=current_user.id,
        refund_method=payload.refund_method,
        items=[item.model_dump() for item in payload.items],
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        exchange_items=[item.model_dump() for item in payload.exchange_items],
        exchange_payment_method=payload.exchange_payment_method,
    )
    return SaleReturnResponse.model_validate(sale_return)


@router.get("/{sale_id}/returns", response_model=PaginatedSaleReturns)
def list_sale_returns(
    sale_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.read"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
) -> PaginatedSaleReturns:
    items, total = SaleReturnService(db).list_returns_for_sale(
        sale_id, skip=skip, limit=limit
    )
    return PaginatedSaleReturns(
        items=[SaleReturnResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/returns/{return_id}", response_model=SaleReturnResponse)
def get_sale_return(
    return_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleReturnResponse:
    sale_return = SaleReturnService(db).get_return(return_id)
    return SaleReturnResponse.model_validate(sale_return)


@router.delete("/returns/{return_id}", response_model=SaleReturnResponse)
def cancel_sale_return(
    return_id: UUID,
    _: Annotated[User, Depends(require_permission("sales.returns"))],
    db: Annotated[Session, Depends(get_db)],
) -> SaleReturnResponse:
    """Anula una devolución registrada (corrección administrativa)."""
    sale_return = SaleReturnService(db).cancel_return(return_id)
    return SaleReturnResponse.model_validate(sale_return)
