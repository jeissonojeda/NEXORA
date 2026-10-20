"""Asistente local determinista (Fase 13).

Responde peticiones en español usando **datos reales** del sistema cuando el
proveedor de IA (Gemini) no está configurado o no devuelve respuesta. Solo
ejecuta herramientas de SOLO LECTURA; las acciones de escritura se limitan a
*proponerlas* (nunca se ejecutan aquí).

Reglas:
- Nunca inventa datos: si no encuentra información lo dice claramente.
- Si una referencia (producto/proveedor) es ambigua, pide aclaración.
- Si el usuario no tiene permisos para una acción, no la propone y lo explica.
- Si no entiende la petición, ofrece ejemplos de lo que sí sabe hacer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.ai import intent as intent_engine
from app.ai.data_gatherer import _money
from app.ai.tools import (
    ACTION_NATIVE_PERMISSION,
    READ_EXECUTORS,
)
from app.core.exceptions import AppError
from app.services.rbac_service import RbacService

PRODUCT_INTENTS = {
    intent_engine.Intents.PRODUCT_STOCK,
    intent_engine.Intents.SEARCH_PRODUCT,
    intent_engine.Intents.ADJUST_STOCK,
    intent_engine.Intents.CREATE_PURCHASE,
}


@dataclass
class LocalAnswer:
    message: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    action_proposals: list[dict[str, Any]] = field(default_factory=list)
    intent: str = intent_engine.Intents.UNKNOWN


def _product_label(p: dict[str, Any]) -> str:
    parts = [str(p.get("name"))]
    if p.get("barcode"):
        parts.append(f"código {p['barcode']}")
    if p.get("category"):
        parts.append(str(p["category"]))
    return " · ".join(parts)


class LocalAssistant:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rbac = RbacService(db)

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def respond(self, user, message: str, history: list[Any] | None = None) -> LocalAnswer:
        result = intent_engine.classify(message)

        # Resolución de referencias de seguimiento ("ese producto", "sus
        # existencias") usando el historial de la conversación.
        if (
            result.intent in PRODUCT_INTENTS
            and not result.entities.get("product_query")
            and not result.entities.get("barcode")
        ):
            carried = self._carry_product_from_history(history)
            if carried:
                result.entities["product_query"] = carried

        handler = getattr(self, f"_handle_{result.intent}", None)
        if handler is None:
            return self._handle_unknown(result)
        return handler(user, result)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _exec(self, name: str, args: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
        try:
            output = READ_EXECUTORS[name](self.db, args)
            return output, None
        except AppError as e:  # pragma: no cover - defensivo
            return None, {"name": name, "error": e.message}

    def _has(self, user, code: str) -> bool:
        return self.rbac.user_has_permission(user, code)

    def _can_action(self, user, action_type: str) -> bool:
        native = ACTION_NATIVE_PERMISSION.get(action_type)
        if not native or not self._has(user, native):
            return False
        ai_perm = "ai.purchase" if action_type == "purchase" else "ai.inventory"
        return self._has(user, ai_perm)

    def _carry_product_from_history(self, history: list[Any] | None) -> str | None:
        if not history:
            return None
        for turn in reversed(history):
            text = getattr(turn, "text", None)
            role = getattr(turn, "role", None)
            if text is None and isinstance(turn, dict):
                text = turn.get("text")
                role = turn.get("role")
            if not text:
                continue
            if role and role != "user":
                continue
            candidate = intent_engine.extract_product_query(str(text), intent_engine.normalize(str(text)))
            if candidate:
                return candidate
        return None

    def _resolve_products(self, query: str | None, barcode: str | None) -> list[dict[str, Any]]:
        output, _err = self._exec("get_product_stock", {"q": query, "barcode": barcode})
        if not output:
            return []
        return output.get("matches") or []

    def _resolve_supplier(self, query: str | None) -> dict[str, Any] | None:
        if not query:
            return None
        output, _err = self._exec("search_suppliers", {"q": query})
        if isinstance(output, list) and len(output) == 1:
            return output[0]
        return None

    # ------------------------------------------------------------------
    # Handlers de lectura
    # ------------------------------------------------------------------
    def _handle_help(self, user, result) -> LocalAnswer:
        return LocalAnswer(
            message=intent_engine.HELP_MESSAGE,
            intent=result.intent,
        )

    def _handle_unknown(self, user, result) -> LocalAnswer:
        return LocalAnswer(
            message=(
                "No estoy seguro de lo que necesitas. "
                "Puedo consultar productos, inventario, compras, proveedores, "
                "clientes, cuentas por cobrar, ventas, caja y reportes.\n\n"
                + intent_engine.HELP_MESSAGE
            ),
            intent=result.intent,
        )

    def _handle_low_stock(self, user, result) -> LocalAnswer:
        output, err = self._exec("get_low_stock", {})
        tools = [{"name": "get_low_stock", "output": output}] if output is not None else ([err] if err else [])
        if not output:
            return LocalAnswer(
                message="No hay productos por debajo del stock mínimo. Todo el inventario está en orden.",
                tool_results=tools,
                intent=result.intent,
            )
        lines = [
            f"• {item['product']}: {item['stock']} unidades (mínimo {item['minimum']}, faltan {item['shortage']})"
            for item in output[:10]
        ]
        return LocalAnswer(
            message=(
                f"Encontré {len(output)} producto(s) con stock bajo o agotado:\n"
                + "\n".join(lines)
                + "\n\nPuedo proponerte una compra a un proveedor si me indicas cuál."
            ),
            tool_results=tools,
            intent=result.intent,
        )

    def _handle_product_stock(self, user, result) -> LocalAnswer:
        return self._product_lookup(result, show_prices=True)

    def _handle_search_product(self, user, result) -> LocalAnswer:
        return self._product_lookup(result, show_prices=True)

    def _product_lookup(self, result, show_prices: bool) -> LocalAnswer:
        query = result.entities.get("product_query")
        barcode = result.entities.get("barcode")
        if not query and not barcode:
            return LocalAnswer(
                message=(
                    "¿De qué producto quieres saber las existencias? "
                    "Indícame el nombre o el código de barras."
                ),
                intent=result.intent,
            )
        matches = self._resolve_products(query, barcode)
        tool = {"name": "get_product_stock", "output": {"query": query or barcode, "matches": matches}}
        if not matches:
            return LocalAnswer(
                message=(
                    f"No encontré ningún producto activo que coincida con "
                    f"«{query or barcode}». Verifica el nombre o el código de barras."
                ),
                tool_results=[tool],
                intent=result.intent,
            )
        if len(matches) > 1:
            options = "\n".join(f"• {_product_label(m)}" for m in matches[:6])
            return LocalAnswer(
                message=(
                    f"«{query or barcode}» coincide con varios productos. "
                    "¿A cuál te refieres?\n" + options
                ),
                tool_results=[tool],
                intent=result.intent,
            )
        p = matches[0]
        price = f" Precio venta: {_money(p['sale_price'])}." if show_prices else ""
        low = " (por debajo del mínimo)" if p["stock"] <= p["minimum_stock"] else ""
        supplier = f" Proveedor: {p['supplier']}." if p.get("supplier") else ""
        return LocalAnswer(
            message=(
                f"{p['name']} tiene {p['stock']} unidades en stock "
                f"(mínimo {p['minimum_stock']}){low}.{price}{supplier}"
            ),
            tool_results=[tool],
            intent=result.intent,
        )

    def _handle_inventory_summary(self, user, result) -> LocalAnswer:
        health, _e1 = self._exec("get_stock_health", {})
        context, _e2 = self._exec("get_business_context", {})
        tools = [{"name": "get_stock_health", "output": health}]
        inv = (context or {}).get("inventory") if isinstance(context, dict) else None
        if inv:
            tools.append({"name": "get_business_context", "output": {"inventory": inv}})
        if not health:
            return LocalAnswer(message="No pude obtener el estado del inventario.", tool_results=tools, intent=result.intent)
        lines = [
            f"• Productos activos: {health['total_products']}",
            f"• Con stock bajo: {health['low_stock_products']}",
            f"• Agotados: {health['out_of_stock_products']}",
        ]
        if inv:
            lines.append(f"• Unidades totales: {inv['total_units']}")
            lines.append(f"• Valor a costo: {inv['total_value_cost']}")
            lines.append(f"• Valor a venta: {inv['total_value_sale']}")
        return LocalAnswer(
            message="Estado del inventario:\n" + "\n".join(lines),
            tool_results=tools,
            intent=result.intent,
        )

    def _handle_sales_summary(self, user, result) -> LocalAnswer:
        days = int(result.entities.get("days") or 30)
        output, err = self._exec("get_sales_summary", {"days": days})
        tools = [{"name": "get_sales_summary", "output": output}] if output else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No pude obtener las ventas.", tool_results=tools, intent=result.intent)
        lines = [
            f"Ventas de los últimos {output['period_days']} días:",
            f"• Total facturado: {output['total_revenue']}",
            f"• Número de ventas: {output['total_sales']}",
            f"• Impuestos: {output['total_tax']} · Descuentos: {output['total_discount']}",
        ]
        if output.get("top_products"):
            lines.append("• Más vendidos:")
            for p in output["top_products"][:5]:
                lines.append(f"   - {p['name']}: {p['qty']} unidades ({p['revenue']})")
        if not output["total_sales"]:
            lines.append("No hay ventas registradas en ese período.")
        return LocalAnswer(message="\n".join(lines), tool_results=tools, intent=result.intent)

    def _handle_purchases_summary(self, user, result) -> LocalAnswer:
        days = int(result.entities.get("days") or 30)
        output, err = self._exec("get_purchases_summary", {"days": days})
        tools = [{"name": "get_purchases_summary", "output": output}] if output else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No pude obtener las compras.", tool_results=tools, intent=result.intent)
        lines = [
            f"Compras de los últimos {output['period_days']} días:",
            f"• Cantidad: {output['total_purchases']}",
            f"• Monto total: {output['total_amount']}",
        ]
        if output.get("recent"):
            lines.append("• Recientes:")
            for r in output["recent"][:5]:
                lines.append(f"   - {r['number']} · {r['supplier']} · {r['status']} · {r['total']}")
        if not output["total_purchases"]:
            lines.append("No hay compras registradas en ese período.")
        return LocalAnswer(message="\n".join(lines), tool_results=tools, intent=result.intent)

    def _handle_suppliers(self, user, result) -> LocalAnswer:
        query = result.entities.get("supplier_query")
        output, err = self._exec("search_suppliers", {"q": query})
        tools = [{"name": "search_suppliers", "output": output}] if output is not None else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No encontré proveedores con ese criterio.", tool_results=tools, intent=result.intent)
        lines = [f"• {s['name']}" + (f" · {s['city']}" if s.get("city") else "") for s in output[:10]]
        return LocalAnswer(
            message=f"Encontré {len(output)} proveedor(es):\n" + "\n".join(lines),
            tool_results=tools,
            intent=result.intent,
        )

    def _handle_customers(self, user, result) -> LocalAnswer:
        query = result.entities.get("customer_query")
        output, err = self._exec("search_customers", {"q": query})
        tools = [{"name": "search_customers", "output": output}] if output is not None else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No encontré clientes con ese criterio.", tool_results=tools, intent=result.intent)
        lines = []
        for c in output[:10]:
            extra = f" · saldo {_money(c['current_balance'])}" if c.get("credit_enabled") else ""
            lines.append(f"• {c['name']}{extra}")
        return LocalAnswer(
            message=f"Encontré {len(output)} cliente(s):\n" + "\n".join(lines),
            tool_results=tools,
            intent=result.intent,
        )

    def _handle_receivables(self, user, result) -> LocalAnswer:
        output, err = self._exec("get_receivables", {})
        tools = [{"name": "get_receivables", "output": output}] if output else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No pude obtener las cuentas por cobrar.", tool_results=tools, intent=result.intent)
        customers = output.get("customers", {})
        by_status = output.get("receivables", {}).get("by_status", [])
        lines = [
            "Cartera de clientes y cuentas por cobrar:",
            f"• Clientes registrados: {customers.get('total_customers', 0)}",
            f"• Clientes con crédito: {customers.get('credit_enabled_customers', 0)}",
            f"• Saldo total de crédito: {customers.get('total_current_balance', '0.00')}",
            f"• Saldo pendiente por cobrar: {customers.get('total_receivable_balance', '0.00')}",
        ]
        if by_status:
            lines.append("• Cuentas por estado:")
            for row in by_status:
                lines.append(f"   - {row['status']}: {row['count']} ({row['balance']})")
        return LocalAnswer(message="\n".join(lines), tool_results=tools, intent=result.intent)

    def _handle_cash(self, user, result) -> LocalAnswer:
        output, err = self._exec("get_cash_summary", {})
        tools = [{"name": "get_cash_summary", "output": output}] if output else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No pude obtener el estado de caja.", tool_results=tools, intent=result.intent)
        lines = [f"• Cajas abiertas: {output.get('open_registers', 0)}"]
        recent = output.get("recent_closed") or []
        if recent:
            lines.append("• Últimos cierres:")
            for r in recent[:5]:
                lines.append(
                    f"   - Esperado {r['expected']} · Contado {r['counted']} · Diferencia {r['difference']}"
                )
        else:
            lines.append("No hay cierres de caja registrados.")
        return LocalAnswer(message="\n".join(lines), tool_results=tools, intent=result.intent)

    def _handle_business_summary(self, user, result) -> LocalAnswer:
        output, err = self._exec("get_business_context", {})
        tools = [{"name": "get_business_context", "output": output}] if output else ([err] if err else [])
        if not output:
            return LocalAnswer(message="No pude obtener el resumen del negocio.", tool_results=tools, intent=result.intent)
        sales = output.get("sales", {})
        inv = output.get("inventory", {})
        rec = output.get("receivables", {}).get("by_status", [])
        lines = [
            "Resumen de los últimos 30 días:",
            f"• Ventas: {sales.get('total_sales', 0)} · Facturado {sales.get('total_revenue', '0.00')}",
            f"• Productos activos: {inv.get('total_active_products', 0)} · Con stock bajo {len(inv.get('low_stock_products', []))}",
            f"• Saldo por cobrar: {output.get('customers', {}).get('total_receivable_balance', '0.00')}",
        ]
        if rec:
            lines.append("• Cuentas por cobrar por estado: " + ", ".join(f"{r['status']}={r['count']}" for r in rec))
        return LocalAnswer(message="\n".join(lines), tool_results=tools, intent=result.intent)

    # ------------------------------------------------------------------
    # Handlers de acción (solo propuesta, nunca ejecución)
    # ------------------------------------------------------------------
    def _handle_adjust_stock(self, user, result) -> LocalAnswer:
        if not self._can_action(user, "inventory"):
            return LocalAnswer(
                message="No tienes permiso para ajustar inventario mediante el asistente.",
                intent=result.intent,
            )
        query = result.entities.get("product_query")
        barcode = result.entities.get("barcode")
        new_stock = result.entities.get("quantity")
        if new_stock is None:
            return LocalAnswer(
                message="¿Cuál es el stock final que deseas? Ej.: «ajusta el stock de arroz a 50».",
                intent=result.intent,
            )
        matches = self._resolve_products(query, barcode)
        if len(matches) != 1:
            if not matches:
                return LocalAnswer(
                    message=f"No encontré el producto «{query or barcode}». Indícame el nombre exacto o el código de barras.",
                    intent=result.intent,
                )
            options = "\n".join(f"• {_product_label(m)}" for m in matches[:6])
            return LocalAnswer(
                message="¿A cuál producto te refieres?\n" + options,
                intent=result.intent,
            )
        p = matches[0]
        proposal = {
            "action_name": "adjust_inventory",
            "action_type": "inventory",
            "args": {
                "product_id": p["id"],
                "new_stock": int(new_stock),
                "reason": "Ajuste solicitado vía asistente",
            },
            "permission": "ai.inventory",
        }
        return LocalAnswer(
            message=(
                f"Propongo ajustar «{p['name']}» de {p['stock']} a {int(new_stock)} unidades. "
                "Revisa y confirma la acción."
            ),
            action_proposals=[proposal],
            intent=result.intent,
        )

    def _handle_create_purchase(self, user, result) -> LocalAnswer:
        if not self._can_action(user, "purchase"):
            return LocalAnswer(
                message="No tienes permiso para registrar compras mediante el asistente.",
                intent=result.intent,
            )
        query = result.entities.get("product_query")
        quantity = result.entities.get("quantity")
        if not query:
            return LocalAnswer(
                message="¿Qué producto deseas comprar? Ej.: «comprar 20 arroz a Distribuidora ABC».",
                intent=result.intent,
            )
        if quantity is None:
            return LocalAnswer(
                message="¿Cuántas unidades deseas comprar?",
                intent=result.intent,
            )
        matches = self._resolve_products(query, result.entities.get("barcode"))
        if len(matches) != 1:
            if not matches:
                return LocalAnswer(
                    message=f"No encontré el producto «{query}». Indícame el nombre exacto.",
                    intent=result.intent,
                )
            options = "\n".join(f"• {_product_label(m)}" for m in matches[:6])
            return LocalAnswer(message="¿A cuál producto te refieres?\n" + options, intent=result.intent)

        p = matches[0]
        supplier = self._resolve_supplier(result.entities.get("supplier_query"))
        if supplier is None and p.get("supplier"):
            supplier = {"id": None, "name": p["supplier"]}
            # El proveedor del producto no incluye su id; buscamos por nombre.
            resolved = self._resolve_supplier(p["supplier"])
            if resolved:
                supplier = resolved
        if not supplier or not supplier.get("id"):
            return LocalAnswer(
                message=(
                    f"¿A qué proveedor le compro «{p['name']}»? "
                    "Indícame el nombre del proveedor."
                ),
                intent=result.intent,
            )
        unit_cost = str(Decimal(str(p["purchase_price"])))
        proposal = {
            "action_name": "create_purchase",
            "action_type": "purchase",
            "args": {
                "supplier_id": supplier["id"],
                "items": [
                    {
                        "product_id": p["id"],
                        "quantity": int(quantity),
                        "unit_cost": unit_cost,
                    }
                ],
                "notes": "Compra propuesta vía asistente",
            },
            "permission": "ai.purchase",
        }
        return LocalAnswer(
            message=(
                f"Propongo comprar {int(quantity)} x «{p['name']}» a {supplier['name']} "
                f"(costo unitario {_money(unit_cost)}). Revisa y confirma la acción."
            ),
            action_proposals=[proposal],
            intent=result.intent,
        )
