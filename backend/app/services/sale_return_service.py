from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.customer import ReceivableAccount, ReceivableAccountStatuses
from app.models.purchase import MovementReferences
from app.models.sale import PaymentMethods, Sale, SaleStatuses
from app.models.sale_return import (
    RefundMethods,
    ReturnConditions,
    ReturnStatuses,
    ReturnTypes,
    SaleReturn,
    SaleReturnItem,
    VALID_REFUND_METHODS,
    VALID_RETURN_CONDITIONS,
)
from app.repositories.receivable_repository import ReceivableRepository
from app.repositories.sale_return_repository import SaleReturnRepository
from app.services.cash_service import CashService
from app.services.customer_credit_service import money
from app.services.inventory_service import InventoryService
from app.services.receivable_service import ReceivableService
from app.services.sale_service import SaleService


class SaleReturnService:
    """Devoluciones y cambios de ventas CONFIRMED.

    Reglas clave:

    - La venta original NUNCA se modifica (es inmutable); la devolución es un
      documento aparte (DEV-YYYY-NNNNNN) trazado a sus ítems.
    - Devolución total o parcial: valida que la cantidad devuelta no exceda lo
      vendido menos lo ya devuelto en devoluciones COMPLETED.
    - Reembolso: CASH genera CASH_OUT en la caja abierta del operador;
      CREDIT reduce la cuenta por cobrar de la venta (hasta su saldo);
      CARD/TRANSFER es reembolso externo registrado para trazabilidad.
    - Cambio (EXCHANGE): en la MISMA transacción se crea y confirma una nueva
      venta de reemplazo; el crédito de lo devuelto se aplica como descuento
      de esa venta y el excedente se reembolsa por el método elegido.
    - Todo es transaccional: un único COMMIT; ante cualquier error ROLLBACK
      completo (ni stock, ni saldo, ni caja quedan tocados parcialmente).
    - Idempotencia: clave única en BD; repetir la misma clave retorna la
      devolución original sin aplicar efectos.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.returns = SaleReturnRepository(db)
        self.sales = SaleService(db)
        self.inventory = InventoryService(db)
        self.cash = CashService(db)
        self.receivables = ReceivableService(db)
        self.receivable_accounts = ReceivableRepository(db)

    # ------------------------------------------------------------------
    # Numeración
    # ------------------------------------------------------------------
    @staticmethod
    def _advisory_lock(db: Session) -> None:
        """Serializa la generación de números en PostgreSQL."""
        from sqlalchemy import text

        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('sale_returns_number'))")
            )

    def _next_return_number(self) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"DEV-{year}-"
        last = self.returns.last_number_for_year(prefix)
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:06d}"

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_return(self, return_id: UUID) -> SaleReturn:
        sale_return = self.returns.get_with_items(return_id)
        if sale_return is None:
            raise AppError(
                status_code=404,
                error_code="SALE_RETURN_NOT_FOUND",
                message="Devolución no encontrada",
            )
        return sale_return

    def list_returns_for_sale(
        self, sale_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[SaleReturn], int]:
        return self.returns.search_for_sale(sale_id, skip=skip, limit=limit)

    # ------------------------------------------------------------------
    # Creación (transacción única)
    # ------------------------------------------------------------------
    def create_return(
        self,
        sale_id: UUID,
        created_by: UUID,
        refund_method: str,
        items: list[dict],
        reason: str | None = None,
        idempotency_key: str | None = None,
        exchange_items: list[dict] | None = None,
        exchange_payment_method: str | None = None,
    ) -> SaleReturn:
        key = idempotency_key.strip() if idempotency_key else None
        if key is not None:
            existing = self.returns.get_by_idempotency_key(key)
            if existing is not None:
                return self.get_return(existing.id)

        if refund_method not in VALID_REFUND_METHODS:
            raise AppError(
                status_code=422,
                error_code="INVALID_REFUND_METHOD",
                message=(
                    "Método de reembolso inválido. Use uno de: "
                    + ", ".join(sorted(VALID_REFUND_METHODS))
                ),
            )
        if not items:
            raise AppError(
                status_code=422,
                error_code="RETURN_EMPTY",
                message="La devolución debe incluir al menos un producto",
            )

        exchange_items = exchange_items or []
        is_exchange = bool(exchange_items)

        try:
            sale_return_id = self._create_return_in_transaction(
                sale_id=sale_id,
                created_by=created_by,
                refund_method=refund_method,
                items=items,
                reason=reason,
                key=key,
                exchange_items=exchange_items,
                exchange_payment_method=exchange_payment_method,
                is_exchange=is_exchange,
            )
            self.db.commit()
        except IntegrityError:
            # Carrera perdida sobre UNIQUE(idempotency_key): devolver la
            # devolución ganadora garantiza que nunca se aplique dos veces.
            self.db.rollback()
            if key is not None:
                existing = self.returns.get_by_idempotency_key(key)
                if existing is not None:
                    return self.get_return(existing.id)
            raise AppError(
                status_code=409,
                error_code="RETURN_IDEMPOTENCY_CONFLICT",
                message="Conflicto de clave de idempotencia",
            )
        except Exception:
            self.db.rollback()
            raise

        return self.get_return(sale_return_id)

    def _create_return_in_transaction(
        self,
        *,
        sale_id: UUID,
        created_by: UUID,
        refund_method: str,
        items: list[dict],
        reason: str | None,
        key: str | None,
        exchange_items: list[dict],
        exchange_payment_method: str | None,
        is_exchange: bool,
    ) -> UUID:
        return_type = ReturnTypes.EXCHANGE if is_exchange else ReturnTypes.RETURN

        # Bloquea la venta (SELECT ... FOR UPDATE) hasta el COMMIT.
        sale = self.sales.sales.get_for_update(sale_id)
        if sale is None:
            raise AppError(
                status_code=404,
                error_code="SALE_NOT_FOUND",
                message="Venta no encontrada",
            )
        if sale.status != SaleStatuses.CONFIRMED:
            raise AppError(
                status_code=409,
                error_code="SALE_NOT_CONFIRMED",
                message="Solo se puede devolver una venta confirmada",
            )

        if key is not None:
            # Re-chequeo bajo lock: otra petición pudo ganar la carrera.
            existing = self.returns.get_by_idempotency_key(key)
            if existing is not None:
                return existing.id

        # Cantidad ya devuelta por ítem (devoluciones COMPLETED).
        returned_by_item = self.returns.sum_returned_quantity_for_sale(sale.id)
        sale_items = {item.id: item for item in sale.items}

        # Valida y calcula cada línea de devolución (proporcional al ítem
        # original: unit_price/descuento/impuesto son snapshot histórico).
        planned: list[tuple[SaleReturnItem, object]] = []
        seen_items: set[UUID] = set()
        for raw in items:
            sale_item_id = UUID(str(raw["sale_item_id"]))
            if sale_item_id in seen_items:
                raise AppError(
                    status_code=409,
                    error_code="RETURN_ITEM_DUPLICATE",
                    message="El ítem de venta aparece más de una vez",
                )
            seen_items.add(sale_item_id)
            sale_item = sale_items.get(sale_item_id)
            if sale_item is None:
                raise AppError(
                    status_code=404,
                    error_code="SALE_ITEM_NOT_FOUND",
                    message="El ítem no pertenece a esta venta",
                )
            quantity = int(raw["quantity"])
            if quantity <= 0:
                raise AppError(
                    status_code=422,
                    error_code="INVALID_QUANTITY",
                    message="La cantidad debe ser mayor que cero",
                )
            already = returned_by_item.get(sale_item_id, 0)
            available = sale_item.quantity - already
            if quantity > available:
                raise AppError(
                    status_code=409,
                    error_code="RETURN_EXCEEDS_SOLD",
                    message=(
                        f"La cantidad a devolver ({quantity}) excede lo "
                        f"disponible ({available}) del producto "
                        f"{sale_item.product_name or sale_item.product_id}"
                    ),
                )
            condition = raw.get("condition") or ReturnConditions.RESALE
            if condition not in VALID_RETURN_CONDITIONS:
                raise AppError(
                    status_code=422,
                    error_code="INVALID_RETURN_CONDITION",
                    message=(
                        "Condición inválida. Use una de: "
                        + ", ".join(sorted(VALID_RETURN_CONDITIONS))
                    ),
                )

            # Montos proporcionales: total_del_linea * cantidad_devuelta /
            # cantidad_vendida (respetando descuento e impuesto del snapshot).
            ratio = Decimal(quantity) / Decimal(sale_item.quantity)
            unit_price = money(sale_item.unit_price)
            line_discount = money(sale_item.discount) * ratio
            line_tax = money(sale_item.tax) * ratio
            line_subtotal = money(Decimal(quantity) * unit_price)
            line_total = money(line_subtotal - line_discount + line_tax)
            restock = condition == ReturnConditions.RESALE

            return_item = SaleReturnItem(
                sale_item_id=sale_item.id,
                product_id=sale_item.product_id,
                quantity=quantity,
                unit_price=unit_price,
                discount=money(line_discount),
                tax=money(line_tax),
                tax_rate=money(sale_item.tax_rate),
                tax_name=sale_item.tax_name,
                subtotal=line_subtotal,
                total=line_total,
                restock=restock,
                condition=condition,
            )
            planned.append((return_item, sale_item))

        return_total = money(sum((ri.total for ri, _ in planned), Decimal("0")))
        if return_total <= 0:
            raise AppError(
                status_code=422,
                error_code="RETURN_AMOUNT_POSITIVE",
                message="El total de la devolución debe ser mayor que cero",
            )
        return_subtotal = money(
            sum((ri.subtotal for ri, _ in planned), Decimal("0"))
        )
        return_tax = money(sum((ri.tax for ri, _ in planned), Decimal("0")))

        # Número DEV-YYYY-NNNNNN. El advisory lock serializa la generación en
        # PostgreSQL (mismo patrón que las ventas); en SQLite el lock global
        # de escritura serializa las transacciones.
        self._advisory_lock(self.db)
        sale_return = SaleReturn(
            return_number=self._next_return_number(),
            sale_id=sale.id,
            status=ReturnStatuses.COMPLETED,
            return_type=return_type,
            refund_method=refund_method,
            reason=(reason.strip() or None) if reason else None,
            subtotal=return_subtotal,
            tax=return_tax,
            total=return_total,
            credit_applied=Decimal("0"),
            refunded_amount=Decimal("0"),
            idempotency_key=key,
            created_by=created_by,
        )
        for return_item, _sale_item in planned:
            sale_return.items.append(return_item)
        self.db.add(sale_return)
        self.db.flush()

        # Reingreso de stock vendible (solo RESALE); SIN commit.
        for return_item in sale_return.items:
            if return_item.restock:
                self.inventory.apply_return(
                    product_id=return_item.product_id,
                    quantity=return_item.quantity,
                    created_by=created_by,
                    reason=f"Devolución {sale_return.return_number}",
                    reference_id=str(sale_return.id),
                    reference_type=MovementReferences.SALE_RETURN,
                )

        credit_applied = Decimal("0")
        refunded_amount = Decimal("0")

        if is_exchange:
            credit_applied, refunded_amount = self._apply_exchange(
                sale=sale,
                sale_return=sale_return,
                credit=return_total,
                exchange_items=exchange_items,
                exchange_payment_method=exchange_payment_method,
                created_by=created_by,
            )
        else:
            refunded_amount = return_total

        sale_return.credit_applied = money(credit_applied)
        sale_return.refunded_amount = money(refunded_amount)

        # Reembolso por el método elegido (solo si hay monto a reembolsar).
        if money(refunded_amount) > 0:
            if refund_method == RefundMethods.CASH:
                self._require_open_register(created_by)
                self.cash.record_sale_return_refund_in_transaction(
                    sale_return, user_id=created_by
                )
            elif refund_method == RefundMethods.CREDIT:
                self._refund_credit(sale, refunded_amount)

        # CARD/TRANSFER: reembolso externo; queda registrado en el documento
        # (refunded_amount) para trazabilidad, sin movimiento de caja.

        self.db.flush()
        return sale_return.id

    # ------------------------------------------------------------------
    # Cambio (EXCHANGE): nueva venta de reemplazo en la MISMA transacción
    # ------------------------------------------------------------------
    def _apply_exchange(
        self,
        *,
        sale: Sale,
        sale_return: SaleReturn,
        credit: Decimal,
        exchange_items: list[dict],
        exchange_payment_method: str | None,
        created_by: UUID,
    ) -> tuple[Decimal, Decimal]:
        """Crea y confirma la venta de cambio; retorna (crédito_aplicado, excedente)."""
        payment_method = exchange_payment_method or sale.payment_method
        customer_id = sale.customer_id

        exchange_sale = self.sales.create_sale_in_transaction(
            created_by=created_by,
            customer_id=customer_id,
            payment_method=payment_method,
            amount_paid=Decimal("0"),
            notes=(
                f"Cambio por devolución {sale_return.return_number} "
                f"(venta {sale.sale_number})"
            ),
            items=exchange_items,
        )

        # El crédito de lo devuelto se aplica como descuento de cabecera de
        # la nueva venta; el descuento no puede exceder el subtotal.
        credit_applied = money(min(credit, exchange_sale.subtotal))
        exchange_sale.discount = money(
            money(exchange_sale.discount) + credit_applied
        )
        # Recalcula totales con el descuento aplicado.
        subtotal = money(
            sum((item.subtotal for item in exchange_sale.items), Decimal("0"))
        )
        discount = money(exchange_sale.discount)
        tax = money(exchange_sale.tax)
        if tax == 0:
            items_tax = money(
                sum((item.tax for item in exchange_sale.items), Decimal("0"))
            )
            if items_tax > 0:
                tax = items_tax
                exchange_sale.tax = tax
        exchange_sale.subtotal = subtotal
        exchange_sale.total = money(subtotal - discount + tax)

        # Confirma la venta de cambio (descuenta stock de los productos
        # nuevos, crea cuenta si es CREDIT y movimiento de caja si aplica).
        self.sales.confirm_sale_in_transaction(
            exchange_sale.id, confirmed_by=created_by
        )

        sale_return.exchange_sale_id = exchange_sale.id
        excess = money(credit - credit_applied)
        return credit_applied, excess

    # ------------------------------------------------------------------
    # Reembolsos
    # ------------------------------------------------------------------
    def _require_open_register(self, user_id: UUID) -> None:
        register = self.cash.registers.get_open_for_user(user_id)
        if register is None:
            raise AppError(
                status_code=409,
                error_code="REGISTER_NOT_OPEN",
                message=(
                    "El reembolso en efectivo requiere una caja abierta "
                    "para el usuario"
                ),
            )

    def _refund_credit(self, sale: Sale, amount: Decimal) -> None:
        """Reduce la cuenta por cobrar de la venta original (crédito)."""
        account = self._find_sale_receivable(sale.id)
        if account is None:
            raise AppError(
                status_code=409,
                error_code="SALE_HAS_NO_RECEIVABLE",
                message=(
                    "La venta no tiene cuenta por cobrar; use reembolso "
                    "en efectivo u otro método"
                ),
            )
        self.receivables.apply_refund_in_transaction(
            account_id=account.id,
            amount=amount,
            description=f"Devolución de venta {sale.sale_number}",
        )

    def _find_sale_receivable(self, sale_id: UUID) -> ReceivableAccount | None:
        from sqlalchemy import select

        stmt = (
            select(ReceivableAccount)
            .where(
                ReceivableAccount.reference_type == MovementReferences.SALE,
                ReceivableAccount.reference_id == str(sale_id),
                ReceivableAccount.status.in_(
                    [
                        ReceivableAccountStatuses.OPEN,
                        ReceivableAccountStatuses.PARTIALLY_PAID,
                    ]
                ),
            )
            .with_for_update()
        )
        return self.db.scalars(stmt).first()

    # ------------------------------------------------------------------
    # Anulación de una devolución (write-off administrativo)
    # ------------------------------------------------------------------
    def cancel_return(self, return_id: UUID) -> SaleReturn:
        """Anula una devolución ya registrada (historial conservado).

        No re-ingresa stock ni revierte reembolsos automáticamente: es una
        corrección administrativa; el efecto sobre inventario/caja debe
        registrarse como movimiento/ajuste manual correspondiente.
        """
        try:
            sale_return = self.returns.get_for_update(return_id)
            if sale_return is None:
                raise AppError(
                    status_code=404,
                    error_code="SALE_RETURN_NOT_FOUND",
                    message="Devolución no encontrada",
                )
            if sale_return.status == ReturnStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="RETURN_ALREADY_CANCELLED",
                    message="La devolución ya está cancelada",
                )
            sale_return.status = ReturnStatuses.CANCELLED
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(sale_return)
        return self.get_return(sale_return.id)
