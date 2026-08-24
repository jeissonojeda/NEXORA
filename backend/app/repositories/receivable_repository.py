from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.customer import ReceivableAccount, ReceivablePayment
from app.repositories.base import BaseRepository


class ReceivableRepository(BaseRepository[ReceivableAccount]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, ReceivableAccount)

    def get_for_update(self, account_id: UUID) -> ReceivableAccount | None:
        """Bloquea la cuenta (SELECT ... FOR UPDATE) con sus pagos precargados."""
        stmt = (
            select(ReceivableAccount)
            .where(ReceivableAccount.id == account_id)
            .options(selectinload(ReceivableAccount.payments))
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_with_relations(self, account_id: UUID) -> ReceivableAccount | None:
        stmt = (
            select(ReceivableAccount)
            .where(ReceivableAccount.id == account_id)
            .options(
                selectinload(ReceivableAccount.payments).joinedload(
                    ReceivablePayment.user
                ),
                joinedload(ReceivableAccount.customer),
            )
        )
        return self.db.scalars(stmt).first()

    def search(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        due_from: Any | None = None,
        due_to: Any | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReceivableAccount], int]:
        # joinedload evita N+1 al serializar el cliente en el listado.
        stmt = select(ReceivableAccount).options(
            joinedload(ReceivableAccount.customer)
        )
        count_stmt = select(func.count()).select_from(ReceivableAccount)

        conditions: list[Any] = []
        if customer_id is not None:
            conditions.append(ReceivableAccount.customer_id == customer_id)
        if status is not None:
            conditions.append(ReceivableAccount.status == status)
        if date_from is not None:
            conditions.append(ReceivableAccount.created_at >= date_from)
        if date_to is not None:
            conditions.append(ReceivableAccount.created_at <= date_to)
        if due_from is not None:
            conditions.append(ReceivableAccount.due_date >= due_from)
        if due_to is not None:
            conditions.append(ReceivableAccount.due_date <= due_to)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(
                ReceivableAccount.created_at.desc(), ReceivableAccount.id
            )
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total

    def count_by_status(
        self, customer_id: UUID
    ) -> dict[str, tuple[int, Any]]:
        """Conteo y saldo por estado en una sola consulta (sin N+1)."""
        stmt = (
            select(
                ReceivableAccount.status,
                func.count(),
                func.coalesce(func.sum(ReceivableAccount.balance), 0),
            )
            .where(ReceivableAccount.customer_id == customer_id)
            .group_by(ReceivableAccount.status)
        )
        return {
            row[0]: (int(row[1]), row[2]) for row in self.db.execute(stmt).all()
        }


class ReceivablePaymentRepository(BaseRepository[ReceivablePayment]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, ReceivablePayment)

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> ReceivablePayment | None:
        stmt = select(ReceivablePayment).where(
            ReceivablePayment.idempotency_key == idempotency_key
        )
        return self.db.scalars(stmt).first()

    def search_for_account(
        self,
        account_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReceivablePayment], int]:
        base = select(ReceivablePayment).where(
            ReceivablePayment.receivable_account_id == account_id
        )
        count_stmt = (
            select(func.count())
            .select_from(ReceivablePayment)
            .where(ReceivablePayment.receivable_account_id == account_id)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = base.order_by(ReceivablePayment.created_at.desc()).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def search(
        self,
        customer_id: UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReceivablePayment], int]:
        stmt = select(ReceivablePayment).join(
            ReceivableAccount,
            ReceivablePayment.receivable_account_id == ReceivableAccount.id,
        )
        count_stmt = (
            select(func.count())
            .select_from(ReceivablePayment)
            .join(
                ReceivableAccount,
                ReceivablePayment.receivable_account_id == ReceivableAccount.id,
            )
        )
        if customer_id is not None:
            stmt = stmt.where(ReceivableAccount.customer_id == customer_id)
            count_stmt = count_stmt.where(
                ReceivableAccount.customer_id == customer_id
            )
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.options(joinedload(ReceivablePayment.user))
            .order_by(ReceivablePayment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total
