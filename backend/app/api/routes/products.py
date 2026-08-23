from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import (
    PaginatedProducts,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("", response_model=PaginatedProducts)
def list_products(
    _: Annotated[User, Depends(require_permission("products.read"))],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    category_id: UUID | None = None,
    supplier_id: UUID | None = None,
    is_active: bool | None = None,
    low_stock: bool = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedProducts:
    items, total = ProductService(db).search_products(
        q=q,
        category_id=category_id,
        supplier_id=supplier_id,
        is_active=is_active,
        low_stock=low_stock,
        skip=skip,
        limit=limit,
    )
    return PaginatedProducts(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
    )


@router.get("/barcode/{barcode}", response_model=ProductResponse)
def get_product_by_barcode(
    barcode: str,
    _: Annotated[User, Depends(require_permission("products.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductResponse:
    product = ProductService(db).get_active_product_by_barcode(barcode)
    return ProductResponse.model_validate(product)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    _: Annotated[User, Depends(require_permission("products.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductResponse:
    return ProductResponse.model_validate(ProductService(db).get_product(product_id))


@router.post(
    "", response_model=ProductResponse, status_code=status.HTTP_201_CREATED
)
def create_product(
    payload: ProductCreate,
    _: Annotated[User, Depends(require_permission("products.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductResponse:
    product = ProductService(db).create_product(
        name=payload.name,
        barcode=payload.barcode,
        description=payload.description,
        purchase_price=payload.purchase_price,
        sale_price=payload.sale_price,
        category_id=payload.category_id,
        supplier_id=payload.supplier_id,
        stock=payload.stock,
        minimum_stock=payload.minimum_stock,
    )
    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    _: Annotated[User, Depends(require_permission("products.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductResponse:
    fields = payload.model_dump(exclude_unset=True)
    product = ProductService(db).update_product(product_id, **fields)
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(
    product_id: UUID,
    _: Annotated[User, Depends(require_permission("products.delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    ProductService(db).deactivate_product(product_id)
