"""Registro de herramientas (tools) de IA para NEXORA AI Operativo.

Define dos familias de tools:
  - ``READ_TOOLS``: herramientas de SOLO LECTURA que la IA ejecuta durante el
    chat (buscar productos, stock bajo, contexto del negocio, proveedores).
    Nunca modifican datos.
  - ``ACTION_TOOLS``: acciones que la IA PUEDE PROPONER pero NUNCA ejecutar
    directamente. Deben confirmarse vía /ai/action/preview -> /ai/action/confirm
    en el backend, que valida permisos (ai.inventory / ai.purchase / etc.).

La autorización de cada acción se valida en el backend por el permiso de la
acción; la IA no puede auto-elevar permisos.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.data_gatherer import DataGatherer
from app.core.exceptions import AppError
from app.core.rbac import Permissions

# Permiso nativo requerido por tipo de acción (defensa en profundidad: la IA
# no puede hacer algo que el rol ya no puede hacer por su cuenta).
ACTION_NATIVE_PERMISSION: dict[str, str] = {
    "purchase": Permissions.PURCHASES_CREATE,
    "inventory": Permissions.INVENTORY_UPDATE,
    "product": Permissions.PRODUCTS_CREATE,
    "supplier": Permissions.SUPPLIERS_CREATE,
    "payment": Permissions.RECEIVABLES_PAYMENT,
}


# ----------------------------------------------------------------------
# Helpers / mapeo de Argumentos de acciones -> sábana de dominio
# ----------------------------------------------------------------------
def _opt_uuid(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    return UUID(str(value))


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# ----------------------------------------------------------------------
# Tools de SOLO LECTURA
# ----------------------------------------------------------------------
def execute_search_products(db: Session, args: dict[str, Any]) -> list[dict[str, Any]]:
    from app.models.product import Product
    from app.repositories.product_repository import ProductRepository

    q = _opt_str(args.get("q")) or ""
    repo = ProductRepository(db)
    items, _total = repo.search(q=q, is_active=True, limit=20)
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "barcode": p.barcode,
            "category": p.category.name if p.category else None,
            "stock": p.stock,
            "minimum_stock": p.minimum_stock,
            "sale_price": str(p.sale_price),
            "purchase_price": str(p.purchase_price),
            "supplier_id": str(p.supplier_id) if p.supplier_id else None,
        }
        for p in items
    ]


def execute_get_low_stock(db: Session, args: dict[str, Any]) -> list[dict[str, Any]]:
    gather = DataGatherer(db)
    return gather.low_stock_products()


def execute_get_business_context(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    gather = DataGatherer(db)
    return gather.full_business_context()


def execute_search_suppliers(db: Session, args: dict[str, Any]) -> list[dict[str, Any]]:
    from app.models.supplier import Supplier
    from app.repositories.supplier_repository import SupplierRepository

    q = _opt_str(args.get("q")) or ""
    repo = SupplierRepository(db)
    items, _total = repo.search(q=q, is_active=True, limit=20)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "identification": s.identification,
            "city": s.city,
            "is_active": s.is_active,
        }
        for s in items
    ]


def execute_get_sales_summary(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from app.ai.data_gatherer import DataGatherer

    days = _opt_int(args.get("days")) or 30
    return DataGatherer(db).sales_summary(days=max(1, min(days, 365)))


def execute_get_purchases_summary(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from app.ai.data_gatherer import DataGatherer

    days = _opt_int(args.get("days")) or 30
    return DataGatherer(db).purchase_summary(days=max(1, min(days, 365)))


def execute_get_receivables(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from app.ai.data_gatherer import DataGatherer

    gather = DataGatherer(db)
    return {
        "customers": gather.customer_credit_status(),
        "receivables": gather.receivables_status(),
    }


def execute_get_cash_summary(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from app.ai.data_gatherer import DataGatherer

    return DataGatherer(db).cash_status()


def execute_search_customers(db: Session, args: dict[str, Any]) -> list[dict[str, Any]]:
    from app.repositories.customer_repository import CustomerRepository

    q = _opt_str(args.get("q")) or ""
    repo = CustomerRepository(db)
    items, _total = repo.search(q=q, limit=20)
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "identification": c.identification,
            "phone": c.phone,
            "credit_enabled": c.credit_enabled,
            "current_balance": str(c.current_balance),
            "credit_limit": str(c.credit_limit),
            "is_active": c.is_active,
        }
        for c in items
    ]


def execute_get_product_stock(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Resuelve un producto por código de barras o texto y devuelve su stock.

    Devuelve ``matches`` (hasta 5) y ``ambiguous`` para que el asistente pueda
    pedir aclaración cuando la referencia no es única.
    """
    from app.repositories.product_repository import ProductRepository

    barcode = _opt_str(args.get("barcode"))
    q = _opt_str(args.get("q")) or ""
    repo = ProductRepository(db)

    items: list[Any] = []
    if barcode:
        found = repo.get_by_barcode(barcode)
        if found is not None:
            items = [found]
    if not items and q:
        items, _total = repo.search(q=q, is_active=True, limit=5)

    def _serialize(p: Any) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "name": p.name,
            "barcode": p.barcode,
            "category": p.category.name if p.category else None,
            "supplier": p.supplier.name if p.supplier else None,
            "stock": p.stock,
            "minimum_stock": p.minimum_stock,
            "sale_price": str(p.sale_price),
            "purchase_price": str(p.purchase_price),
            "is_active": p.is_active,
        }

    return {
        "query": barcode or q,
        "count": len(items),
        "ambiguous": len(items) > 1,
        "matches": [_serialize(p) for p in items],
    }


