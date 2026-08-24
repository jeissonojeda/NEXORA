from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.services.customer_credit_service import money

NULLABLE_FIELDS = (
    "identification",
    "phone",
    "email",
    "address",
    "city",
    "notes",
)


def _normalize_optional(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)

    def _ensure_unique_identification(
        self, identification: str | None, exclude_customer_id: UUID | None = None
    ) -> None:
        if identification is None:
            return
        existing = self.customers.get_by_identification(identification)
        if existing is not None and existing.id != exclude_customer_id:
            raise AppError(
                status_code=409,
                error_code="CUSTOMER_IDENTIFICATION_ALREADY_EXISTS",
                message="Ya existe un cliente con esa identificación",
            )

    @staticmethod
    def _validate_credit_change(
        customer: Customer,
        new_limit: Any | None,
        enable_credit: bool | None,
    ) -> None:
        """El límite nunca puede quedar por debajo del saldo actual."""
        final_limit = (
            money(new_limit) if new_limit is not None else money(customer.credit_limit)
        )
        balance = money(customer.current_balance)

        if new_limit is not None and final_limit < balance:
            raise AppError(
                status_code=409,
                error_code="CREDIT_LIMIT_BELOW_BALANCE",
                message=(
                    f"El límite ({final_limit}) no puede ser inferior al "
                    f"saldo actual ({balance})"
                ),
            )
        if enable_credit and final_limit <= 0:
            raise AppError(
                status_code=422,
                error_code="CREDIT_LIMIT_REQUIRED",
                message=(
                    "Para habilitar crédito debe definirse un límite "
                    "mayor que cero"
                ),
            )
        if enable_credit and balance > final_limit:
            raise AppError(
                status_code=409,
                error_code="CREDIT_LIMIT_BELOW_BALANCE",
                message=(
                    f"No se puede habilitar crédito: saldo ({balance}) "
                    f"supera el límite ({final_limit})"
                ),
            )

    def create_customer(self, **fields: Any) -> Customer:
        name = str(fields["name"]).strip()
        identification = _normalize_optional(fields.get("identification"))
        self._ensure_unique_identification(identification)

        credit_limit = money(fields.get("credit_limit") or Decimal("0"))
        if fields.get("credit_enabled") and credit_limit <= 0:
            raise AppError(
                status_code=422,
                error_code="CREDIT_LIMIT_REQUIRED",
                message=(
                    "Para habilitar crédito debe definirse un límite "
                    "mayor que cero"
                ),
            )

        customer = Customer(
            name=name,
            identification=identification,
            phone=_normalize_optional(fields.get("phone")),
            email=_normalize_optional(fields.get("email")),
            address=_normalize_optional(fields.get("address")),
            city=_normalize_optional(fields.get("city")),
            notes=_normalize_optional(fields.get("notes")),
            is_active=True,
            credit_enabled=bool(fields.get("credit_enabled", False)),
            credit_limit=credit_limit,
            current_balance=money(Decimal("0")),
        )
        self.customers.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def get_customer(self, customer_id: UUID) -> Customer:
        customer = self.customers.get_by_id(customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                error_code="CUSTOMER_NOT_FOUND",
                message="Cliente no encontrado",
            )
        return customer

    def list_customers(
        self,
        q: str | None = None,
        is_active: bool | None = None,
        credit_enabled: bool | None = None,
        order_by: str = "name",
        order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        return self.customers.search(
            q=q,
            is_active=is_active,
            credit_enabled=credit_enabled,
            order_by=order_by,
            order=order,
            skip=skip,
            limit=limit,
        )

    def update_customer(self, customer_id: UUID, **fields: Any) -> Customer:
        customer = self.get_customer(customer_id)

        new_name = fields.get("name")
        if new_name is not None:
            customer.name = str(new_name).strip()

        if "identification" in fields:
            new_identification = _normalize_optional(fields.get("identification"))
            self._ensure_unique_identification(
                new_identification, exclude_customer_id=customer.id
            )
            customer.identification = new_identification

        for field in NULLABLE_FIELDS:
            if field == "identification" or field not in fields:
                continue
            setattr(customer, field, _normalize_optional(fields.get(field)))

        self._validate_credit_change(
            customer,
            new_limit=fields.get("credit_limit"),
            enable_credit=fields.get("credit_enabled"),
        )
        if fields.get("credit_limit") is not None:
            customer.credit_limit = money(fields["credit_limit"])
        if fields.get("credit_enabled") is not None:
            customer.credit_enabled = bool(fields["credit_enabled"])

        is_active = fields.get("is_active")
        if is_active is not None:
            customer.is_active = bool(is_active)

        self.db.commit()
        self.db.refresh(customer)
        return customer

    def deactivate_customer(self, customer_id: UUID) -> Customer:
        """Borrado lógico: conserva historial financiero íntegro.

        Un cliente inactivo no podrá usarse en ventas futuras, pero sus
        cuentas por cobrar y pagos permanecen intactos para auditoría.
        """
        customer = self.get_customer(customer_id)
        customer.is_active = False
        self.db.commit()
        self.db.refresh(customer)
        return customer
