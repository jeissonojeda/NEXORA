from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(tags=["Usuarios"])


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _: Annotated[User, Depends(require_permission("users.read"))],
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[UserResponse]:
    users = UserService(db).list_users(skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    _: Annotated[User, Depends(require_permission("users.create"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    user = UserService(db).create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role_name=payload.role_name,
    )
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    _: Annotated[User, Depends(require_permission("users.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    return UserResponse.model_validate(UserService(db).get_user(user_id))


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: Annotated[User, Depends(require_permission("users.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise AppError(
            status_code=422,
            error_code="EMPTY_UPDATE",
            message="Debe enviar al menos un campo a actualizar",
        )
    if user_id == current_user.id and fields.get("is_active") is False:
        raise AppError(
            status_code=409,
            error_code="CANNOT_DEACTIVATE_SELF",
            message="No puedes desactivar tu propia cuenta",
        )
    user = UserService(db).update_user(user_id, **fields)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: UUID,
    acting_user: Annotated[User, Depends(require_permission("users.delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    UserService(db).deactivate_user(user_id, acting_user_id=acting_user.id)
