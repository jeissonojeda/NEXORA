from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository

MONEY_QUANTUM = Decimal("0.01")


def money(value: Any) -> Decimal:
    """Normaliza un monto a Decimal escala 2 con redondeo comercial."""
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class CustomerCreditService:
    """Guardarraíles financieros del crédito de clientes.

    Es el ÚNICO componente autorizado para modificar
    ``customer.current_balance``. Todos los movimientos asumen que el
    llamador mantiene la fila del cliente bloqueada (FOR UPDATE) y que la
    persistencia final (COMMIT/ROLLBACK) es responsabilidad del llamador,
    de modo que varias operaciones puedan componerse en una transacción.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)

    def lock_customer(self, customer_id: UUID) -> Customer:
        customer = self.customers.get_for_update(customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                error_code="CUSTOMER_NOT_FOUND",
                message="Cliente no encontrado",
            )
        return customer

    @staticmethod
    def ensure_can_assume_debt(
        customer: Customer, additional_amount: Decimal
    ) -> None:
        """Valida crédito habilitado y cupo disponible para nueva deuda."""
        if not customer.is_active:
            raise AppError(
                status_code=409,
                error_code="CUSTOMER_INACTIVE",
                message="El cliente está inactivo",
            )
        if not customer.credit_enabled:
            raise AppError(
                status_code=409,
                error_code="CREDIT_NOT_ENABLED",
                message=(
                    "El cliente no tiene crédito habilitado "
                    "(credit_enabled=false)"
                ),
            )
        projected = money(customer.current_balance) + money(additional_amount)
        if projected > money(customer.credit_limit):
            raise AppError(
                status_code=409,
                error_code="CREDIT_LIMIT_EXCEEDED",
                message=(
                    f"El límite de crédito sería excedido: saldo proyectado "
                    f"{projected} > límite {money(customer.credit_limit)}"
                ),
            )

    @staticmethod
    def available_credit(customer: Customer) -> Decimal:
        return customer.credit_available

    @staticmethod
    def increase_balance(customer: Customer, amount: Decimal) -> None:
        """Suma deuda validando cupo. Requiere fila bloqueada."""
        amount = money(amount)
        if amount <= 0:
            raise AppError(
                status_code=422,
                error_code="INVALID_AMOUNT",
                message="El monto debe ser mayor que cero",
            )
        CustomerCreditService.ensure_can_assume_debt(customer, amount)
        customer.current_balance = money(customer.current_balance) + amount

    @staticmethod
    def decrease_balance(customer: Customer, amount: Decimal) -> None:
        """Resta deuda garantizando que el saldo nunca quede negativo."""
        amount = money(amount)
        if amount <= 0:
            raise AppError(
                status_code=422,
                error_code="INVALID_AMOUNT",
                message="El monto debe ser mayor que cero",
            )
        new_balance = money(customer.current_balance) - amount
        if new_balance < 0:
            raise AppError(
                status_code=409,
                error_code="CUSTOMER_BALANCE_NEGATIVE",
                message="La operación dejaría el saldo del cliente negativo",
            )
        customer.current_balance = new_balance
