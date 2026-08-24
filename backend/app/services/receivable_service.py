from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.customer import (
    PaymentMethods,
    ReceivableAccount,
    ReceivableAccountStatuses,
    ReceivablePayment,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.receivable_repository import (
    ReceivablePaymentRepository,
    ReceivableRepository,
)
from app.services.customer_credit_service import CustomerCreditService, money

VALID_REFERENCES = {"MANUAL", "SALE"}


class ReceivableService:
    """Cuentas por cobrar y pagos.

    Transaccionalidad: crear cuenta / registrar pago / anular son operaciones
    atómicas que bloquean con SELECT ... FOR UPDATE la fila de la cuenta y
    del cliente. El saldo del cliente SOLO se mueve vía CustomerCreditService.
    Idempotencia de pagos: si se envía ``idempotency_key`` y ya existe un pago
    con esa clave, se retorna el pago original sin aplicar ningún movimiento
    (única restricción UNIQUE en BD como red de seguridad ante carreras).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.receivables = ReceivableRepository(db)
        self.payments_repo = ReceivablePaymentRepository(db)
        self.credit = CustomerCreditService(db)
        self.customers = CustomerRepository(db)

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def _get_account(self, account_id: UUID) -> ReceivableAccount:
        account = self.receivables.get_with_relations(account_id)
        if account is None:
            raise AppError(
                status_code=404,
                error_code="RECEIVABLE_NOT_FOUND",
                message="Cuenta por cobrar no encontrada",
            )
        return account

    def get_account(self, account_id: UUID) -> ReceivableAccount:
        return self._get_account(account_id)

    def list_accounts(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        due_from=None,
        due_to=None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReceivableAccount], int]:
        if status is not None and status not in (
            ReceivableAccountStatuses.OPEN,
            ReceivableAccountStatuses.PARTIALLY_PAID,
            ReceivableAccountStatuses.PAID,
            ReceivableAccountStatuses.CANCELLED,
        ):
            raise AppError(
                status_code=422,
                error_code="INVALID_RECEIVABLE_STATUS",
                message="Estado inválido",
            )
        return self.receivables.search(
            customer_id=customer_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            due_from=due_from,
            due_to=due_to,
            skip=skip,
            limit=limit,
        )

    def list_payments_of_account(
        self, account_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[ReceivablePayment], int]:
        # Valida existencia antes de listar (404 coherente).
        self._get_account(account_id)
        payments, total = self.payments_repo.search_for_account(
            account_id, skip=skip, limit=limit
        )
        for payment in payments:
            _ = payment.created_by_username  # precarga user para serializar
        return payments, total

    # ------------------------------------------------------------------
    # Crear cuenta por cobrar
    # ------------------------------------------------------------------
    def _create_receivable_core(
        self,
        customer_id: UUID,
        original_amount: Decimal,
        description: str | None,
        due_date,
        reference_type: str,
        reference_id: str | None,
    ) -> ReceivableAccount:
        """Núcleo de creación de cuenta SIN commit ni rollback.

        Valida monto/referencia, bloquea al cliente, verifica cupo
        (ensure_can_assume_debt), crea la cuenta OPEN y aumenta el saldo vía
        CustomerCreditService. Participa en la transacción del llamador:
        si algo falla después (p. ej. el descuento de stock en una venta),
        el rollback del llamador deshace también la cuenta y el saldo.
        """
        if reference_type not in VALID_REFERENCES:
            raise AppError(
                status_code=422,
                error_code="INVALID_REFERENCE_TYPE",
                message=f"reference_type debe ser uno de: {sorted(VALID_REFERENCES)}",
            )
        amount = money(original_amount)
        if amount <= 0:
            raise AppError(
                status_code=422,
                error_code="RECEIVABLE_AMOUNT_POSITIVE",
                message="El monto debe ser mayor que cero",
            )
        customer = self.credit.lock_customer(customer_id)  # 404 si no existe
        self.credit.ensure_can_assume_debt(customer, amount)
        account = ReceivableAccount(
            customer_id=customer.id,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description.strip() if description else None,
            original_amount=amount,
            paid_amount=money(Decimal("0")),
            balance=amount,
            due_date=due_date,
            status=ReceivableAccountStatuses.OPEN,
        )
        self.receivables.add(account)
        self.credit.increase_balance(customer, amount)
        return account

    def create_receivable_in_transaction(
        self,
        customer_id: UUID,
        original_amount: Decimal,
        description: str | None = None,
        due_date=None,
        reference_type: str = "SALE",
        reference_id: str | None = None,
    ) -> ReceivableAccount:
        """Variante sin commit para composición transaccional.

        SalesService la usa dentro de la confirmación de una venta a crédito:
        la cuenta por cobrar se crea en la MISMA transacción que el descuento
        de stock y el cambio de estado de la venta.
        """
        return self._create_receivable_core(
            customer_id=customer_id,
            original_amount=original_amount,
            description=description,
            due_date=due_date,
            reference_type=reference_type,
            reference_id=reference_id,
        )

    def create_receivable(
        self,
        customer_id: UUID,
        original_amount: Decimal,
        description: str | None = None,
        due_date=None,
        reference_type: str = "MANUAL",
        reference_id: str | None = None,
    ) -> ReceivableAccount:
        """API de servicio con commit propio (operación independiente)."""
        try:
            account = self._create_receivable_core(
                customer_id=customer_id,
                original_amount=original_amount,
                description=description,
                due_date=due_date,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(account)
        return account

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------
    def register_payment(
        self,
        account_id: UUID,
        *,
        amount: Decimal,
        payment_method: str,
        created_by: UUID,
        reference: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[ReceivablePayment, bool]:
        """Registra un pago de forma atómica.

        Retorna ``(pago, creado)``; ``creado=False`` indica respuesta
        idempotente (la clave ya existía y NO se aplicó ningún movimiento).
        """
        key = idempotency_key.strip() if idempotency_key else None
        payment_amount = money(amount)
        if payment_amount <= 0:
            raise AppError(
                status_code=422,
                error_code="PAYMENT_AMOUNT_POSITIVE",
                message="El pago debe ser mayor que cero",
            )
        if payment_method not in (
            PaymentMethods.CASH,
            PaymentMethods.CARD,
            PaymentMethods.TRANSFER,
            PaymentMethods.OTHER,
        ):
            raise AppError(
                status_code=422,
                error_code="INVALID_PAYMENT_METHOD",
                message="Método de pago inválido",
            )

        if key is not None:
            existing = self.payments_repo.get_by_idempotency_key(key)
            if existing is not None:
                return existing, False

        try:
            account = self.receivables.get_for_update(account_id)
            if account is None:
                raise AppError(
                    status_code=404,
                    error_code="RECEIVABLE_NOT_FOUND",
                    message="Cuenta por cobrar no encontrada",
                )
            if key is not None:
                # Re-chequeo bajo lock: otra petición pudo ganar la carrera.
                existing = self.payments_repo.get_by_idempotency_key(key)
                if existing is not None:
                    self.db.rollback()
                    return existing, False
            if account.status == ReceivableAccountStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="RECEIVABLE_CANCELLED",
                    message="La cuenta está cancelada y no admite pagos",
                )
            if account.status == ReceivableAccountStatuses.PAID:
                raise AppError(
                    status_code=409,
                    error_code="RECEIVABLE_ALREADY_PAID",
                    message="La cuenta ya está pagada en su totalidad",
                )
            balance = money(account.balance)
            if payment_amount > balance:
                raise AppError(
                    status_code=409,
                    error_code="PAYMENT_EXCEEDS_BALANCE",
                    message=(
                        f"El pago ({payment_amount}) excede el saldo "
                        f"pendiente ({balance})"
                    ),
                )

            customer = self.credit.lock_customer(account.customer_id)

            payment = ReceivablePayment(
                receivable_account_id=account.id,
                amount=payment_amount,
                payment_method=payment_method,
                reference=_clean(reference),
                idempotency_key=key,
                notes=_clean(notes),
                created_by=created_by,
            )
            self.payments_repo.add(payment)

            new_paid = money(account.paid_amount) + payment_amount
            account.paid_amount = new_paid
            account.balance = money(account.original_amount) - new_paid
            account.status = (
                ReceivableAccountStatuses.PAID
                if account.balance == 0
                else ReceivableAccountStatuses.PARTIALLY_PAID
            )

            self.credit.decrease_balance(customer, payment_amount)

            self.db.commit()
        except IntegrityError:
            # Carrera perdida sobre UNIQUE(idempotency_key): devolver el pago
            # ganador garantiza que nunca se aplique dos veces.
            self.db.rollback()
            if key is not None:
                existing = self.payments_repo.get_by_idempotency_key(key)
                if existing is not None:
                    return existing, False
            raise AppError(
                status_code=409,
                error_code="PAYMENT_IDEMPOTENCY_CONFLICT",
                message="Conflicto de clave de idempotencia",
            )
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(payment)
        return payment, True

    # ------------------------------------------------------------------
    # Anulación (write-off del saldo restante)
    # ------------------------------------------------------------------
    def cancel_receivable(self, account_id: UUID) -> ReceivableAccount:
        """Anula la cuenta; el saldo pendiente sale del saldo del cliente.

        Los pagos ya realizados se conservan como historial inmutable.
        """
        try:
            account = self.receivables.get_for_update(account_id)
            if account is None:
                raise AppError(
                    status_code=404,
                    error_code="RECEIVABLE_NOT_FOUND",
                    message="Cuenta por cobrar no encontrada",
                )
            if account.status == ReceivableAccountStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="RECEIVABLE_ALREADY_CANCELLED",
                    message="La cuenta ya está cancelada",
                )
            if account.status == ReceivableAccountStatuses.PAID:
                raise AppError(
                    status_code=409,
                    error_code="RECEIVABLE_ALREADY_PAID",
                    message="Una cuenta pagada no puede cancelarse",
                )

            remaining = money(account.balance)
            customer = self.credit.lock_customer(account.customer_id)
            if remaining > 0:
                self.credit.decrease_balance(customer, remaining)
            account.status = ReceivableAccountStatuses.CANCELLED
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(account)
        return account

    # ------------------------------------------------------------------
    # Estado de cuenta
    # ------------------------------------------------------------------
    def statement(
        self,
        customer_id: UUID,
        accounts_skip: int = 0,
        accounts_limit: int = 20,
        payments_skip: int = 0,
        payments_limit: int = 20,
    ) -> dict[str, Any]:
        customer = self.customers.get_by_id(customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                error_code="CUSTOMER_NOT_FOUND",
                message="Cliente no encontrado",
            )

        by_status = self.receivables.count_by_status(customer_id)
        open_count = by_status.get(ReceivableAccountStatuses.OPEN, (0, Decimal("0")))
        partial_count = by_status.get(
            ReceivableAccountStatuses.PARTIALLY_PAID, (0, Decimal("0"))
        )
        paid_count = by_status.get(ReceivableAccountStatuses.PAID, (0, Decimal("0")))
        cancelled_count = by_status.get(
            ReceivableAccountStatuses.CANCELLED, (0, Decimal("0"))
        )
        total_balance = money(open_count[1]) + money(partial_count[1])

        accounts, accounts_total = self.receivables.search(
            customer_id=customer_id,
            skip=accounts_skip,
            limit=accounts_limit,
        )
        payments, payments_total = self.payments_repo.search(
            customer_id=customer_id,
            skip=payments_skip,
            limit=payments_limit,
        )

        return {
            "customer": customer,
            "credit": {
                "credit_enabled": customer.credit_enabled,
                "credit_limit": money(customer.credit_limit),
                "current_balance": money(customer.current_balance),
                "credit_available": customer.credit_available,
            },
            "summary": {
                "open_count": open_count[0],
                "partially_paid_count": partial_count[0],
                "paid_count": paid_count[0],
                "cancelled_count": cancelled_count[0],
                "total_balance": total_balance,
            },
            "accounts": {"items": accounts, "total": accounts_total},
            "payments": {"items": payments, "total": payments_total},
        }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
