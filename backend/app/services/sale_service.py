from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.customer import Customer
from app.models.purchase import MovementReferences
from app.models.sale import (
    FULL_PAYMENT_METHODS,
    PaymentMethods,
    Sale,
    SaleItem,
    SaleStatuses,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sale_repository import SaleRepository
from app.services.customer_credit_service import money
from app.services.inventory_service import InventoryService
from app.services.receivable_service import ReceivableService

MAX_NUMBER_RETRIES = 5


class SaleService:
    """Lógica de negocio de ventas y facturación interna.

    La confirmación es transaccional: valida venta/productos/pagos/crédito,
    descuenta stock vía InventoryService.apply_exit (sin commits
    intermedios, movimiento EXIT con reference_type='SALE'), crea la cuenta
    por cobrar en caso de venta a crédito (ReceivableService, misma
    transacción), marca la venta como CONFIRMED y hace un único COMMIT.
    Ante cualquier error ejecuta ROLLBACK completo: ni stock, ni saldo del
    cliente, ni cuentas quedan tocados parcialmente. Es idempotente: solo
    una venta DRAFT puede confirmarse y el bloqueo de fila evita dobles
    confirmaciones concurrentes.

    El dinero se maneja SIEMPRE como Decimal (NUMERIC en BD); los precios
    de los ítems son snapshot históricos: cambiar Product.sale_price no
    recalcula ventas pasadas.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales = SaleRepository(db)
        self.products = ProductRepository(db)
        self.customers = CustomerRepository(db)

    # ------------------------------------------------------------------
    # Validaciones compartidas
    # ------------------------------------------------------------------
    def _get_sale(self, sale_id: UUID) -> Sale:
        sale = self.sales.get_by_id(sale_id)
        if sale is None:
            raise AppError(
                status_code=404,
                error_code="SALE_NOT_FOUND",
                message="Venta no encontrada",
            )
        return sale

    def _get_sale_with_items(self, sale_id: UUID) -> Sale:
        sale = self.sales.get_with_items(sale_id)
        if sale is None:
            raise AppError(
                status_code=404,
                error_code="SALE_NOT_FOUND",
                message="Venta no encontrada",
            )
        return sale

    @staticmethod
    def _ensure_editable(sale: Sale) -> None:
        if sale.status == SaleStatuses.CONFIRMED:
            raise AppError(
                status_code=409,
                error_code="SALE_ALREADY_CONFIRMED",
                message="La venta ya está confirmada y no puede modificarse",
            )
        if sale.status == SaleStatuses.CANCELLED:
            raise AppError(
                status_code=409,
                error_code="SALE_CANCELLED",
                message="La venta está cancelada y no puede modificarse",
            )

    def _validate_customer(self, customer_id: UUID) -> Customer:
        customer = self.customers.get_by_id(customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                error_code="CUSTOMER_NOT_FOUND",
                message="Cliente no encontrado",
            )
        if not customer.is_active:
            raise AppError(
                status_code=409,
                error_code="CUSTOMER_INACTIVE",
                message="El cliente está inactivo",
            )
        return customer

    def _validate_product(self, product_id: UUID):
        product = self.products.get_by_id(product_id)
        if product is None:
            raise AppError(
                status_code=404,
                error_code="PRODUCT_NOT_FOUND",
                message="Producto no encontrado",
            )
        if not product.is_active:
            raise AppError(
                status_code=409,
                error_code="PRODUCT_INACTIVE",
                message="El producto está inactivo",
            )
        return product

    # ------------------------------------------------------------------
    # Cálculos (Decimal, sin float)
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_item_totals(
        quantity: int, unit_price: Decimal, discount: Decimal, tax: Decimal
    ) -> tuple[Decimal, Decimal]:
        unit_price = money(unit_price)
        discount = money(discount)
        tax = money(tax)
        subtotal = money(Decimal(quantity) * unit_price)
        if discount > subtotal:
            raise AppError(
                status_code=422,
                error_code="ITEM_DISCOUNT_EXCEEDS_SUBTOTAL",
                message=(
                    f"El descuento del ítem ({discount}) excede su "
                    f"subtotal ({subtotal})"
                ),
            )
        total = money(subtotal - discount + tax)
        return subtotal, total

    @staticmethod
    def _fill_item(item: SaleItem) -> SaleItem:
        item.unit_price = money(item.unit_price)
        item.discount = money(item.discount)
        item.tax = money(item.tax)
        item.subtotal, item.total = SaleService._compute_item_totals(
            item.quantity, item.unit_price, item.discount, item.tax
        )
        return item

    def _recalculate_header(self, sale: Sale) -> None:
        subtotal = money(
            sum((item.subtotal for item in sale.items), Decimal("0"))
        )
        discount = money(sale.discount)
        tax = money(sale.tax)
        if discount > subtotal:
            raise AppError(
                status_code=422,
                error_code="DISCOUNT_EXCEEDS_SUBTOTAL",
                message=(
                    f"El descuento ({discount}) excede el subtotal "
                    f"({subtotal})"
                ),
            )
        sale.subtotal = subtotal
        sale.total = money(subtotal - discount + tax)

    # ------------------------------------------------------------------
    # Pagos: coherencia se valida al CONFIRMAR; en DRAFT se almacena lo
    # enviado para que el cajero edite libremente el carrito.
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_payment_at_confirm(sale: Sale) -> None:
        total = money(sale.total)
        if sale.payment_method == PaymentMethods.CASH:
            paid = money(sale.amount_paid or Decimal("0"))
            if paid == 0:
                # Sin registro de efectivo recibido se asume pago exacto
                # (flujo POS por defecto).
                sale.amount_paid = total
                sale.change_due = money(Decimal("0"))
                return
            if paid < total:
                raise AppError(
                    status_code=422,
                    error_code="PAYMENT_INSUFFICIENT",
                    message=(
                        f"Efectivo recibido ({paid}) insuficiente para el "
                        f"total ({total})"
                    ),
                )
            sale.amount_paid = paid
            sale.change_due = money(paid - total)
        elif sale.payment_method == PaymentMethods.CREDIT:
            # El cobro real ocurre cuando el cliente pague la cuenta por
            # cobrar generada; la venta misma no registra efectivo.
            sale.amount_paid = money(Decimal("0"))
            sale.change_due = money(Decimal("0"))
        else:
            # CARD/TRANSFER: pago electrónico exacto por el total.
            sale.amount_paid = total
            sale.change_due = money(Decimal("0"))

    def _resolve_payment_customer(
        self, payment_method: str, customer_id: UUID | None
    ) -> Customer | None:
        """Valida la pareja método/cliente en creación y edición DRAFT."""
        if payment_method == PaymentMethods.CREDIT:
            if customer_id is None:
                raise AppError(
                    status_code=422,
                    error_code="CUSTOMER_REQUIRED_FOR_CREDIT",
                    message=(
                        "La venta a crédito requiere un cliente asociado"
                    ),
                )
            customer = self._validate_customer(customer_id)
            if not customer.credit_enabled:
                raise AppError(
                    status_code=409,
                    error_code="CREDIT_NOT_ENABLED",
                    message="El cliente no tiene crédito habilitado",
                )
            return customer
        if customer_id is not None:
            return self._validate_customer(customer_id)
        return None

    # ------------------------------------------------------------------
    # Número de venta
    # ------------------------------------------------------------------
    @staticmethod
    def _advisory_lock(db: Session) -> None:
        """Serializa la generación de números en PostgreSQL."""
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(hashtext('sales_number'))"))

    def _next_sale_number(self) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"VTA-{year}-"
        last = self.sales.last_number_for_year(prefix)
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:06d}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create_sale(
        self,
        created_by: UUID,
        customer_id: UUID | None = None,
        payment_method: str = PaymentMethods.CASH,
        amount_paid: Decimal | None = None,
        notes: str | None = None,
        discount: Decimal = Decimal("0"),
        tax: Decimal = Decimal("0"),
        items: list[dict[str, Any]] | None = None,
    ) -> Sale:
        self._resolve_payment_customer(payment_method, customer_id)

        prepared: list[dict[str, Any]] = []
        seen_products: set[UUID] = set()
        for raw in items or []:
            product_id = UUID(str(raw["product_id"]))
            self._validate_product(product_id)
            if product_id in seen_products:
                raise AppError(
                    status_code=409,
                    error_code="SALE_ITEM_DUPLICATE_PRODUCT",
                    message="El producto ya está en la venta",
                )
            seen_products.add(product_id)
            prepared.append(raw)

        for attempt in range(MAX_NUMBER_RETRIES):
            try:
                self._advisory_lock(self.db)
                sale = Sale(
                    customer_id=customer_id,
                    sale_number=self._next_sale_number(),
                    status=SaleStatuses.DRAFT,
                    payment_method=payment_method,
                    amount_paid=money(amount_paid or Decimal("0")),
                    change_due=Decimal("0"),
                    subtotal=Decimal("0"),
                    discount=money(discount),
                    tax=money(tax),
                    total=Decimal("0"),
                    notes=notes,
                    created_by=created_by,
                )
                for raw in prepared:
                    item = self._build_item_from_payload(raw)
                    sale.items.append(item)
                self._recalculate_header(sale)
                self.sales.add(sale)
                self.db.commit()
                self.db.refresh(sale)
                return sale
            except IntegrityError:
                # Colisión de sale_number: revertir y reintentar.
                self.db.rollback()
        raise AppError(
            status_code=409,
            error_code="SALE_NUMBER_GENERATION_FAILED",
            message="No se pudo generar el número de venta, intente nuevamente",
        )

    def _build_item_from_payload(self, raw: dict[str, Any]) -> SaleItem:
        product_id = UUID(str(raw["product_id"]))
        unit_price = raw.get("unit_price")
        if unit_price is None:
            # Snapshot del precio de venta actual del producto.
            product = self.products.get_by_id(product_id)
            assert product is not None  # validado por el llamador
            unit_price = product.sale_price
        return self._fill_item(
            SaleItem(
                product_id=product_id,
                quantity=int(raw["quantity"]),
                unit_price=money(unit_price),
                discount=money(raw.get("discount") or Decimal("0")),
                tax=money(raw.get("tax") or Decimal("0")),
                subtotal=Decimal("0"),
                total=Decimal("0"),
            )
        )

    def get_sale_detail(self, sale_id: UUID) -> Sale:
        return self._get_sale_with_items(sale_id)

    def list_sales(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Sale], int]:
        return self.sales.search(
            customer_id=customer_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            skip=skip,
            limit=limit,
        )

    def update_sale(self, sale_id: UUID, **fields: Any) -> Sale:
        sale = self._get_sale_with_items(sale_id)
        self._ensure_editable(sale)

        if "customer_id" in fields:
            new_customer = fields["customer_id"]
            method = fields.get("payment_method") or sale.payment_method
            effective_customer = (
                UUID(str(new_customer)) if new_customer is not None else None
            )
            self._resolve_payment_customer(method, effective_customer)
            sale.customer_id = effective_customer
        elif "payment_method" in fields and fields["payment_method"] is not None:
            self._resolve_payment_customer(fields["payment_method"], sale.customer_id)

        if "payment_method" in fields and fields["payment_method"] is not None:
            sale.payment_method = fields["payment_method"]
        if "amount_paid" in fields and fields["amount_paid"] is not None:
            sale.amount_paid = money(fields["amount_paid"])
        if "notes" in fields:
            sale.notes = fields["notes"]
        if "discount" in fields and fields["discount"] is not None:
            sale.discount = money(fields["discount"])
        if "tax" in fields and fields["tax"] is not None:
            sale.tax = money(fields["tax"])

        self._recalculate_header(sale)
        self.db.commit()
        self.db.refresh(sale)
        return sale

    def cancel_sale(self, sale_id: UUID) -> Sale:
        sale = self._get_sale(sale_id)
        if sale.status == SaleStatuses.CONFIRMED:
            raise AppError(
                status_code=409,
                error_code="SALE_ALREADY_CONFIRMED",
                message="No se puede cancelar una venta confirmada",
            )
        if sale.status == SaleStatuses.CANCELLED:
            raise AppError(
                status_code=409,
                error_code="SALE_ALREADY_CANCELLED",
                message="La venta ya está cancelada",
            )
        sale.status = SaleStatuses.CANCELLED
        self.db.commit()
        self.db.refresh(sale)
        return sale

    # ------------------------------------------------------------------
    # Ítems (solo en DRAFT)
    # ------------------------------------------------------------------
    def _get_draft_item(self, sale: Sale, item_id: UUID) -> SaleItem:
        for item in sale.items:
            if item.id == item_id:
                return item
        raise AppError(
            status_code=404,
            error_code="SALE_ITEM_NOT_FOUND",
            message="Ítem de venta no encontrado",
        )

    def add_item(
        self,
        sale_id: UUID,
        product_id: UUID,
        quantity: int,
        unit_price: Decimal | None = None,
        discount: Decimal = Decimal("0"),
        tax: Decimal = Decimal("0"),
    ) -> SaleItem:
        sale = self._get_sale_with_items(sale_id)
        self._ensure_editable(sale)
        self._validate_product(product_id)
        if any(item.product_id == product_id for item in sale.items):
            raise AppError(
                status_code=409,
                error_code="SALE_ITEM_DUPLICATE_PRODUCT",
                message="El producto ya está en la venta",
            )

        if unit_price is None:
            product = self.products.get_by_id(product_id)
            assert product is not None
            unit_price = product.sale_price

        item = self._fill_item(
            SaleItem(
                sale_id=sale.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=money(unit_price),
                discount=money(discount),
                tax=money(tax),
                subtotal=Decimal("0"),
                total=Decimal("0"),
            )
        )
        sale.items.append(item)
        self.db.flush()
        self._recalculate_header(sale)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(
        self, sale_id: UUID, item_id: UUID, **fields: Any
    ) -> SaleItem:
        sale = self._get_sale_with_items(sale_id)
        self._ensure_editable(sale)
        item = self._get_draft_item(sale, item_id)

        if fields.get("quantity") is not None:
            item.quantity = int(fields["quantity"])
        if fields.get("unit_price") is not None:
            item.unit_price = money(fields["unit_price"])
        if fields.get("discount") is not None:
            item.discount = money(fields["discount"])
        if fields.get("tax") is not None:
            item.tax = money(fields["tax"])

        self._fill_item(item)
        self._recalculate_header(sale)
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_item(self, sale_id: UUID, item_id: UUID) -> None:
        sale = self._get_sale_with_items(sale_id)
        self._ensure_editable(sale)
        item = self._get_draft_item(sale, item_id)

        sale.items.remove(item)
        self.db.flush()
        self._recalculate_header(sale)
        self.db.commit()

    # ------------------------------------------------------------------
    # Confirmación (transacción única + idempotencia)
    # ------------------------------------------------------------------
    def confirm_sale(self, sale_id: UUID, confirmed_by: UUID) -> Sale:
        try:
            sale = self.sales.get_for_update(sale_id)
            if sale is None:
                raise AppError(
                    status_code=404,
                    error_code="SALE_NOT_FOUND",
                    message="Venta no encontrada",
                )

            if sale.status == SaleStatuses.CONFIRMED:
                raise AppError(
                    status_code=409,
                    error_code="SALE_ALREADY_CONFIRMED",
                    message="La venta ya fue confirmada",
                )
            if sale.status == SaleStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="SALE_CANCELLED",
                    message="La venta está cancelada y no puede confirmarse",
                )
            if not sale.items:
                raise AppError(
                    status_code=422,
                    error_code="SALE_EMPTY",
                    message="La venta no tiene productos",
                )

            for item in sale.items:
                self._validate_product(item.product_id)

            if sale.payment_method == PaymentMethods.CREDIT:
                if sale.customer_id is None:
                    raise AppError(
                        status_code=422,
                        error_code="CUSTOMER_REQUIRED_FOR_CREDIT",
                        message=(
                            "La venta a crédito requiere un cliente asociado"
                        ),
                    )
                receivables = ReceivableService(self.db)

            # Único punto de modificación de stock: InventoryService.
            # apply_exit NO hace commit: todo queda en esta transacción.
            inventory = InventoryService(self.db)
            for item in sale.items:
                inventory.apply_exit(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    created_by=confirmed_by,
                    reason=f"Venta {sale.sale_number}",
                    reference_id=str(sale.id),
                    reference_type=MovementReferences.SALE,
                )

            self._normalize_payment_at_confirm(sale)

            if sale.payment_method == PaymentMethods.CREDIT:
                # Misma transacción: si falla el cupo, el ROLLBACK deshace
                # también las salidas de stock ya aplicadas.
                receivables.create_receivable_in_transaction(
                    customer_id=sale.customer_id,
                    original_amount=sale.total,
                    description=f"Venta {sale.sale_number}",
                    reference_type=MovementReferences.SALE,
                    reference_id=str(sale.id),
                )

            sale.status = SaleStatuses.CONFIRMED
            sale.confirmed_at = datetime.now(timezone.utc)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(sale)
        return sale
