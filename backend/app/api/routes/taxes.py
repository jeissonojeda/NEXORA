from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.tax import TaxCreate, TaxResponse, TaxUpdate
from app.services.tax_service import TaxService

router = APIRouter(prefix="/taxes", tags=["Impuestos"])


@router.get("", response_model=list[TaxResponse])
def list_taxes(
    _: Annotated[User, Depends(require_permission("settings.read"))],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: Annotated[bool, Query()] = False,
):
    return TaxService(db).list_taxes(include_inactive=include_inactive)


@router.post("", response_model=TaxResponse, status_code=201)
def create_tax(
    payload: TaxCreate,
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
):
    return TaxService(db).create_tax(
        name=payload.name,
        rate=payload.rate,
        description=payload.description,
        is_active=payload.is_active,
        is_default=payload.is_default,
    )


@router.put("/{tax_id}", response_model=TaxResponse)
def update_tax(
    tax_id: UUID,
    payload: TaxUpdate,
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
):
    return TaxService(db).update_tax(tax_id, **payload.model_dump(exclude_unset=True))


@router.delete("/{tax_id}", response_model=TaxResponse)
def deactivate_tax(
    tax_id: UUID,
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
):
    return TaxService(db).deactivate_tax(tax_id)
