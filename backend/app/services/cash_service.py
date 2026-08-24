from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.cash import (
    CashMovement,
    CashReferenceTypes,
    CashRegister,
    MovementTypes,
    RegisterStatuses,
    VALID_MOVEMENT_TYPES,
    VALID_REGISTER_STATUSES,
)
from app.models.sale import PaymentMethods as SalePaymentMethods
from app.repositories.cash_repository import (
    CashMovementRepository,
    CashRegisterRepository,
)
from app.services.customer_credit_service import money

MANUAL_MOVEMENT_TYPES = frozenset(
    {MovementTypes.CASH_IN, MovementTypes.CASH_OUT}
)


class CashService:
    """Caja y control de efectivo.

    Reglas clave:

    - Un cajero tiene a lo sumo UNA caja abierta (índice parcial único en
      BD como red de seguridad ante carreras; el servicio además
      re-verifica tras un IntegrityError).
    - La apertura crea la caja y su movimiento OPENING en la MISMA
      transacción (nunca existe caja abierta sin OPENING).
    - El cierre bloquea la fila (SELECT ... FOR UPDATE), calcula el
      efectivo esperado desde los movimientos, guarda esperado/contado/
      diferencia y cambia el estado en una sola transacción idempotente
      (una caja CLOSED nunca vuelve a cerrarse).
    - Ventas y abonos de cuentas por cobrar generan movimientos de caja
      automáticamente SOLO si el usuario que opera tiene una caja abierta;
      son idempotentes por UNIQUE(reference_type, reference_id): repetir
      una confirmación o un pago jamás duplica movimientos.
    - CARD/TRANSFER quedan registrados para trazabilidad pero NO mueven
      el efectivo esperado (solo CASH lo hace); CREDIT de venta no genera
      movimiento (la deuda vive en la cuenta por cobrar).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.registers = CashRegisterRepository(db)
        self.movements_repo = CashMovementRepository(db)

    # ------------------------------------------------------------------
    # Apertura
    # ------------------------------------------------------------------
    def open_register(
        self,
        user_id: UUID,
        opening_amount: Decimal,
        notes: str | None = None,
    ) -> CashRegister:
        amount = money(opening_amount)
        existing = self.registers.get_open_for_user(user_id)
        if existing is not None:
            raise AppError(
                status_code=409,
                error_code="REGISTER_ALREADY_OPEN",
                message="El usuario ya tiene una caja abierta",
            )
        try:
            register = CashRegister(
                user_id=user_id,
                status=RegisterStatuses.OPEN,
                opening_amount=amount,
                notes=(notes.strip() or None) if notes else None,
            )
            self.registers.add(register)
            self.movements_repo.add(
                CashMovement(
                    register_id=register.id,
                    user_id=user_id,
                    movement_type=MovementTypes.OPENING,
                    payment_method=None,
                    amount=amount,
                    description="Apertura de caja",
                    reference_type=None,
                    reference_id=None,
                )
            )
            self.db.commit()
        except IntegrityError:
            # Carrera: otro turno del mismo usuario ganó la inserción.
            self.db.rollback()
            winner = self.registers.get_open_for_user(user_id)
            if winner is not None:
                raise AppError(
                    status_code=409,
                    error_code="REGISTER_ALREADY_OPEN",
                    message="El usuario ya tiene una caja abierta",
                ) from None
            raise
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(register)
        return register

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_current(self, user_id: UUID) -> CashRegister | None:
        register = self.registers.get_open_for_user(user_id)
        if register is not None:
            _ = register.user_username  # precarga para serializar
        return register

    def get_register(self, register_id: UUID) -> CashRegister:
        register = self._get_loaded_register(register_id)
        return register

    def list_registers(
        self,
        user_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CashRegister], int]:
        if status is not None and status not in VALID_REGISTER_STATUSES:
            raise AppError(
                status_code=422,
                error_code="INVALID_REGISTER_STATUS",
                message=(
                    "Estado inválido. Use uno de: "
                    + ", ".join(sorted(VALID_REGISTER_STATUSES))
                ),
            )
        registers, total = self.registers.search(
            user_id=user_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
        for register in registers:
            _ = register.user_username  # precarga para serializar
        return registers, total

    def list_movements(
        self,
        register_id: UUID,
        movement_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CashMovement], int]:
        self._ensure_exists(register_id)
        if movement_type is not None and movement_type not in VALID_MOVEMENT_TYPES:
            raise AppError(
                status_code=422,
                error_code="INVALID_MOVEMENT_TYPE",
                message=(
                    "Tipo inválido. Use uno de: "
                    + ", ".join(sorted(VALID_MOVEMENT_TYPES))
                ),
            )
        movements, total = self.movements_repo.search_for_register(
            register_id,
            movement_type=movement_type,
            skip=skip,
            limit=limit,
        )
        for movement in movements:
            _ = movement.user_username  # precarga para serializar
        return movements, total

    def summary(self, register: CashRegister) -> dict[str, Decimal]:
        """Resumen del turno; para caja cerrada replica los montos fijados."""
        totals = self.movements_repo.totals_for_register(register)
        if register.status == RegisterStatuses.CLOSED:
            totals["expected_cash"] = money(register.expected_amount)
        return totals

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def close_register(
        self,
        register_id: UUID,
        counted_amount: Decimal,
        closed_by: UUID,
    ) -> CashRegister:
        counted = money(counted_amount)
        try:
            register = self.registers.get_for_update(register_id)
            if register is None:
                raise AppError(
                    status_code=404,
                    error_code="REGISTER_NOT_FOUND",
                    message="Caja no encontrada",
                )
            if register.status == RegisterStatuses.CLOSED:
                raise AppError(
                    status_code=409,
                    error_code="REGISTER_ALREADY_CLOSED",
                    message="La caja ya está cerrada",
                )
            if register.status == RegisterStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="REGISTER_CANCELLED",
                    message="La caja está cancelada",
                )

            totals = self.movements_repo.totals_for_register(register)
            expected = money(totals["expected_cash"])

            register.expected_amount = expected
            register.counted_amount = counted
            register.difference = money(counted - expected)
            register.closed_at = datetime.now(tz=self._tz())
            register.closed_by_id = closed_by
            register.status = RegisterStatuses.CLOSED
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(register)
        return register

    # ------------------------------------------------------------------
    # Movimientos manuales (CASH_IN / CASH_OUT)
    # ------------------------------------------------------------------
    def add_manual_movement(
        self,
        user_id: UUID,
        movement_type: str,
        amount: Decimal,
        description: str,
    ) -> CashMovement:
        if movement_type not in MANUAL_MOVEMENT_TYPES:
            raise AppError(
                status_code=422,
                error_code="INVALID_MOVEMENT_TYPE",
                message=(
                    "Tipo inválido para movimiento manual. Use: "
                    + ", ".join(sorted(MANUAL_MOVEMENT_TYPES))
                ),
            )
        value = money(amount)
        register = self.registers.get_open_for_user(user_id)
        if register is None:
            raise AppError(
                status_code=409,
                error_code="REGISTER_NOT_OPEN",
                message="No hay una caja abierta para este usuario",
            )
        if movement_type == MovementTypes.CASH_OUT:
            totals = self.movements_repo.totals_for_register(register)
            available = money(totals["expected_cash"])
            if value > available:
                raise AppError(
                    status_code=409,
                    error_code="INSUFFICIENT_CASH",
                    message=(
                        f"Egreso ({value}) excede el efectivo en caja "
                        f"({available})"
                    ),
                )
        try:
            movement = self.movements_repo.add(
                CashMovement(
                    register_id=register.id,
                    user_id=user_id,
                    movement_type=movement_type,
                    payment_method=None,
                    amount=value,
                    description=description.strip(),
                    reference_type=None,
                    reference_id=None,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(movement)
        return movement

    # ------------------------------------------------------------------
    # Integraciones transaccionales (sin commit; llamadas desde ventas y
    # cuentas por cobrar dentro de SU transacción).
    # ------------------------------------------------------------------
    def record_sale_movement_in_transaction(
        self, sale, user_id: UUID
    ) -> CashMovement | None:
        """Movimiento SALE para una venta recién confirmada.

        Sin caja abierta para el usuario NO hace nada (la venta sigue siendo
        válida fuera de un turno de caja). Venta CREDIT no genera movimiento
        (la deuda vive en la cuenta por cobrar). Idempotente: si ya existe
        un movimiento con reference (SALE, sale.id) no duplica.
        """
        if sale.payment_method == SalePaymentMethods.CREDIT:
            return None
        if money(sale.total) <= 0:
            # Venta con total cero no mueve efectivo (evita violar el
            # CHECK de montos positivos en movimientos distintos de
            # OPENING).
            return None
        register = self.registers.get_open_for_user(user_id)
        if register is None:
            return None
        reference_id = str(sale.id)
        if (
            self.movements_repo.get_by_reference(
                CashReferenceTypes.SALE, reference_id
            )
            is not None
        ):
            return None
        return self.movements_repo.add(
            CashMovement(
                register_id=register.id,
                user_id=user_id,
                movement_type=MovementTypes.SALE,
                payment_method=sale.payment_method,
                amount=money(sale.total),
                description=f"Venta {sale.sale_number}",
                reference_type=CashReferenceTypes.SALE,
                reference_id=reference_id,
            )
        )

    def record_receivable_payment_movement_in_transaction(
        self, payment, account, user_id: UUID
    ) -> CashMovement | None:
        """Movimiento RECEIVABLE_PAYMENT para un abono recién creado.

        Solo métodos CASH/CARD/TRANSFER (OTHER queda sin registro). Sin
        caja abierta no hace nada; idempotente por referencia al pago.
        """
        method = getattr(payment, "payment_method", None)
        if method not in ("CASH", "CARD", "TRANSFER"):
            return None
        register = self.registers.get_open_for_user(user_id)
        if register is None:
            return None
        reference_id = str(payment.id)
        if (
            self.movements_repo.get_by_reference(
                CashReferenceTypes.RECEIVABLE_PAYMENT, reference_id
            )
            is not None
        ):
            return None
        label = getattr(account, "reference_type", None) or "cuenta"
        number = getattr(account, "reference_id", None) or str(account.id)[:8]
        return self.movements_repo.add(
            CashMovement(
                register_id=register.id,
                user_id=user_id,
                movement_type=MovementTypes.RECEIVABLE_PAYMENT,
                payment_method=method,
                amount=money(payment.amount),
                description=f"Abono cuenta por cobrar ({label} {number})",
                reference_type=CashReferenceTypes.RECEIVABLE_PAYMENT,
                reference_id=reference_id,
            )
        )

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    def _tz():
        from datetime import timezone

        return timezone.utc

    def _ensure_exists(self, register_id: UUID) -> CashRegister:
        register = self.registers.get_by_id(register_id)
        if register is None:
            raise AppError(
                status_code=404,
                error_code="REGISTER_NOT_FOUND",
                message="Caja no encontrada",
            )
        return register

    def _get_loaded_register(self, register_id: UUID) -> CashRegister:
        register = self.registers.get_with_relations(register_id)
        if register is None:
            raise AppError(
                status_code=404,
                error_code="REGISTER_NOT_FOUND",
                message="Caja no encontrada",
            )
        return register
