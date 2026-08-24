from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.inventory import InventoryMovement, MovementTypes
from app.models.product import Product
from app.repositories.product_repository import InventoryMovementRepository


class InventoryService:
    """Único punto de modificación de stock del sistema.

    Concurrencia: cada operación bloquea la fila del producto con
    SELECT ... FOR UPDATE hasta el COMMIT, evitando condiciones de carrera
    entre lecturas y escrituras simultáneas (en PostgreSQL). En SQLite el
    hint se ignora y la serialización la resuelve su lock global de escritura.
    Además, un CHECK constraint (stock >= 0) protege a nivel de base de datos.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.movements = InventoryMovementRepository(db)

    def _lock_product(self, product_id: UUID) -> Product:
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .with_for_update()
        )
        product = self.db.scalars(stmt).first()
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

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise AppError(
                status_code=422,
                error_code="INVALID_QUANTITY",
                message="La cantidad debe ser mayor que cero",
            )

    def _register_movement(
        self,
        product: Product,
        movement_type: str,
        quantity: int,
        previous_stock: int,
        new_stock: int,
        reason: str | None,
        reference_id: str | None,
        created_by: UUID,
        reference_type: str | None = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            product_id=product.id,
            movement_type=movement_type,
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
            created_by=created_by,
        )
        self.db.add(movement)
        return movement

    def _commit_and_refresh(
        self, product: Product, movement: InventoryMovement
    ) -> InventoryMovement:
        self.db.commit()
        self.db.refresh(movement)
        self.db.refresh(product)
        return movement

    def apply_entry(
        self,
        product_id: UUID,
        quantity: int,
        created_by: UUID,
        reason: str | None = None,
        reference_id: str | None = None,
        reference_type: str | None = None,
    ) -> InventoryMovement:
        """Núcleo de entrada de stock SIN hacer commit.

        Participa en la transacción del llamador (p. ej. confirmación de
        compras), garantizando atomicidad entre stock y movimientos.
        Bloquea la fila del producto hasta el COMMIT del llamador.
        """
        self._validate_quantity(quantity)
        product = self._lock_product(product_id)

        previous_stock = product.stock
        product.stock = previous_stock + quantity
        return self._register_movement(
            product,
            MovementTypes.ENTRY,
            quantity,
            previous_stock,
            product.stock,
            reason,
            reference_id,
            created_by,
            reference_type=reference_type,
        )

    def add_stock(
        self,
        product_id: UUID,
        quantity: int,
        created_by: UUID,
        reason: str | None = None,
        reference_id: str | None = None,
    ) -> InventoryMovement:
        movement = self.apply_entry(
            product_id=product_id,
            quantity=quantity,
            created_by=created_by,
            reason=reason,
            reference_id=reference_id,
        )
        product = self.db.get(Product, product_id)
        assert product is not None
        self._commit_and_refresh(product, movement)
        return movement

    def apply_exit(
        self,
        product_id: UUID,
        quantity: int,
        created_by: UUID,
        reason: str | None = None,
        reference_id: str | None = None,
        reference_type: str | None = None,
    ) -> InventoryMovement:
        """Núcleo de salida de stock SIN hacer commit.

        Participa en la transacción del llamador (p. ej. confirmación de
        ventas), garantizando atomicidad entre stock y movimientos. Si el
        stock resulta insuficiente se lanza 409 y el llamador debe hacer
        rollback para deshacer las salidas ya aplicadas.
        Bloquea la fila del producto hasta el COMMIT del llamador.
        """
        self._validate_quantity(quantity)
        product = self._lock_product(product_id)

        if quantity > product.stock:
            raise AppError(
                status_code=409,
                error_code="INSUFFICIENT_STOCK",
                message=(
                    f"Stock insuficiente: solicitado {quantity}, "
                    f"disponible {product.stock}"
                ),
            )

        previous_stock = product.stock
        product.stock = previous_stock - quantity
        return self._register_movement(
            product,
            MovementTypes.EXIT,
            quantity,
            previous_stock,
            product.stock,
            reason,
            reference_id,
            created_by,
            reference_type=reference_type,
        )

    def remove_stock(
        self,
        product_id: UUID,
        quantity: int,
        created_by: UUID,
        reason: str | None = None,
        reference_id: str | None = None,
    ) -> InventoryMovement:
        movement = self.apply_exit(
            product_id=product_id,
            quantity=quantity,
            created_by=created_by,
            reason=reason,
            reference_id=reference_id,
        )
        product = self.db.get(Product, product_id)
        assert product is not None
        return self._commit_and_refresh(product, movement)

    def adjust_stock(
        self,
        product_id: UUID,
        new_stock: int,
        reason: str,
        created_by: UUID,
        reference_id: str | None = None,
    ) -> InventoryMovement:
        if new_stock < 0:
            raise AppError(
                status_code=422,
                error_code="INVALID_QUANTITY",
                message="El stock final no puede ser negativo",
            )
        product = self._lock_product(product_id)

        difference = new_stock - product.stock
        if difference == 0:
            raise AppError(
                status_code=422,
                error_code="ADJUSTMENT_WITHOUT_CHANGE",
                message="El stock final es igual al stock actual",
            )

        previous_stock = product.stock
        product.stock = new_stock
        movement = self._register_movement(
            product,
            MovementTypes.ADJUSTMENT,
            abs(difference),
            previous_stock,
            new_stock,
            reason,
            reference_id,
            created_by,
        )
        return self._commit_and_refresh(product, movement)

    def return_stock(
        self,
        product_id: UUID,
        quantity: int,
        created_by: UUID,
        reason: str | None = None,
        reference_id: str | None = None,
    ) -> InventoryMovement:
        self._validate_quantity(quantity)
        product = self._lock_product(product_id)

        previous_stock = product.stock
        product.stock = previous_stock + quantity
        movement = self._register_movement(
            product,
            MovementTypes.RETURN,
            quantity,
            previous_stock,
            product.stock,
            reason,
            reference_id,
            created_by,
        )
        return self._commit_and_refresh(product, movement)

    def get_movement(self, movement_id: UUID) -> InventoryMovement:
        movement = self.movements.get_by_id(movement_id)
        if movement is None:
            raise AppError(
                status_code=404,
                error_code="MOVEMENT_NOT_FOUND",
                message="Movimiento no encontrado",
            )
        return movement

    def list_movements(
        self,
        product_id: UUID | None = None,
        movement_type: str | None = None,
        created_by: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[InventoryMovement], int]:
        return self.movements.search(
            product_id=product_id,
            movement_type=movement_type,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
