"""Acceso a datos para reportes (Fase 9).

Solo consultas de lectura con agregados en BD (GROUP BY / SUM) y JOINs
precargados: sin N+1 y sin duplicar lógica de negocio. Cada reporte
expone ``*_rows`` (datos paginables; ``limit=None`` exporta todo) y
``*_totals`` (agregados sobre TODO el conjunto filtrado).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, func, select
from sqlalchemy.orm import Session

from app.models.cash import CashRegister
from app.models.category import Category
from app.models.customer import (
    Customer,
    ReceivableAccount,
    ReceivableAccountStatuses,
)
from app.models.product import Product
from app.models.purchase import Purchase
from app.models.sale import Sale, SaleItem, SaleStatuses
from app.models.supplier import Supplier
from app.models.user import User

_OPEN_RECEIVABLE_STATUSES = (
    ReceivableAccountStatuses.OPEN,
    ReceivableAccountStatuses.PARTIALLY_PAID,
)


def _effective_sale_date():
    """Fecha de negocio de una venta (confirmación; fallback creación)."""
    return func.coalesce(Sale.confirmed_at, Sale.created_at)


class ReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Ventas
    # ------------------------------------------------------------------
    def _sales_conditions(
        self,
        user_id: UUID | None,
        payment_method: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        conditions: list[Any] = [Sale.status == SaleStatuses.CONFIRMED]
        if user_id is not None:
            conditions.append(Sale.created_by == user_id)
        if payment_method is not None:
            conditions.append(Sale.payment_method == payment_method)
        effective_date = _effective_sale_date()
        if date_from is not None:
            conditions.append(effective_date >= date_from)
        if date_to is not None:
            conditions.append(effective_date <= date_to)
        return conditions

    def sales_rows(
        self,
        user_id: UUID | None = None,
        payment_method: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._sales_conditions(
            user_id, payment_method, date_from, date_to
        )
        base = (
            select(
                Sale.sale_number,
                _effective_sale_date().label("sale_date"),
                User.username.label("seller"),
                Customer.name.label("customer_name"),
                Sale.payment_method,
                Sale.subtotal,
                Sale.discount,
                Sale.tax,
                Sale.total,
            )
            .join(User, Sale.created_by == User.id)
            .outerjoin(Customer, Sale.customer_id == Customer.id)
            .where(*conditions)
        )
        total = int(
            self.db.scalar(
                select(func.count())
                .select_from(Sale)
                .where(*conditions)
            )
            or 0
        )
        stmt = base.order_by(_effective_sale_date().desc(), Sale.sale_number)
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def sales_totals(
        self,
        user_id: UUID | None = None,
        payment_method: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = self._sales_conditions(
            user_id, payment_method, date_from, date_to
        )
        return self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(Sale.subtotal), 0),
                func.coalesce(func.sum(Sale.discount), 0),
                func.coalesce(func.sum(Sale.tax), 0),
                func.coalesce(func.sum(Sale.total), 0),
            )
            .select_from(Sale)
            .where(*conditions),
            ("count", "subtotal_sum", "discount_sum", "tax_sum", "total_sum"),
        )

    # ------------------------------------------------------------------
    # Productos vendidos (agregado por producto)
    # ------------------------------------------------------------------
    def _products_sold_conditions(
        self,
        category_id: UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        conditions = [
            Sale.status == SaleStatuses.CONFIRMED,
        ]
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        effective_date = _effective_sale_date()
        if date_from is not None:
            conditions.append(effective_date >= date_from)
        if date_to is not None:
            conditions.append(effective_date <= date_to)
        return conditions

    def products_sold_rows(
        self,
        category_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._products_sold_conditions(
            category_id, date_from, date_to
        )
        base_stmt = (
            select(
                Product.name.label("product_name"),
                Category.name.label("category_name"),
                func.sum(SaleItem.quantity).label("quantity_sold"),
                func.count(func.distinct(Sale.id)).label("sales_count"),
                func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .where(*conditions)
            .group_by(Product.id, Product.name, Category.name)
        )

        count_stmt = (
            select(func.count(func.distinct(SaleItem.product_id)))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(*conditions)
        )
        total = int(self.db.scalar(count_stmt) or 0)

        stmt = base_stmt.order_by(func.sum(SaleItem.quantity).desc())
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def products_sold_totals(
        self,
        category_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = self._products_sold_conditions(
            category_id, date_from, date_to
        )
        return self._one_aggregate(
            select(
                func.coalesce(func.sum(SaleItem.quantity), 0),
                func.coalesce(func.sum(SaleItem.total), 0),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(*conditions),
            ("units_sold", "revenue_sum"),
        )

    # ------------------------------------------------------------------
    # Inventario / Stock bajo
    # ------------------------------------------------------------------
    def inventory_rows(
        self,
        category_id: UUID | None = None,
        state: str | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._inventory_conditions(category_id, state)
        base_stmt = (
            select(
                Product.name.label("product_name"),
                Product.barcode,
                Category.name.label("category_name"),
                Supplier.name.label("supplier_name"),
                Product.stock,
                Product.minimum_stock,
                Product.purchase_price,
                Product.sale_price,
            )
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Supplier, Product.supplier_id == Supplier.id)
            .where(*conditions)
        )
        total = self._count(Product, conditions)
        stmt = base_stmt.order_by(Category.name, Product.name)
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def inventory_totals(
        self,
        category_id: UUID | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        conditions = self._inventory_conditions(category_id, state)
        result = self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(Product.stock), 0),
                func.coalesce(
                    func.sum(Product.stock * Product.purchase_price), 0
                ),
                func.coalesce(
                    func.sum(Product.stock * Product.sale_price), 0
                ),
            ).where(*conditions),
            (
                "products_count",
                "total_units",
                "total_value_cost",
                "total_value_sale",
            ),
        )
        # El COUNT anterior es sobre el JOIN con categorías; recalcular
        # sobre la tabla base evita dobles conteos por joins 1:N.
        result["products_count"] = self._count(Product, conditions)
        return result

    def _inventory_conditions(
        self, category_id: UUID | None, state: str | None
    ) -> list[Any]:
        conditions: list[Any] = []
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        if state == "active":
            conditions.append(Product.is_active.is_(True))
        elif state == "inactive":
            conditions.append(Product.is_active.is_(False))
        return conditions

    def low_stock_rows(
        self,
        category_id: UUID | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = [
            Product.is_active.is_(True),
            Product.stock <= Product.minimum_stock,
        ]
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        base_stmt = (
            select(
                Product.name.label("product_name"),
                Category.name.label("category_name"),
                Supplier.name.label("supplier_name"),
                Product.stock,
                Product.minimum_stock,
                (Product.minimum_stock - Product.stock).label("shortage"),
            )
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Supplier, Product.supplier_id == Supplier.id)
            .where(*conditions)
        )
        total = self._count(Product, conditions)
        stmt = base_stmt.order_by(
            (Product.minimum_stock - Product.stock).desc(),
            Product.name,
        )
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def low_stock_totals(
        self, category_id: UUID | None = None
    ) -> dict[str, Any]:
        conditions = [
            Product.is_active.is_(True),
            Product.stock <= Product.minimum_stock,
        ]
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        return self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(Product.minimum_stock - Product.stock), 0),
            ).where(*conditions),
            ("products_count", "total_shortage"),
        )

    # ------------------------------------------------------------------
    # Compras
    # ------------------------------------------------------------------
    def _purchases_conditions(
        self,
        supplier_id: UUID | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        conditions: list[Any] = []
        if supplier_id is not None:
            conditions.append(Purchase.supplier_id == supplier_id)
        if status is not None:
            conditions.append(Purchase.status == status)
        if date_from is not None:
            conditions.append(Purchase.created_at >= date_from)
        if date_to is not None:
            conditions.append(Purchase.created_at <= date_to)
        return conditions

    def purchases_rows(
        self,
        supplier_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._purchases_conditions(
            supplier_id, status, date_from, date_to
        )
        base_stmt = (
            select(
                Purchase.purchase_number,
                Purchase.created_at.label("purchase_date"),
                Supplier.name.label("supplier_name"),
                Purchase.status,
                Purchase.subtotal,
                Purchase.discount,
                Purchase.tax,
                Purchase.total,
            )
            .join(Supplier, Purchase.supplier_id == Supplier.id)
            .where(*conditions)
        )
        total = self._count(Purchase, conditions)
        stmt = base_stmt.order_by(Purchase.created_at.desc(), Purchase.purchase_number)
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def purchases_totals(
        self,
        supplier_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = self._purchases_conditions(
            supplier_id, status, date_from, date_to
        )
        return self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(Purchase.total), 0),
            )
            .select_from(Purchase)
            .where(*conditions),
            ("count", "total_sum"),
        )

    # ------------------------------------------------------------------
    # Caja (turnos)
    # ------------------------------------------------------------------
    def _cash_conditions(
        self,
        user_id: UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        conditions: list[Any] = []
        if user_id is not None:
            conditions.append(CashRegister.user_id == user_id)
        if date_from is not None:
            conditions.append(CashRegister.opened_at >= date_from)
        if date_to is not None:
            conditions.append(CashRegister.opened_at <= date_to)
        return conditions

    def cash_registers_rows(
        self,
        user_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._cash_conditions(user_id, date_from, date_to)
        base_stmt = (
            select(
                User.username.label("cashier"),
                CashRegister.status,
                CashRegister.opened_at,
                CashRegister.closed_at,
                CashRegister.opening_amount,
                CashRegister.expected_amount,
                CashRegister.counted_amount,
                CashRegister.difference,
            )
            .join(User, CashRegister.user_id == User.id)
            .where(*conditions)
        )
        total = self._count(CashRegister, conditions)
        stmt = base_stmt.order_by(CashRegister.opened_at.desc())
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def cash_registers_totals(
        self,
        user_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = self._cash_conditions(user_id, date_from, date_to)
        closed = case((CashRegister.status == "CLOSED", 1), else_=0)
        return self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(closed), 0),
                func.coalesce(func.sum(CashRegister.opening_amount), 0),
                func.coalesce(func.sum(CashRegister.expected_amount), 0),
                func.coalesce(func.sum(CashRegister.counted_amount), 0),
                func.coalesce(func.sum(CashRegister.difference), 0),
            )
            .select_from(CashRegister)
            .where(*conditions),
            (
                "registers_count",
                "closed_count",
                "opening_sum",
                "expected_sum",
                "counted_sum",
                "difference_sum",
            ),
        )

    # ------------------------------------------------------------------
    # Clientes: cartera de crédito
    # ------------------------------------------------------------------
    def customers_credit_rows(
        self,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = [Customer.credit_enabled.is_(True)]
        if q:
            pattern = f"%{q.strip()}%"
            conditions.append(
                Customer.name.ilike(pattern)
                | Customer.identification.ilike(pattern)
            )
        if date_from is not None:
            conditions.append(Customer.created_at >= date_from)
        if date_to is not None:
            conditions.append(Customer.created_at <= date_to)

        open_balance = func.coalesce(
            func.sum(
                case(
                    (
                        ReceivableAccount.status.in_(_OPEN_RECEIVABLE_STATUSES),
                        ReceivableAccount.balance,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        open_count = func.coalesce(
            func.sum(
                case(
                    (
                        ReceivableAccount.status.in_(_OPEN_RECEIVABLE_STATUSES),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        base_stmt = (
            select(
                Customer.name.label("customer_name"),
                Customer.identification,
                Customer.is_active,
                Customer.credit_limit,
                Customer.current_balance,
                open_balance.label("receivable_balance"),
                open_count.label("open_accounts"),
            )
            .outerjoin(
                ReceivableAccount,
                ReceivableAccount.customer_id == Customer.id,
            )
            .where(*conditions)
            .group_by(Customer.id)
        )
        count_stmt = (
            select(func.count())
            .select_from(Customer)
            .where(*conditions)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = base_stmt.order_by(open_balance.desc(), Customer.name)
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).unique().all(), total

    def customers_credit_totals(
        self,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = [Customer.credit_enabled.is_(True)]
        if q:
            pattern = f"%{q.strip()}%"
            conditions.append(
                Customer.name.ilike(pattern)
                | Customer.identification.ilike(pattern)
            )
        if date_from is not None:
            conditions.append(Customer.created_at >= date_from)
        if date_to is not None:
            conditions.append(Customer.created_at <= date_to)
        totals = self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(Customer.credit_limit), 0),
                func.coalesce(func.sum(Customer.current_balance), 0),
            )
            .select_from(Customer)
            .where(*conditions),
            ("customers_count", "credit_limit_sum", "balance_sum"),
        )
        # Saldo vigente en cuentas por cobrar de la cartera filtrada
        # (mismas condiciones sobre clientes, agregado sobre las cuentas).
        open_balance_total = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ReceivableAccount.status.in_(
                                    _OPEN_RECEIVABLE_STATUSES
                                ),
                                ReceivableAccount.balance,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                )
            )
            .select_from(Customer)
            .outerjoin(
                ReceivableAccount,
                ReceivableAccount.customer_id == Customer.id,
            )
            .where(*conditions)
        )
        totals["receivable_balance_sum"] = open_balance_total or 0
        return totals

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------
    def _receivables_conditions(
        self,
        customer_id: UUID | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        conditions: list[Any] = []
        if customer_id is not None:
            conditions.append(ReceivableAccount.customer_id == customer_id)
        if status is not None:
            conditions.append(ReceivableAccount.status == status)
        if date_from is not None:
            conditions.append(ReceivableAccount.created_at >= date_from)
        if date_to is not None:
            conditions.append(ReceivableAccount.created_at <= date_to)
        return conditions

    def receivables_rows(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int | None = 0,
        limit: int | None = 50,
    ) -> tuple[list[Any], int]:
        conditions = self._receivables_conditions(
            customer_id, status, date_from, date_to
        )
        base_stmt = (
            select(
                Customer.name.label("customer_name"),
                ReceivableAccount.reference_type,
                ReceivableAccount.description,
                ReceivableAccount.original_amount,
                ReceivableAccount.paid_amount,
                ReceivableAccount.balance,
                ReceivableAccount.due_date,
                ReceivableAccount.status,
                ReceivableAccount.created_at,
            )
            .join(Customer, ReceivableAccount.customer_id == Customer.id)
            .where(*conditions)
        )
        total = self._count(ReceivableAccount, conditions)
        stmt = base_stmt.order_by(
            ReceivableAccount.created_at.desc()
        )
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all(), total

    def receivables_totals(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        conditions = self._receivables_conditions(
            customer_id, status, date_from, date_to
        )
        return self._one_aggregate(
            select(
                func.count(),
                func.coalesce(func.sum(ReceivableAccount.original_amount), 0),
                func.coalesce(func.sum(ReceivableAccount.paid_amount), 0),
                func.coalesce(func.sum(ReceivableAccount.balance), 0),
            )
            .select_from(ReceivableAccount)
            .where(*conditions),
            ("count", "original_sum", "paid_sum", "balance_sum"),
        )

    # ------------------------------------------------------------------
    # Utilidades (aproximadas con costo actual del producto)
    # ------------------------------------------------------------------
    @staticmethod
    def _period_expression(period: str):
        text_date = func.cast(_effective_sale_date(), String)
        length = 10 if period == "DAY" else 7
        return func.substr(text_date, 1, length)

    def utilities_revenue_by_period(
        self,
        period: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Ventas confirmadas agrupadas por período (DAY o MONTH)."""
        conditions = self._utilities_conditions(date_from, date_to)
        period_expr = self._period_expression(period)
        stmt = (
            select(
                period_expr.label("period"),
                func.count().label("sales_count"),
                func.coalesce(func.sum(Sale.total), 0).label("revenue"),
            )
            .select_from(Sale)
            .where(*conditions)
            .group_by(period_expr)
        )
        return {
            row.period: {"period": row.period, "sales_count": int(row.sales_count), "revenue": row.revenue}
            for row in self.db.execute(stmt).all()
        }

    def utilities_cost_by_period(
        self,
        period: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Costo estimado por período: cantidad vendida × precio de compra
        ACTUAL del producto (los ítems de venta no guardan snapshot del
        costo; aproximación documentada en ARCHITECTURE.md §21.7)."""
        conditions = self._utilities_conditions(date_from, date_to)
        period_expr = self._period_expression(period)
        stmt = (
            select(
                period_expr.label("period"),
                func.coalesce(
                    func.sum(SaleItem.quantity * Product.purchase_price), 0
                ).label("cost"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(*conditions)
            .group_by(period_expr)
        )
        return {
            row.period: {"period": row.period, "cost": row.cost}
            for row in self.db.execute(stmt).all()
        }

    def _utilities_conditions(
        self, date_from: datetime | None, date_to: datetime | None
    ) -> list[Any]:
        conditions = [Sale.status == SaleStatuses.CONFIRMED]
        effective_date = _effective_sale_date()
        if date_from is not None:
            conditions.append(effective_date >= date_from)
        if date_to is not None:
            conditions.append(effective_date <= date_to)
        return conditions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _count(self, model, conditions: list[Any]) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(model).where(*conditions)
            )
            or 0
        )

    def _one_aggregate(self, stmt, keys: tuple[str, ...]) -> dict[str, Any]:
        raw = self.db.execute(stmt).one()
        return dict(zip(keys, raw))
