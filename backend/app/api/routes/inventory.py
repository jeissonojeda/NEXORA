from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.inventory import VALID_MOVEMENT_TYPES, MovementTypes
from app.models.product import Product
from app.models.user import User
from app.schemas.inventory import (
    AdjustmentCreate,
    MovementResponse,
    PaginatedMovements,
    StockOperationCreate,
)
from app.schemas.product import ProductResponse
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService

router = APIRouter(prefix="/inventory", tags=["Inventario"])

VALID_TYPES = sorted(VALID_MOVEMENT_TYPES)


@router.get("/movements", response_model=PaginatedMovements)
def list_movements(
    _: Annotated[User, Depends(require_permission("inventory.read"))],
    db: Annotated[Session, Depends(get_db)],
    product_id: UUID | None = None,
    movement_type: Annotated[str | None, Query()] = None,
    created_by: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedMovements:
    if movement_type is not None and movement_type not in VALID_MOVEMENT_TYPES:
        raise AppError(
            status_code=422,
            error_code="INVALID_MOVEMENT_TYPE",
            message=f"Tipo inválido. Use uno de: {', '.join(VALID_TYPES)}",
        )
    items, total = InventoryService(db).list_movements(
        product_id=product_id,
        movement_type=movement_type,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedMovements(
        items=[MovementResponse.model_validate(m) for m in items],
        total=total,
    )


@router.get("/movements/{movement_id}", response_model=MovementResponse)
def get_movement(
    movement_id: UUID,
    _: Annotated[User, Depends(require_permission("inventory.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = InventoryService(db).get_movement(movement_id)
    return MovementResponse.model_validate(movement)


@router.get("/low-stock", response_model=list[ProductResponse])
def low_stock_products(
    _: Annotated[User, Depends(require_permission("inventory.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProductResponse]:
    products = ProductService(db).low_stock_products()
    return [ProductResponse.model_validate(p) for p in products]


@router.post(
    "/entries", response_model=MovementResponse, status_code=status.HTTP_201_CREATED
)
def create_entry(
    payload: StockOperationCreate,
    current_user: Annotated[
        User, Depends(require_permission("inventory.create"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = InventoryService(db).add_stock(
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_id=payload.reference_id,
        created_by=current_user.id,
    )
    return MovementResponse.model_validate(movement)


@router.post(
    "/exits", response_model=MovementResponse, status_code=status.HTTP_201_CREATED
)
def create_exit(
    payload: StockOperationCreate,
    current_user: Annotated[
        User, Depends(require_permission("inventory.create"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = InventoryService(db).remove_stock(
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_id=payload.reference_id,
        created_by=current_user.id,
    )
    return MovementResponse.model_validate(movement)


@router.post(
    "/adjustments",
    response_model=MovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_adjustment(
    payload: AdjustmentCreate,
    current_user: Annotated[
        User, Depends(require_permission("inventory.update"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = InventoryService(db).adjust_stock(
        product_id=payload.product_id,
        new_stock=payload.new_stock,
        reason=payload.reason,
        created_by=current_user.id,
    )
    return MovementResponse.model_validate(movement)


@router.post(
    "/returns", response_model=MovementResponse, status_code=status.HTTP_201_CREATED
)
def create_return(
    payload: StockOperationCreate,
    current_user: Annotated[
        User, Depends(require_permission("inventory.create"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = InventoryService(db).return_stock(
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_id=payload.reference_id,
        created_by=current_user.id,
    )
    return MovementResponse.model_validate(movement)