def execute_get_stock_health(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from app.models.product import Product
    from sqlalchemy import func, select

    total = db.scalar(
        select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    ) or 0
    low = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.is_active.is_(True),
            Product.stock <= Product.minimum_stock,
        )
    ) or 0
    out = db.scalar(
        select(func.count()).select_from(Product).where(
            Product.is_active.is_(True), Product.stock == 0
        )
    ) or 0
    return {
        "total_products": int(total),
        "low_stock_products": int(low),
        "out_of_stock_products": int(out),
    }


READ_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": (
            "Busca productos activos por nombre o código de barras. "
            "Retorna lista con id, nombre, stock, precios y proveedor."
        ),
        "parameters": {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "texto de búsqueda"}},
            "required": [],
        },
    },
    {
        "name": "get_low_stock",
        "description": "Retorna productos con stock bajo o agotados (<= mínimo).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_business_context",
        "description": (
            "Resumen general del negocio: ventas, inventario, compras, clientes, "
            "cuentas por cobrar y caja de los últimos 30 días."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_suppliers",
        "description": "Busca proveedores activos por nombre o identificación.",
        "parameters": {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "texto de búsqueda"}},
            "required": [],
        },
    },
    {
        "name": "get_stock_health",
        "description": "Retorna conteos de productos totales, con stock bajo y agotados.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_product_stock",
        "description": (
            "Resuelve un producto por nombre, texto o código de barras y "
            "devuelve su stock, precios, categoría y proveedor. Marca "
            "'ambiguous' cuando la referencia coincide con varios productos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "nombre o texto del producto"},
                "barcode": {"type": "string", "description": "código de barras exacto"},
            },
            "required": [],
        },
    },
    {
        "name": "get_sales_summary",
        "description": (
            "Resumen real de ventas de un período: total facturado, número de "
            "ventas, métodos de pago y productos más vendidos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "período en días (por defecto 30)"}
            },
            "required": [],
        },
    },
    {
        "name": "get_purchases_summary",
        "description": (
            "Resumen real de compras de un período: cantidad, monto total por "
            "estado y compras recientes con su proveedor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "período en días (por defecto 30)"}
            },
            "required": [],
        },
    },
    {
        "name": "get_receivables",
        "description": (
            "Estado de la cartera de clientes y cuentas por cobrar: totales de "
            "crédito, saldo pendiente y desglose por estado."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_customers",
        "description": "Busca clientes activos por nombre, identificación, correo o teléfono.",
        "parameters": {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "texto de búsqueda"}},
            "required": [],
        },
    },
    {
        "name": "get_cash_summary",
        "description": (
            "Estado de caja: cajas abiertas y turnos cerrados recientes con "
            "efectivo esperado, contado y diferencia."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

READ_EXECUTORS: dict[str, Any] = {
    "search_products": execute_search_products,
    "get_low_stock": execute_get_low_stock,
    "get_business_context": execute_get_business_context,
    "search_suppliers": execute_search_suppliers,
    "get_stock_health": execute_get_stock_health,
    "get_product_stock": execute_get_product_stock,
    "get_sales_summary": execute_get_sales_summary,
    "get_purchases_summary": execute_get_purchases_summary,
    "get_receivables": execute_get_receivables,
    "search_customers": execute_search_customers,
    "get_cash_summary": execute_get_cash_summary,
}

READ_TOOL_NAMES = {t["name"] for t in READ_TOOLS}


# ----------------------------------------------------------------------
# Tools de ACCIÓN (solo propuesta; requieren confirmación)
# ----------------------------------------------------------------------
ACTION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_purchase",
        "permission": "ai.purchase",
        "action_type": "purchase",
        "description": (
            "Propone crear una compra a un proveedor con sus ítems. "
            "NO se ejecuta; requiere confirmación del usuario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "supplier_id": {"type": "string", "description": "ID del proveedor"},
                "notes": {"type": "string", "description": "notas de la compra"},
                "items": {
                    "type": "array",
                    "description": "ítems con product_id, quantity, unit_cost",
                },
            },
            "required": ["supplier_id", "items"],
        },
    },
    {
        "name": "adjust_inventory",
        "permission": "ai.inventory",
        "action_type": "inventory",
        "description": (
            "Propone ajustar el stock de un producto a un valor final. "
            "NO se ejecuta; requiere confirmación del usuario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "ID del producto"},
                "new_stock": {"type": "integer", "description": "stock final deseado"},
                "reason": {"type": "string", "description": "motivo del ajuste"},
            },
            "required": ["product_id", "new_stock", "reason"],
        },
    },
    {
        "name": "create_product",
        "permission": "ai.inventory",
        "action_type": "product",
        "description": (
            "Propone crear un nuevo producto. NO se ejecuta; requiere confirmación."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category_id": {"type": "string"},
                "sale_price": {"type": "string"},
                "purchase_price": {"type": "string"},
                "barcode": {"type": "string"},
                "minimum_stock": {"type": "integer"},
            },
            "required": ["name", "category_id", "sale_price"],
        },
    },
    {
        "name": "create_supplier",
        "permission": "ai.inventory",
        "action_type": "supplier",
        "description": (
            "Propone crear un proveedor. NO se ejecuta; requiere confirmación."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "identification": {"type": "string"},
                "contact_name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "city": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "register_payment",
        "permission": "ai.inventory",
        "action_type": "payment",
        "description": (
            "Propone registrar un pago de una cuenta por cobrar. "
            "NO se ejecuta; requiere confirmación del usuario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "ID de la cuenta por cobrar"},
                "amount": {"type": "string", "description": "monto del pago"},
                "payment_method": {"type": "string", "description": "CASH|CARD|TRANSFER|OTHER"},
                "notes": {"type": "string"},
            },
            "required": ["account_id", "amount", "payment_method"],
        },
    },
]

ACTION_TOOL_MAP: dict[str, dict[str, Any]] = {
    t["name"]: t for t in ACTION_TOOLS
}
ACTION_TOOL_NAMES = set(ACTION_TOOL_MAP)


def get_action_tool_or_404(name: str) -> dict[str, Any]:
    tool = ACTION_TOOL_MAP.get(name)
    if tool is None:
        raise AppError(
            status_code=404,
            error_code="AI_ACTION_TOOL_NOT_FOUND",
            message=f"La herramienta de acción '{name}' no existe",
        )
    return tool
