from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categorías"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    _: Annotated[User, Depends(require_permission("categories.read"))],
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CategoryResponse]:
    rows = CategoryService(db).list_categories(skip=skip, limit=limit)
    return [
        CategoryResponse(
            **CategoryResponse.model_validate(category).model_dump(
                exclude={"products_count"}
            ),
            products_count=products_count,
        )
        for category, products_count in rows
    ]


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    _: Annotated[User, Depends(require_permission("categories.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    return CategoryResponse.model_validate(CategoryService(db).get_category(category_id))


@router.post(
    "", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: CategoryCreate,
    _: Annotated[User, Depends(require_permission("categories.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    category = CategoryService(db).create_category(
        name=payload.name, description=payload.description, tax_id=payload.tax_id
    )
    return CategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _: Annotated[User, Depends(require_permission("categories.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    fields = payload.model_dump(exclude_unset=True)
    category = CategoryService(db).update_category(category_id, **fields)
    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT
)
def deactivate_category(
    category_id: UUID,
    _: Annotated[User, Depends(require_permission("categories.delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    CategoryService(db).deactivate_category(category_id)
