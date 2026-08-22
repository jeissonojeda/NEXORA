from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, db: Session, model: type[ModelT]) -> None:
        self.db = db
        self.model = model

    def get_by_id(self, entity_id: UUID) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def list_paginated(
        self, skip: int = 0, limit: int = 100
    ) -> list[ModelT]:
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
