from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.cash import (
    CashSummaryResponse,
    ManualMovementCreate,
    MovementResponse,
    PaginatedMovements,
    PaginatedRegisters,
    RegisterCloseRequest,
    RegisterDetailResponse,
    RegisterOpenRequest,
    RegisterResponse,
)
from app.services.cash_service import CashService

router = APIRouter(prefix="/cash", tags=["Caja"])


@router.post(
    "/registers/open",
    response_model=RegisterDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def open_register(
    payload: RegisterOpenRequest,
    current_user: Annotated[User, Depends(require_permission("cash.open"))],
    db: Annotated[Session, Depends(get_db)],
) -> RegisterDetailResponse:
    service = CashService(db)
    register = service.open_register(
        user_id=current_user.id,
        opening_amount=payload.opening_amount,
        notes=payload.notes,
    )
    return _detail_response(service, register)


@router.get(
    "/registers/current",
    response_model=RegisterDetailResponse | None,
)
def get_current_register(
    current_user: Annotated[User, Depends(require_permission("cash.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> RegisterDetailResponse | None:
    service = CashService(db)
    register = service.get_current(current_user.id)
    if register is None:
        return None
    return _detail_response(service, register)


@router.get("/registers", response_model=PaginatedRegisters)
def list_registers(
    _: Annotated[User, Depends(require_permission("cash.read"))],
    db: Annotated[Session, Depends(get_db)],
    user_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedRegisters:
    items, total = CashService(db).list_registers(
        user_id=user_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedRegisters(
        items=[RegisterResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/registers/{register_id}", response_model=RegisterDetailResponse)
def get_register(
    register_id: UUID,
    _: Annotated[User, Depends(require_permission("cash.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> RegisterDetailResponse:
    service = CashService(db)
    register = service.get_register(register_id)
    return _detail_response(service, register)


@router.post(
    "/registers/{register_id}/close",
    response_model=RegisterDetailResponse,
)
def close_register(
    register_id: UUID,
    payload: RegisterCloseRequest,
    current_user: Annotated[User, Depends(require_permission("cash.close"))],
    db: Annotated[Session, Depends(get_db)],
) -> RegisterDetailResponse:
    service = CashService(db)
    register = service.close_register(
        register_id,
        counted_amount=payload.counted_amount,
        closed_by=current_user.id,
    )
    return _detail_response(service, register)


@router.get(
    "/registers/{register_id}/movements",
    response_model=PaginatedMovements,
)
def list_movements(
    register_id: UUID,
    _: Annotated[User, Depends(require_permission("cash.read"))],
    db: Annotated[Session, Depends(get_db)],
    movement_type: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedMovements:
    items, total = CashService(db).list_movements(
        register_id,
        movement_type=movement_type,
        skip=skip,
        limit=limit,
    )
    return PaginatedMovements(
        items=[MovementResponse.model_validate(m) for m in items],
        total=total,
    )


@router.get(
    "/registers/{register_id}/summary",
    response_model=CashSummaryResponse,
)
def get_summary(
    register_id: UUID,
    _: Annotated[User, Depends(require_permission("cash.report"))],
    db: Annotated[Session, Depends(get_db)],
) -> CashSummaryResponse:
    service = CashService(db)
    register = service.get_register(register_id)
    return CashSummaryResponse(**service.summary(register))


@router.post("/movements", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
def create_manual_movement(
    payload: ManualMovementCreate,
    current_user: Annotated[
        User, Depends(require_permission("cash.movements"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> MovementResponse:
    movement = CashService(db).add_manual_movement(
        user_id=current_user.id,
        movement_type=payload.movement_type,
        amount=payload.amount,
        description=payload.description,
    )
    return MovementResponse.model_validate(movement)


def _detail_response(
    service: CashService, register
) -> RegisterDetailResponse:
    data = RegisterResponse.model_validate(register).model_dump()
    data["summary"] = CashSummaryResponse(**service.summary(register)).model_dump()
    return RegisterDetailResponse.model_validate(data)
