"""Módulo de recopilación de datos reales para IA (Fase 10).

Consulta los repositorios existentes y serializa datos relevantes del
negocio como contexto para los prompts de OpenAI.  **Solo lectura**:
nunca modifica datos del sistema.

Cada función devuelve un diccionario serializable listo para inyectarse
en los prompts del módulo de IA.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.cash import CashRegister, RegisterStatuses
from app.models.category import Category
from app.models.customer import Customer, ReceivableAccount, ReceivableAccountStatuses
from app.models.inventory import InventoryMovement
from app.models.product import Product
from app.models.purchase import Purchase, PurchaseStatuses
from app.models.sale import Sale, SaleItem, SaleStatuses
from app.models.supplier import Supplier


_OPEN_RECEIVABLE = (
    ReceivableAccountStatuses.OPEN,
    ReceivableAccountStatuses.PARTIALLY_PAID,
)


def _money(v: Any) -> str:
    if v is None:
        return "0.00"
    return str(Decimal(str(v)).quantize(Decimal("0.01")))


class DataGatherer:
    """Recopilador de datos reales del sistema para consumo de IA."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Ventas
    # ------------------------------------------------------------------
    def sales_summary(self, days: int = 30) -> dict[str, Any]:
        cutoff = datetime.now() - timedelta(days=days)
        effective_date = func.coalesce(Sale.confirmed_at, Sale.created_at)

        totals = self.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Sale.total), 0),
                func.coalesce(func.sum(Sale.tax), 0),
                func.coalesce(func.sum(Sale.discount), 0),
            )
            .select_from(Sale)
            .where(
                Sale.status == SaleStatuses.CONFIRMED,
                effective_date >= cutoff,
            )
        ).one()

        by_method = self.db.execute(
            select(
                Sale.payment_method,
                func.count(),
                func.coalesce(func.sum(Sale.total), 0),
            )
            .where(
                Sale.status == SaleStatuses.CONFIRMED,
                effective_date >= cutoff,
            )
            .group_by(Sale.payment_method)
        ).all()

        top_products = self.db.execute(
            select(
                Product.name.label("product"),
                func.sum(SaleItem.quantity).label("qty"),
                func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(
                Sale.status == SaleStatuses.CONFIRMED,
                effective_date >= cutoff,
            )
            .group_by(Product.id, Product.name)
            .order_by(func.sum(SaleItem.quantity).desc())
            .limit(10)
        ).all()

        return {
            "period_days": days,
            "total_sales": int(totals[0]),
            "total_revenue": _money(totals[1]),
            "total_tax": _money(totals[2]),
            "total_discount": _money(totals[3]),
            "by_payment_method": [
                {"method": m, "count": int(c), "total": _money(t)}
                for m, c, t in by_method
            ],
            "top_products": [
                {"name": p, "qty": int(q), "revenue": _money(r)}
                for p, q, r in top_products
            ],
        }

    # ------------------------------------------------------------------
    # Inventario
    # ------------------------------------------------------------------
    def inventory_snapshot(self) -> dict[str, Any]:
        total_products = self.db.scalar(
            select(func.count()).select_from(Product).where(Product.is_active.is_(True))
        ) or 0

        totals = self.db.execute(
            select(
                func.coalesce(func.sum(Product.stock), 0),
                func.coalesce(func.sum(Product.stock * Product.purchase_price), 0),
                func.coalesce(func.sum(Product.stock * Product.sale_price), 0),
            )
            .where(Product.is_active.is_(True))
        ).one()

        low_stock = self.db.execute(
            select(
                Product.name,
                Product.stock,
                Product.minimum_stock,
                Supplier.name.label("supplier"),
            )
            .outerjoin(Supplier, Product.supplier_id == Supplier.id)
            .where(
                Product.is_active.is_(True),
                Product.stock <= Product.minimum_stock,
            )
            .order_by((Product.minimum_stock - Product.stock).desc())
            .limit(15)
        ).all()

        categories = self.db.execute(
            select(
                Category.name,
                func.count(Product.id),
                func.coalesce(func.sum(Product.stock), 0),
            )
            .outerjoin(Product, (Product.category_id == Category.id) & Product.is_active.is_(True))
            .group_by(Category.id, Category.name)
            .order_by(Category.name)
        ).all()

        return {
            "total_active_products": int(total_products),
            "total_units": int(totals[0]),
            "total_value_cost": _money(totals[1]),
            "total_value_sale": _money(totals[2]),
            "low_stock_products": [
                {"name": n, "stock": int(s), "min": int(m), "supplier": sup or "N/A"}
                for n, s, m, sup in low_stock
            ],
            "by_category": [
                {"name": n, "products": int(p), "units": int(u)}
                for n, p, u in categories
            ],
        }

    def low_stock_products(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(
                Product.name,
                Product.stock,
                Product.minimum_stock,
                (Product.minimum_stock - Product.stock).label("shortage"),
                Category.name.label("category"),
                Supplier.name.label("supplier"),
            )
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Supplier, Product.supplier_id == Supplier.id)
            .where(
                Product.is_active.is_(True),
                Product.stock <= Product.minimum_stock,
            )
            .order_by((Product.minimum_stock - Product.stock).desc())
            .limit(20)
        ).all()

        return [
            {
                "product": n,
                "category": cat,
                "supplier": sup or "N/A",
                "stock": int(s),
                "minimum": int(m),
                "shortage": int(sh),
            }
            for n, s, m, sh, cat, sup in rows
        ]

    # ------------------------------------------------------------------
    # Compras
    # ------------------------------------------------------------------
    def purchase_summary(self, days: int = 30) -> dict[str, Any]:
        cutoff = datetime.now() - timedelta(days=days)

        totals = self.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Purchase.total), 0),
            )
            .select_from(Purchase)
            .where(Purchase.created_at >= cutoff)
        ).one()

        by_status = self.db.execute(
            select(
                Purchase.status,
                func.count(),
                func.coalesce(func.sum(Purchase.total), 0),
            )
            .where(Purchase.created_at >= cutoff)
            .group_by(Purchase.status)
        ).all()

        recent = self.db.execute(
            select(
                Purchase.purchase_number,
                Supplier.name.label("supplier"),
                Purchase.status,
                Purchase.total,
                Purchase.created_at,
            )
            .join(Supplier, Purchase.supplier_id == Supplier.id)
            .where(Purchase.created_at >= cutoff)
            .order_by(Purchase.created_at.desc())
            .limit(10)
        ).all()

        return {
            "period_days": days,
            "total_purchases": int(totals[0]),
            "total_amount": _money(totals[1]),
            "by_status": [
                {"status": s, "count": int(c), "total": _money(t)}
                for s, c, t in by_status
            ],
            "recent": [
                {
                    "number": num,
                    "supplier": sup,
                    "status": st,
                    "total": _money(t),
                    "date": dt.isoformat() if dt else None,
                }
                for num, sup, st, t, dt in recent
            ],
        }

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------
    def customer_credit_status(self) -> dict[str, Any]:
        total_customers = self.db.scalar(select(func.count()).select_from(Customer)) or 0
        credit_customers = self.db.scalar(
            select(func.count()).select_from(Customer).where(Customer.credit_enabled.is_(True))
        ) or 0

        credit_totals = self.db.execute(
            select(
                func.coalesce(func.sum(Customer.credit_limit), 0),
                func.coalesce(func.sum(Customer.current_balance), 0),
            )
            .where(Customer.credit_enabled.is_(True))
        ).one()

        open_receivable_balance = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (ReceivableAccount.status.in_(_OPEN_RECEIVABLE), ReceivableAccount.balance),
                            else_=0,
                        )
                    ),
                    0,
                )
            )
        ) or 0

        return {
            "total_customers": int(total_customers),
            "credit_enabled_customers": int(credit_customers),
            "total_credit_limit": _money(credit_totals[0]),
            "total_current_balance": _money(credit_totals[1]),
            "total_receivable_balance": _money(open_receivable_balance),
        }

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------
    def receivables_status(self) -> dict[str, Any]:
        by_status = self.db.execute(
            select(
                ReceivableAccount.status,
                func.count(),
                func.coalesce(func.sum(ReceivableAccount.balance), 0),
            )
            .group_by(ReceivableAccount.status)
        ).all()

        return {
            "by_status": [
                {"status": s, "count": int(c), "balance": _money(b)}
                for s, c, b in by_status
            ],
        }

    # ------------------------------------------------------------------
    # Caja
    # ------------------------------------------------------------------
    def cash_status(self) -> dict[str, Any]:
        open_registers = self.db.execute(
            select(
                func.count(),
            )
            .select_from(CashRegister)
            .where(CashRegister.status == RegisterStatuses.OPEN)
        ).scalar() or 0

        recent_closed = self.db.execute(
            select(
                CashRegister.id,
                CashRegister.opening_amount,
                CashRegister.expected_amount,
                CashRegister.counted_amount,
                CashRegister.difference,
                CashRegister.opened_at,
                CashRegister.closed_at,
            )
            .where(CashRegister.status == RegisterStatuses.CLOSED)
            .order_by(CashRegister.closed_at.desc())
            .limit(5)
        ).all()

        return {
            "open_registers": int(open_registers),
            "recent_closed": [
                {
                    "id": str(r[0]),
                    "opening": _money(r[1]),
                    "expected": _money(r[2]),
                    "counted": _money(r[3]),
                    "difference": _money(r[4]),
                    "opened_at": r[5].isoformat() if r[5] else None,
                    "closed_at": r[6].isoformat() if r[6] else None,
                }
                for r in recent_closed
            ],
        }

    # ------------------------------------------------------------------
    # Contexto completo del negocio
    # ------------------------------------------------------------------
    def full_business_context(self) -> dict[str, Any]:
        return {
            "sales": self.sales_summary(30),
            "inventory": self.inventory_snapshot(),
            "purchases": self.purchase_summary(30),
            "customers": self.customer_credit_status(),
            "receivables": self.receivables_status(),
            "cash": self.cash_status(),
        }

    # ------------------------------------------------------------------
    # Producto específico
    # ------------------------------------------------------------------
    def product_performance(self, product_id: UUID) -> dict[str, Any]:
        product = self.db.get(Product, product_id)
        if product is None:
            return {"error": "Producto no encontrado"}

        sales_data = self.db.execute(
            select(
                func.coalesce(func.sum(SaleItem.quantity), 0),
                func.coalesce(func.sum(SaleItem.total), 0),
                func.count(func.distinct(SaleItem.sale_id)),
            )
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(
                SaleItem.product_id == product_id,
                Sale.status == SaleStatuses.CONFIRMED,
            )
        ).one()

        movements = self.db.execute(
            select(
                InventoryMovement.movement_type,
                func.count(),
                func.coalesce(func.sum(InventoryMovement.quantity), 0),
            )
            .where(InventoryMovement.product_id == product_id)
            .group_by(InventoryMovement.movement_type)
        ).all()

        return {
            "product": {
                "name": product.name,
                "stock": product.stock,
                "minimum_stock": product.minimum_stock,
                "sale_price": _money(product.sale_price),
                "purchase_price": _money(product.purchase_price),
                "is_active": product.is_active,
            },
            "sales_history": {
                "total_units_sold": int(sales_data[0]),
                "total_revenue": _money(sales_data[1]),
                "total_transactions": int(sales_data[2]),
            },
            "movements": [
                {"type": t, "count": int(c), "quantity": int(q)}
                for t, c, q in movements
            ],
        }
