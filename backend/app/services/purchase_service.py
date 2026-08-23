from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.purchase import (
    MovementReferences,
    Purchase,
    PurchaseItem,
    PurchaseStatuses,
)
from app.models.supplier import Supplier
from app.repositories.product_repository import ProductRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.inventory_service import InventoryService

MONEY_QUANTUM = Decimal("0.01")
MAX_NUMBER_RETRIES = 5


def money(value: Any) -> Decimal:
    """Normaliza un monto a Decimal con escala 2 y redondeo comercial."""
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class PurchaseService:
    """Lógica de negocio de compras y abastecimiento.

    La confirmación es transaccional: valida compra/proveedor/productos,
    registra entradas vía InventoryService (sin commits intermedios),
    marca la compra como CONFIRMED y hace un único COMMIT. Ante cualquier
    error ejecuta ROLLBACK completo (sin stock ni movimientos parciales).
    Es idempotente: solo una compra DRAFT puede confirmarse, y el bloqueo
    de fila (SELECT ... FOR UPDATE) evita dobles confirmaciones concurrentes.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.purchases = PurchaseRepository(db)
        self.products = ProductRepository(db)
        self.suppliers = SupplierRepository(db)

    # ------------------------------------------------------------------
    # Validaciones compartidas
    # ------------------------------------------------------------------
    def _get_purchase(self, purchase_id: UUID) -> Purchase:
        purchase = self.purchases.get_by_id(purchase_id)
        if purchase is None:
            raise AppError(
                status_code=404,
                error_code="PURCHASE_NOT_FOUND",
                message="Compra no encontrada",
            )
        return purchase

    def _get_purchase_with_items(self, purchase_id: UUID) -> Purchase:
        purchase = self.purchases.get_with_items(purchase_id)
        if purchase is None:
            raise AppError(
                status_code=404,
                error_code="PURCHASE_NOT_FOUND",
                message="Compra no encontrada",
            )
        return purchase

    @staticmethod
    def _ensure_editable(purchase: Purchase) -> None:
        if purchase.status == PurchaseStatuses.CONFIRMED:
            raise AppError(
                status_code=409,
                error_code="PURCHASE_ALREADY_CONFIRMED",
                message="La compra ya está confirmada y no puede modificarse",
            )
        if purchase.status == PurchaseStatuses.CANCELLED:
            raise AppError(
                status_code=409,
                error_code="PURCHASE_CANCELLED",
                message="La compra está cancelada y no puede modificarse",
            )

    def _validate_supplier(self, supplier_id: UUID) -> Supplier:
        supplier = self.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise AppError(
                status_code=404,
                error_code="SUPPLIER_NOT_FOUND",
                message="Proveedor no encontrado",
            )
        if not supplier.is_active:
            raise AppError(
                status_code=409,
                error_code="SUPPLIER_INACTIVE",
                message="El proveedor está inactivo",
            )
        return supplier

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
        quantity: int, unit_cost: Decimal, discount: Decimal, tax: Decimal
    ) -> tuple[Decimal, Decimal]:
        unit_cost = money(unit_cost)
        discount = money(discount)
        tax = money(tax)
        subtotal = money(Decimal(quantity) * unit_cost)
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
    def _fill_item(item: PurchaseItem) -> PurchaseItem:
        item.unit_cost = money(item.unit_cost)
        item.discount = money(item.discount)
        item.tax = money(item.tax)
        item.subtotal, item.total = PurchaseService._compute_item_totals(
            item.quantity, item.unit_cost, item.discount, item.tax
        )
        return item

    def _recalculate_header(self, purchase: Purchase) -> None:
        subtotal = money(
            sum((item.subtotal for item in purchase.items), Decimal("0"))
        )
        discount = money(purchase.discount)
        tax = money(purchase.tax)
        if discount > subtotal:
            raise AppError(
                status_code=422,
                error_code="DISCOUNT_EXCEEDS_SUBTOTAL",
                message=(
                    f"El descuento ({discount}) excede el subtotal "
                    f"({subtotal})"
                ),
            )
        purchase.subtotal = subtotal
        purchase.total = money(subtotal - discount + tax)

    # ------------------------------------------------------------------
    # Número de compra
    # ------------------------------------------------------------------
    @staticmethod
    def _advisory_lock(db: Session) -> None:
        """Serializa la generación de números en PostgreSQL."""
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('purchases_number'))")
            )

    def _next_purchase_number(self) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"COMP-{year}-"
        last = self.purchases.last_number_for_year(prefix)
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:06d}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create_purchase(
        self,
        supplier_id: UUID,
        created_by: UUID,
        notes: str | None = None,
        discount: Decimal = Decimal("0"),
        tax: Decimal = Decimal("0"),
        items: list[dict[str, Any]] | None = None,
    ) -> Purchase:
        self._validate_supplier(supplier_id)

        prepared: list[dict[str, Any]] = []
        seen_products: set[UUID] = set()
        for raw in items or []:
            product_id = UUID(str(raw["product_id"]))
            self._validate_product(product_id)
            if product_id in seen_products:
                raise AppError(
                    status_code=409,
                    error_code="PURCHASE_ITEM_DUPLICATE_PRODUCT",
                    message="El producto ya está en la compra",
                )
            seen_products.add(product_id)
            prepared.append(raw)

        for attempt in range(MAX_NUMBER_RETRIES):
            try:
                self._advisory_lock(self.db)
                purchase = Purchase(
                    supplier_id=supplier_id,
                    purchase_number=self._next_purchase_number(),
                    status=PurchaseStatuses.DRAFT,
                    subtotal=Decimal("0"),
                    discount=money(discount),
                    tax=money(tax),
                    total=Decimal("0"),
                    notes=notes,
                    created_by=created_by,
                )
                for raw in prepared:
                    item = PurchaseItem(
                        product_id=UUID(str(raw["product_id"])),
                        quantity=int(raw["quantity"]),
                        unit_cost=money(raw["unit_cost"]),
                        discount=money(raw.get("discount") or Decimal("0")),
                        tax=money(raw.get("tax") or Decimal("0")),
                        subtotal=Decimal("0"),
                        total=Decimal("0"),
                    )
                    self._fill_item(item)
                    purchase.items.append(item)
                self._recalculate_header(purchase)
                self.purchases.add(purchase)
                self.db.commit()
                self.db.refresh(purchase)
                return purchase
            except IntegrityError:
                # Colisión de purchase_number: revertir y reintentar.
                self.db.rollback()
        raise AppError(
            status_code=409,
            error_code="PURCHASE_NUMBER_GENERATION_FAILED",
            message="No se pudo generar el número de compra, intente nuevamente",
        )

    def get_purchase_detail(self, purchase_id: UUID) -> Purchase:
        return self._get_purchase_with_items(purchase_id)

    def list_purchases(
        self,
        supplier_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        return self.purchases.search(
            supplier_id=supplier_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            skip=skip,
            limit=limit,
        )

    def update_purchase(self, purchase_id: UUID, **fields: Any) -> Purchase:
        purchase = self._get_purchase_with_items(purchase_id)
        self._ensure_editable(purchase)

        if "supplier_id" in fields and fields["supplier_id"] is not None:
            supplier_id = UUID(str(fields["supplier_id"]))
            self._validate_supplier(supplier_id)
            purchase.supplier_id = supplier_id

        if "notes" in fields:
            purchase.notes = fields["notes"]

        if "discount" in fields and fields["discount"] is not None:
            purchase.discount = money(fields["discount"])
        if "tax" in fields and fields["tax"] is not None:
            purchase.tax = money(fields["tax"])

        self._recalculate_header(purchase)
        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    def cancel_purchase(self, purchase_id: UUID) -> Purchase:
        purchase = self._get_purchase(purchase_id)
        if purchase.status == PurchaseStatuses.CONFIRMED:
            raise AppError(
                status_code=409,
                error_code="PURCHASE_ALREADY_CONFIRMED",
                message="No se puede cancelar una compra confirmada",
            )
        if purchase.status == PurchaseStatuses.CANCELLED:
            raise AppError(
                status_code=409,
                error_code="PURCHASE_ALREADY_CANCELLED",
                message="La compra ya está cancelada",
            )
        purchase.status = PurchaseStatuses.CANCELLED
        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    # ------------------------------------------------------------------
    # Ítems (solo en DRAFT)
    # ------------------------------------------------------------------
    def _get_draft_item(self, purchase: Purchase, item_id: UUID) -> PurchaseItem:
        for item in purchase.items:
            if item.id == item_id:
                return item
        raise AppError(
            status_code=404,
            error_code="PURCHASE_ITEM_NOT_FOUND",
            message="Ítem de compra no encontrado",
        )

    def add_item(
        self,
        purchase_id: UUID,
        product_id: UUID,
        quantity: int,
        unit_cost: Decimal,
        discount: Decimal = Decimal("0"),
        tax: Decimal = Decimal("0"),
    ) -> PurchaseItem:
        purchase = self._get_purchase_with_items(purchase_id)
        self._ensure_editable(purchase)
        self._validate_product(product_id)
        if any(item.product_id == product_id for item in purchase.items):
            raise AppError(
                status_code=409,
                error_code="PURCHASE_ITEM_DUPLICATE_PRODUCT",
                message="El producto ya está en la compra",
            )

        item = self._fill_item(
            PurchaseItem(
                purchase_id=purchase.id,
                product_id=product_id,
                quantity=quantity,
                unit_cost=money(unit_cost),
                discount=money(discount),
                tax=money(tax),
                subtotal=Decimal("0"),
                total=Decimal("0"),
            )
        )
        purchase.items.append(item)
        self.db.flush()
        self._recalculate_header(purchase)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(
        self, purchase_id: UUID, item_id: UUID, **fields: Any
    ) -> PurchaseItem:
        purchase = self._get_purchase_with_items(purchase_id)
        self._ensure_editable(purchase)
        item = self._get_draft_item(purchase, item_id)

        if fields.get("quantity") is not None:
            item.quantity = int(fields["quantity"])
        if fields.get("unit_cost") is not None:
            item.unit_cost = money(fields["unit_cost"])
        if fields.get("discount") is not None:
            item.discount = money(fields["discount"])
        if fields.get("tax") is not None:
            item.tax = money(fields["tax"])

        self._fill_item(item)
        self._recalculate_header(purchase)
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_item(self, purchase_id: UUID, item_id: UUID) -> None:
        purchase = self._get_purchase_with_items(purchase_id)
        self._ensure_editable(purchase)
        item = self._get_draft_item(purchase, item_id)

        purchase.items.remove(item)
        self.db.flush()
        self._recalculate_header(purchase)
        self.db.commit()

    # ------------------------------------------------------------------
    # Confirmación (transacción única + idempotencia)
    # ------------------------------------------------------------------
    def confirm_purchase(self, purchase_id: UUID, confirmed_by: UUID) -> Purchase:
        try:
            purchase = self.purchases.get_for_update(purchase_id)
            if purchase is None:
                raise AppError(
                    status_code=404,
                    error_code="PURCHASE_NOT_FOUND",
                    message="Compra no encontrada",
                )

            if purchase.status == PurchaseStatuses.CONFIRMED:
                raise AppError(
                    status_code=409,
                    error_code="PURCHASE_ALREADY_CONFIRMED",
                    message="La compra ya fue confirmada",
                )
            if purchase.status == PurchaseStatuses.CANCELLED:
                raise AppError(
                    status_code=409,
                    error_code="PURCHASE_CANCELLED",
                    message="La compra está cancelada y no puede confirmarse",
                )
            if not purchase.items:
                raise AppError(
                    status_code=422,
                    error_code="PURCHASE_EMPTY",
                    message="La compra no tiene productos",
                )

            self._validate_supplier(purchase.supplier_id)
            for item in purchase.items:
                self._validate_product(item.product_id)

            # Único punto de modificación de stock: InventoryService.
            # apply_entry NO hace commit: todo queda en esta transacción.
            inventory = InventoryService(self.db)
            for item in purchase.items:
                inventory.apply_entry(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    created_by=confirmed_by,
                    reason=f"Compra {purchase.purchase_number}",
                    reference_id=str(purchase.id),
                    reference_type=MovementReferences.PURCHASE,
                )

            purchase.status = PurchaseStatuses.CONFIRMED
            purchase.confirmed_at = datetime.now(timezone.utc)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(purchase)
        return purchase
