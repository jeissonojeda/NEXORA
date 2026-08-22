import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password_strength(value: str) -> str:
    errors: list[str] = []
    if not re.search(r"[A-Z]", value):
        errors.append("una mayúscula")
    if not re.search(r"[a-z]", value):
        errors.append("una minúscula")
    if not re.search(r"\d", value):
        errors.append("un número")
    if errors:
        raise ValueError("La contraseña debe contener al menos " + ", ".join(errors))
    return value


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    display_name: str


class UserBase(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
        examples=["jperez"],
    )
    email: EmailStr = Field(examples=["jperez@example.com"])
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role_name: str | None = Field(
        default=None,
        description="Nombre interno del rol (ADMIN, CASHIER, INVENTORY_MANAGER)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return _check_password_strength(value)


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    role_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _check_password_strength(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None
    roles: list[RoleOut]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
