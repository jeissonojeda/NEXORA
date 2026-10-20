from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Decimal


class TaxCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rate: Money = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    is_default: bool = False


class TaxUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    rate: Money | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_default: bool | None = None


class TaxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    rate: Money
    description: str | None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class TaxBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    rate: Money
