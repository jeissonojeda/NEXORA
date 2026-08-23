from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import PaginatedProducts, ProductResponse
from app.schemas.supplier import (
    SUPPLIER_SORT_FIELDS,
    PaginatedSuppliers,
    SupplierCreate,
    SupplierDetailResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Proveedores"])


@router.get("", response_model=PaginatedSuppliers)
def list_suppliers(
    _: Annotated[User, Depends(require_permission("suppliers.read"))],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    order_by: Annotated[str, Query(pattern="^(name|created_at|updated_at)$")] = "name",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedSuppliers:
    assert order_by in SUPPLIER_SORT_FIELDS  # ordenamiento seguro (whitelist)
    rows, total = SupplierService(db).list_suppliers(
        q=q,
        is_active=is_active,
        order_by=order_by,
        order=order,
        skip=skip,
        limit=limit,
    )
    return PaginatedSuppliers(
        items=[
            SupplierDetailResponse(
                **SupplierResponse.model_validate(supplier).model_dump(),
                products_count=products_count,
            )
            for supplier, products_count in rows
        ],
        total=total,
    )


@router.get("/{supplier_id}", response_model=SupplierDetailResponse)
def get_supplier(
    supplier_id: UUID,
    _: Annotated[User, Depends(require_permission("suppliers.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> SupplierDetailResponse:
    detail = SupplierService(db).get_supplier_detail(supplier_id)
    data = SupplierResponse.model_validate(detail["supplier"]).model_dump()
    return SupplierDetailResponse(**data, products_count=detail["products_count"])


@router.get("/{supplier_id}/products", response_model=PaginatedProducts)
def list_supplier_products(
    supplier_id: UUID,
    _: Annotated[User, Depends(require_permission("suppliers.read"))],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedProducts:
    items, total = SupplierService(db).products_of_supplier(
        supplier_id,
        q=q,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return PaginatedProducts(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
    )


@router.post(
    "", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED
)
def create_supplier(
    payload: SupplierCreate,
    _: Annotated[User, Depends(require_permission("suppliers.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    supplier = SupplierService(db).create_supplier(**payload.model_dump())
    return SupplierResponse.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    _: Annotated[User, Depends(require_permission("suppliers.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    fields = payload.model_dump(exclude_unset=True)
    supplier = SupplierService(db).update_supplier(supplier_id, **fields)
    return SupplierResponse.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_supplier(
    supplier_id: UUID,
    _: Annotated[User, Depends(require_permission("suppliers.delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    SupplierService(db).deactivate_supplier(supplier_id)
