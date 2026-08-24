from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.cash import (
    CashMovement,
    CashRegister,
    RegisterStatuses,
    cash_delta,
)
from app.models.sale import Sale, SaleStatuses
from app.repositories.base import BaseRepository


class CashRegisterRepository(BaseRepository[CashRegister]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, CashRegister)

    def get_for_update(self, register_id: UUID) -> CashRegister | None:
        """Bloquea la fila de la caja (SELECT ... FOR UPDATE).

        En PostgreSQL garantiza exclusividad durante el cierre; en SQLite
        el hint se ignora (su lock global de escritura serializa).
        """
        stmt = (
            select(CashRegister)
            .where(CashRegister.id == register_id)
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    def get_open_for_user(self, user_id: UUID) -> CashRegister | None:
        stmt = (
            select(CashRegister)
            .where(
                CashRegister.user_id == user_id,
                CashRegister.status == RegisterStatuses.OPEN,
            )
            .options(joinedload(CashRegister.user))
        )
        return self.db.scalars(stmt).first()

    def get_with_relations(self, register_id: UUID) -> CashRegister | None:
        stmt = (
            select(CashRegister)
            .where(CashRegister.id == register_id)
            .options(
                joinedload(CashRegister.user),
                joinedload(CashRegister.closed_by),
            )
        )
        return self.db.scalars(stmt).first()

    def search(
        self,
        user_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CashRegister], int]:
        stmt = select(CashRegister).options(
            joinedload(CashRegister.user), joinedload(CashRegister.closed_by)
        )
        count_stmt = select(func.count()).select_from(CashRegister)

        conditions: list[Any] = []
        if user_id is not None:
            conditions.append(CashRegister.user_id == user_id)
        if status is not None:
            conditions.append(CashRegister.status == status)
        if date_from is not None:
            conditions.append(CashRegister.opened_at >= date_from)
        if date_to is not None:
            conditions.append(CashRegister.opened_at <= date_to)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(CashRegister.opened_at.desc(), CashRegister.id)
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total


class CashMovementRepository(BaseRepository[CashMovement]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, CashMovement)

    def get_by_reference(
        self, reference_type: str, reference_id: str
    ) -> CashMovement | None:
        stmt = select(CashMovement).where(
            CashMovement.reference_type == reference_type,
            CashMovement.reference_id == reference_id,
        )
        return self.db.scalars(stmt).first()

    def search_for_register(
        self,
        register_id: UUID,
        movement_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CashMovement], int]:
        base_conditions = [CashMovement.register_id == register_id]
        if movement_type is not None:
            base_conditions.append(CashMovement.movement_type == movement_type)

        count_stmt = (
            select(func.count())
            .select_from(CashMovement)
            .where(*base_conditions)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            select(CashMovement)
            .where(*base_conditions)
            .options(joinedload(CashMovement.user))
            .order_by(CashMovement.created_at.desc(), CashMovement.id)
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).unique().all())
        return items, total

    def totals_for_register(self, register: CashRegister) -> dict[str, Decimal]:
        """Agregados del turno en dos consultas (sin N+1).

        Los montos de medios electrónicos se listan aparte porque NO
        afectan el efectivo esperado; el efecto sobre la caja se calcula
        con ``cash_delta`` (única fuente de verdad).

        Las ventas a crédito NO generan movimiento de caja, por lo que
        se cuentan aparte desde la tabla ``sales`` dentro de la ventana
        del turno del cajero responsable.
        """
        grouped = self.db.execute(
            select(
                CashMovement.movement_type,
                CashMovement.payment_method,
                func.coalesce(func.sum(CashMovement.amount), 0),
                func.count(),
            )
            .where(CashMovement.register_id == register.id)
            .group_by(CashMovement.movement_type, CashMovement.payment_method)
        ).all()

        totals = {
            "opening_total": Decimal("0"),
            "cash_in_total": Decimal("0"),
            "cash_out_total": Decimal("0"),
            "cash_sales_total": Decimal("0"),
            "card_sales_total": Decimal("0"),
            "transfer_sales_total": Decimal("0"),
            "credit_sales_count": 0,
            "cash_receivable_payments_total": Decimal("0"),
            "card_receivable_payments_total": Decimal("0"),
            "transfer_receivable_payments_total": Decimal("0"),
            "movement_count": 0,
            "expected_cash": Decimal("0"),
        }

        for movement_type, payment_method, amount_sum, count in grouped:
            amount_sum = Decimal(str(amount_sum or 0))
            count = int(count)
            totals["movement_count"] += count
            key = f"{movement_type}|{payment_method}"
            if movement_type == "OPENING":
                totals["opening_total"] += amount_sum
            elif movement_type == "CASH_IN":
                totals["cash_in_total"] += amount_sum
            elif movement_type == "CASH_OUT":
                totals["cash_out_total"] += amount_sum
            elif movement_type == "SALE":
                if payment_method == "CASH":
                    totals["cash_sales_total"] += amount_sum
                elif payment_method == "CARD":
                    totals["card_sales_total"] += amount_sum
                elif payment_method == "TRANSFER":
                    totals["transfer_sales_total"] += amount_sum
            elif movement_type == "RECEIVABLE_PAYMENT":
                if payment_method == "CASH":
                    totals["cash_receivable_payments_total"] += amount_sum
                elif payment_method == "CARD":
                    totals["card_receivable_payments_total"] += amount_sum
                elif payment_method == "TRANSFER":
                    totals["transfer_receivable_payments_total"] += amount_sum

            effect = cash_delta(movement_type, payment_method)
            if effect != 0:
                totals["expected_cash"] += effect * amount_sum

        credit_stmt = (
            select(func.count())
            .select_from(Sale)
            .where(
                Sale.created_by == register.user_id,
                Sale.payment_method == "CREDIT",
                Sale.status == SaleStatuses.CONFIRMED,
                Sale.confirmed_at >= register.opened_at,
            )
        )
        if register.closed_at is not None:
            credit_stmt = credit_stmt.where(Sale.confirmed_at <= register.closed_at)
        totals["credit_sales_count"] = int(self.db.scalar(credit_stmt) or 0)

        return {k: money_like(v) for k, v in totals.items()}


def money_like(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value)).quantize(Decimal("0.01"))
