from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StockOperationCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)
    reference_id: str | None = Field(default=None, max_length=100)


class AdjustmentCreate(BaseModel):
    product_id: UUID
    new_stock: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=255)


class MovementFilters(BaseModel):
    pass


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    movement_type: str
    quantity: int
    previous_stock: int
    new_stock: int
    reason: str | None
    reference_id: str | None
    created_by: UUID
    created_by_username: str | None
    created_at: datetime


class PaginatedMovements(BaseModel):
    items: list[MovementResponse]
    total: int
