"""Servicio de NEXORA AI Operativo (Fase 12).

Backend es el punto de control: la IA PUEDE LEER (tools de solo lectura en el
chat) pero NUNCA escribe sin confirmación del usuario.

Flujo de acción (seguro):
  1. El chat puede proponer acciones vía ACTION_TOOLS (payload capturado, no
     ejecutado).
  2. ``preview_action`` valida permisos y argumentos y devuelve un resumen.
  3. ``confirm_action`` valida de nuevo permisos (nunca confía en el preview) y
     ejecuta la acción vía los servicios de negocio existentes (PurchaseService,
     InventoryService, ProductService, SupplierService, ReceivableService),
     con idempotencia por clave y auditoría inmutable en AIActionHistory.

TODO lo escritura pasa por los servicios de dominio (punto único de cambio de
stock/saldo/caja); la IA nunca ejecuta SQL ni actualiza datos directamente.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from google.genai import types as genai_types
from sqlalchemy.orm import Session

from app.ai.gemini_client import GeminiClient, GeminiClientError, gemini_client
from app.ai.tools import (
    ACTION_TOOL_MAP,
    ACTION_TOOL_NAMES,
    READ_EXECUTORS,
    READ_TOOL_NAMES,
    get_action_tool_or_404,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.rbac import Permissions
from app.models.ai_action import AIActionHistory, AIActionStatuses, AIInvoiceScan
from app.models.supplier import Supplier
from app.schemas.ai_operational import (
    ActionProposal,
    ActionPreviewResponse,
    ChatResponse,
    InvoiceItem,
    InvoiceScanResponse,
    ProductMatch,
    SupplierMatch,
    ToolResult,
)
from app.services.customer_credit_service import money
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.purchase_service import PurchaseService
from app.services.rbac_service import RbacService
from app.services.receivable_service import ReceivableService
from app.services.supplier_service import SupplierService

logger = logging.getLogger(__name__)

settings = get_settings()

MAX_TOOL_ITERATIONS = 5

# Permiso nativo requerido por tipo de acción (defensa en profundidad: la IA
# no puede hacer algo que el rol ya no puede hacer por su cuenta).
ACTION_NATIVE_PERMISSION: dict[str, str] = {
    "purchase": Permissions.PURCHASES_CREATE,
    "inventory": Permissions.INVENTORY_UPDATE,
    "product": Permissions.PRODUCTS_CREATE,
    "supplier": Permissions.SUPPLIERS_CREATE,
    "payment": Permissions.RECEIVABLES_PAYMENT,
}

_SYSTEM_PROMPT = (
    "Eres NEXORA AI, asistente operativo de un sistema de facturación e "
    "inventario de supermercado. Responde en español, de forma clara y "
    "concisa. Puedes consultar datos del negocio usando las herramientas de "
    "solo lectura disponibles (buscar productos, proveedores, stock bajo, "
    "contexto global). Para MODIFICAR datos (crear compras, ajustar "
    "inventario, crear productos/proveedores, registrar pagos) usa las "
    "herramientas de accion ('create_purchase', 'adjust_inventory', "
    "'create_product', 'create_supplier', 'register_payment'); estas acciones "
    "NO se ejecutan tus mismas, REQUIEREN confirmacion del usuario en el "
    "backend. Nunca inventes IDs ni datos; usa los resultados reales de las "
    "herramientas."
)


class AIOperationalService:
    def __init__(self, db: Session, client: GeminiClient | None = None) -> None:
        self.db = db
        self.client = client or gemini_client
        self.rbac = RbacService(db)

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def _user_has_permission(self, user, code: str) -> bool:
        return self.rbac.user_has_permission(user, code)

    def _require_action_permission(self, user, tool: dict[str, Any]) -> None:
        """Valida permiso IA de la action + permiso nativo del dominio."""
        ai_perm = tool.get("permission")
        if ai_perm and not self._user_has_permission(user, ai_perm):
            raise AppError(
                status_code=403,
                error_code="PERMISSION_DENIED",
                message=f"No tiene el permiso requerido: {ai_perm}",
            )
        native = ACTION_NATIVE_PERMISSION.get(tool.get("action_type"))
        if native and not self._user_has_permission(user, native):
            raise AppError(
                status_code=403,
                error_code="PERMISSION_DENIED",
                message=(
                    f"No tiene la autorización nativa para ejecutar "
                    f"'{tool.get('action_type')}' ({native})"
                ),
            )

    # ------------------------------------------------------------------
    # Chat con herramientas (solo lectura + propuestas)
    # ------------------------------------------------------------------
    def chat(self, user, message: str) -> ChatResponse:
        tool_decls = self._build_all_tool_declarations()
        contents = [
            genai_types.Content(
                role="user", parts=[genai_types.Part(text=_SYSTEM_PROMPT)]
            ),
            genai_types.Content(
                role="user", parts=[genai_types.Part(text=message)]
            ),
        ]

        tool_results: list[ToolResult] = []
        action_proposals: list[ActionProposal] = []
        result: dict[str, Any] = {
            "response": "",
            "model_used": settings.GEMINI_MODEL,
            "tokens_used": None,
            "duration_ms": None,
            "function_calls": [],
        }

        try:
            for _ in range(MAX_TOOL_ITERATIONS):
                result = self.client.generate(
                    contents=contents, tools=tool_decls
                )
                calls = result.get("function_calls") or []
                if not calls:
                    break

                # Eco del turno del modelo (la respuesta function_call).
                contents.append(
                    genai_types.Content(
                        role="model",
                        parts=[
                            genai_types.Part(
                                function_call=genai_types.FunctionCall(
                                    name=c["name"], args=c.get("args") or {}
                                )
                            )
                            for c in calls
                        ],
                    )
                )

                response_parts: list[genai_types.Part] = []
                for c in calls:
                    name = c["name"]
                    args = c.get("args") or {}
                    if name in READ_EXECUTORS:
                        try:
                            output = READ_EXECUTORS[name](self.db, args)
                            tool_results.append(ToolResult(name=name, output=output))
                            response_parts.append(
                                genai_types.Part(
                                    function_response=genai_types.FunctionResponse(
                                        name=name,
                                        response={"result": output},
                                    )
                                )
                            )
                        except AppError as e:
                            tool_results.append(
                                ToolResult(name=name, error=e.message)
                            )
                            response_parts.append(
                                genai_types.Part(
                                    function_response=genai_types.FunctionResponse(
                                        name=name,
                                        response={"error": e.message},
                                    )
                                )
                            )
                    elif name in ACTION_TOOL_NAMES:
                        tool = ACTION_TOOL_MAP[name]
                        existing_proposal = any(
                            p.action_name == name for p in action_proposals
                        )
                        if not existing_proposal:
                            action_proposals.append(
                                ActionProposal(
                                    action_name=name,
                                    action_type=tool["action_type"],
                                    args=args,
                                    permission=tool["permission"],
                                )
                            )
                        response_parts.append(
                            genai_types.Part(
                                function_response=genai_types.FunctionResponse(
                                    name=name,
                                    response={
                                        "status": "pending_confirmation",
                                        "message": (
                                            "La accion fue capturada. No se ejecuto. "
                                            "Informa al usuario para que la revise "
                                            "y confirme."
                                        ),
                                    },
                                )
                            )
                        )
                    else:
                        response_parts.append(
                            genai_types.Part(
                                function_response=genai_types.FunctionResponse(
                                    name=name,
                                    response={"error": "unknown_tool"},
                                )
                            )
                        )

                contents.append(
                    genai_types.Content(role="user", parts=response_parts)
                )
        except GeminiClientError:
            raise

        return ChatResponse(
            message=result.get("response") or "",
            tool_results=tool_results,
            action_proposals=action_proposals,
            model_used=result.get("model_used"),
            tokens_used=result.get("tokens_used"),
            duration_ms=result.get("duration_ms"),
        )

    def _build_all_tool_declarations(self) -> list[dict[str, Any]]:
        from app.ai.tools import ACTION_TOOLS, READ_TOOLS

        return [*READ_TOOLS, *ACTION_TOOLS]

    # ------------------------------------------------------------------
    # Preview de acción
    # ------------------------------------------------------------------
    def preview_action(
        self, user, action_name: str, args: dict[str, Any], idempotency_key: str | None
    ) -> ActionPreviewResponse:
        tool = get_action_tool_or_404(action_name)
        self._require_action_permission(user, tool)

        display = self._build_display(tool["action_type"], args)

        return ActionPreviewResponse(
            action_type=tool["action_type"],
            action_name=action_name,
            display=display,
            args=args,
            requires_confirmation=True,
            idempotency_key=idempotency_key,
        )

    def _build_display(self, action_type: str, args: dict[str, Any]) -> dict[str, Any]:
        """Resumen legible (no ejecuta nada)."""
        display: dict[str, Any] = {}
        try:
            if action_type == "purchase":
                supplier = self.db.get(Supplier, UUID(str(args.get("supplier_id"))))
                items = args.get("items") or []
                display = {
                    "supplier": supplier.name if supplier else str(args.get("supplier_id")),
                    "item_count": len(items),
                    "items": [
                        {
                            "product_id": it.get("product_id"),
                            "quantity": it.get("quantity"),
                            "unit_cost": it.get("unit_cost"),
                        }
                        for it in items
                    ],
                }
            elif action_type == "inventory":
                from app.models.product import Product

                product = self.db.get(Product, UUID(str(args.get("product_id"))))
                display = {
                    "product": product.name if product else str(args.get("product_id")),
                    "current_stock": product.stock if product else None,
                    "new_stock": args.get("new_stock"),
                    "reason": args.get("reason"),
                }
            elif action_type == "product":
                from app.models.category import Category

                cat = self.db.get(Category, UUID(str(args.get("category_id"))))
                display = {
                    "name": args.get("name"),
                    "category": cat.name if cat else str(args.get("category_id")),
                    "sale_price": args.get("sale_price"),
                    "barcode": args.get("barcode"),
                }
            elif action_type == "supplier":
                display = {
                    "name": args.get("name"),
                    "identification": args.get("identification"),
                    "city": args.get("city"),
                }
            elif action_type == "payment":
                from app.models.customer import ReceivableAccount

                account = self.db.get(
                    ReceivableAccount, UUID(str(args.get("account_id")))
                )
                display = {
                    "account_id": str(args.get("account_id")),
                    "customer": (
                        account.customer.name if account and account.customer else None
                    ),
                    "balance": account.balance if account else None,
                    "amount": args.get("amount"),
                    "method": args.get("payment_method"),
                }
        except (ValueError, TypeError):
            display = {"summary": "No se pudo previsualizar la acción"}
        return display

    # ------------------------------------------------------------------
    # Confirmación de acción (escritura segura + idempotente + auditada)
    # ------------------------------------------------------------------
    def confirm_action(
        self, user, action_name: str, args: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        tool = get_action_tool_or_404(action_name)
        self._require_action_permission(user, tool)
        action_type = tool["action_type"]

        # Idempotencia: si ya se confirmó esta acción con la misma clave,
        # devolvemos el resultado almacenado sin volver a ejecutar.
        existing = self._find_confirmed(action_name, idempotency_key)
        if existing is not None:
            return {
                "status": AIActionStatuses.CONFIRMED,
                "action_type": action_type,
                "action_name": action_name,
                "result": json.loads(existing.result_json or "{}"),
                "idempotency_key": idempotency_key,
                "reference_id": json.loads(existing.result_json or "{}").get(
                    "reference_id"
                ),
                "replayed": True,
            }

        try:
            result = self._execute_action(user, action_type, args, idempotency_key)
            self._record(
                user=user,
                action_type=action_type,
                action_name=action_name,
                status=AIActionStatuses.CONFIRMED,
                payload=args,
                result=result,
                idempotency_key=idempotency_key,
            )
            return {
                "status": AIActionStatuses.CONFIRMED,
                "action_type": action_type,
                "action_name": action_name,
                "result": result,
                "idempotency_key": idempotency_key,
                "reference_id": result.get("reference_id"),
            }
        except AppError as e:
            self._record(
                user=user,
                action_type=action_type,
                action_name=action_name,
                status=AIActionStatuses.FAILED,
                payload=args,
                error_code=e.error_code,
                error_message=e.message,
                idempotency_key=idempotency_key,
            )
            raise

    # ------------------------------------------------------------------
    # Ejecución (usa los servicios de negocio del dominio)
    # ------------------------------------------------------------------
    def _execute_action(
        self, user, action_type: str, args: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        user_id = user.id
        if action_type == "purchase":
            return self._execute_purchase(user_id, args)
        if action_type == "inventory":
            return self._execute_inventory(user_id, args)
        if action_type == "product":
            return self._execute_product(user, args)
        if action_type == "supplier":
            return self._execute_supplier(args)
        if action_type == "payment":
            return self._execute_payment(user_id, args, idempotency_key)
        raise AppError(
            status_code=422,
            error_code="UNSUPPORTED_ACTION",
            message=f"Tipo de acción no soportado: {action_type}",
        )

    def _execute_purchase(self, user_id: UUID, args: dict[str, Any]) -> dict[str, Any]:
        supplier_id = UUID(str(args.get("supplier_id")))
        items = args.get("items") or []
        prepared = [
            {
                "product_id": it.get("product_id"),
                "quantity": int(it.get("quantity")),
                "unit_cost": money(it.get("unit_cost")),
            }
            for it in items
            if it.get("product_id")
        ]
        if not prepared:
            raise AppError(
                status_code=422,
                error_code="PURCHASE_EMPTY",
                message="La compra propuesta no tiene productos",
            )

        service = PurchaseService(self.db)
        # create DRAFT (commit propio) y luego confirm (transacción atómica de
        # stock vía InventoryService). Coincide con el flujo de la UI.
        purchase = service.create_purchase(
            supplier_id=supplier_id,
            created_by=user_id,
            notes=(args.get("notes") or None),
            items=prepared,
        )
        confirmed = service.confirm_purchase(purchase.id, confirmed_by=user_id)
        return {
            "reference_id": str(purchase.id),
            "purchase_number": confirmed.purchase_number,
            "total": str(confirmed.total),
            "status": confirmed.status,
        }

    def _execute_inventory(
        self, user_id: UUID, args: dict[str, Any]
    ) -> dict[str, Any]:
        product_id = UUID(str(args.get("product_id")))
        new_stock = int(args.get("new_stock"))
        reason = str(args.get("reason") or "").strip()
        svc = InventoryService(self.db)
        movement = svc.adjust_stock(
            product_id=product_id,
            new_stock=new_stock,
            reason=reason,
            created_by=user_id,
        )
        return {
            "reference_id": str(movement.id),
            "product_id": str(movement.product_id),
            "previous_stock": movement.previous_stock,
            "new_stock": movement.new_stock,
            "movement_type": movement.movement_type,
        }

    def _execute_product(self, user, args: dict[str, Any]) -> dict[str, Any]:
        svc = ProductService(self.db)
        product = svc.create_product(
            name=str(args.get("name")),
            sale_price=money(args.get("sale_price")),
            category_id=UUID(str(args.get("category_id"))),
            purchase_price=(
                money(args.get("purchase_price"))
                if args.get("purchase_price") not in (None, "")
                else None
            ),
            barcode=(args.get("barcode") or None),
            minimum_stock=int(args.get("minimum_stock") or 0),
        )
        return {
            "reference_id": str(product.id),
            "product_name": product.name,
            "barcode": product.barcode,
        }

    def _execute_supplier(self, args: dict[str, Any]) -> dict[str, Any]:
        svc = SupplierService(self.db)
        supplier = svc.create_supplier(
            name=str(args.get("name")),
            identification=(args.get("identification") or None),
            contact_name=(args.get("contact_name") or None),
            phone=(args.get("phone") or None),
            email=(args.get("email") or None),
            city=(args.get("city") or None),
        )
        return {
            "reference_id": str(supplier.id),
            "supplier_name": supplier.name,
        }

    def _execute_payment(
        self, user_id: UUID, args: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        account_id = UUID(str(args.get("account_id")))
        svc = ReceivableService(self.db)
        payment, _created = svc.register_payment(
            account_id=account_id,
            amount=money(args.get("amount")),
            payment_method=str(args.get("payment_method")),
            created_by=user_id,
            notes=(args.get("notes") or None),
            idempotency_key=f"ai:{idempotency_key}",
        )
        return {
            "reference_id": str(payment.id),
            "account_id": str(account_id),
            "amount": str(payment.amount),
            "created": _created,
        }

    # ------------------------------------------------------------------
    # Escaneo de facturas (Gemini Vision)
    # ------------------------------------------------------------------
    def scan_invoice(
        self,
        user,
        file_name: str,
        mime_type: str,
        file_bytes: bytes,
    ) -> InvoiceScanResponse:
        from app.ai.gemini_client import GeminiClientError as GCE

        if mime_type not in {
            "image/jpeg",
            "image/png",
            "image/jpg",
            "application/pdf",
        }:
            raise AppError(
                status_code=422,
                error_code="UNSUPPORTED_FILE_TYPE",
                message="Solo se admiten imágenes (JPG/PNG) o PDF de facturas",
            )

        prompt = (
            "Extrae los datos de esta factura de compra. Responde SOLO en JSON "
            "válido con este formato: "
            '{"supplier_name": "...", "invoice_number": "...", '
            '"total": 123.45, "items": [{"product_name": "...", "quantity": 1, '
            '"unit_price": 10.5, "total": 10.5}]}. '
            "Si algún campo no es legible usa null o lista vacía."
        )

        try:
            raw = self.client.generate_content(
                prompt=prompt,
                file_bytes=file_bytes,
                mime_type=mime_type,
            )
        except GCE as e:
            raise AppError(
                status_code=502,
                error_code=e.error_code or "AI_API_ERROR",
                message=e.message,
            )

        raw_text = raw.get("response") or ""
        parsed = self._parse_scan_json(raw_text)

        scan = AIInvoiceScan(
            user_id=user.id,
            file_name=file_name,
            mime_type=mime_type,
            supplier_name=parsed.get("supplier_name"),
            invoice_number=parsed.get("invoice_number"),
            total=(
                money(parsed["total"])
                if parsed.get("total") not in (None, "")
                else None
            ),
            scan_data_json=json.dumps(parsed, ensure_ascii=False),
        )

        # Detección de duplicados vs escaneos previos (mismo proveedor+factura).
        duplicate_scan = self._find_duplicate_scan(
            parsed.get("supplier_name"), parsed.get("invoice_number"), exclude=None
        )

        self.db.add(scan)
        self.db.flush()
        if duplicate_scan is not None:
            scan.duplicate_of = duplicate_scan.id
        self.db.commit()
        self.db.refresh(scan)

        items = [
            InvoiceItem(
                product_name=str(it.get("product_name") or "")[:200],
                quantity=self._to_decimal(it.get("quantity")),
                unit_price=self._to_decimal(it.get("unit_price")),
                total=self._to_decimal(it.get("total")),
            )
            for it in (parsed.get("items") or [])
        ]

        supplier_matches, product_matches = self._match_catalog(parsed)

        return InvoiceScanResponse(
            scan_id=scan.id,
            file_name=file_name,
            supplier_name=parsed.get("supplier_name"),
            invoice_number=parsed.get("invoice_number"),
            total=(
                money(parsed["total"])
                if parsed.get("total") not in (None, "")
                else None
            ),
            items=items,
            supplier_matches=supplier_matches,
            product_matches=product_matches,
            duplicate=duplicate_scan is not None,
            duplicate_of=duplicate_scan.id if duplicate_scan else None,
            raw_text=raw_text[:3000],
        )

    def _parse_scan_json(self, raw_text: str) -> dict[str, Any]:
        """Extrae el JSON de la respuesta Gemini, tolerante a markup."""
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {}

    def _find_duplicate_scan(
        self, supplier_name: str | None, invoice_number: str | None, exclude
    ) -> AIInvoiceScan | None:
        if not supplier_name or not invoice_number:
            return None
        from sqlalchemy import and_

        q = self.db.query(AIInvoiceScan).filter(
            and_(
                AIInvoiceScan.supplier_name == supplier_name,
                AIInvoiceScan.invoice_number == invoice_number,
            )
        )
        if exclude is not None:
            q = q.filter(AIInvoiceScan.id != exclude)
        return q.order_by(AIInvoiceScan.created_at.desc()).first()

    def _match_catalog(
        self, parsed: dict[str, Any]
    ) -> tuple[list[SupplierMatch], list[ProductMatch]]:
        from app.models.product import Product
        from app.models.supplier import Supplier
        from sqlalchemy import func, select

        supplier_matches: list[SupplierMatch] = []
        supplier_name = parsed.get("supplier_name")
        if supplier_name:
            rows = self.db.execute(
                select(Supplier)
                .where(Supplier.is_active.is_(True), func.lower(Supplier.name) == supplier_name.lower())
                .limit(3)
            ).scalars().all()
            if rows:
                supplier_matches = [SupplierMatch(id=s.id, name=s.name, confidence=0.9) for s in rows]

        product_matches: list[ProductMatch] = []
        seen: set[UUID] = set()
        for it in parsed.get("items") or []:
            name = it.get("product_name")
            if not name:
                continue
            row = self.db.execute(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    func.lower(Product.name) == name.lower(),
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is not None and row.id not in seen:
                seen.add(row.id)
                product_matches.append(
                    ProductMatch(id=row.id, name=row.name, barcode=row.barcode, confidence=0.9)
                )
        return supplier_matches, product_matches

    # ------------------------------------------------------------------
    # Historial / auditoría
    # ------------------------------------------------------------------
    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        return Decimal(str(value))

    def list_history(self, user, skip: int = 0, limit: int = 50) -> tuple[list[AIActionHistory], int]:
        total = self.db.query(AIActionHistory).filter(
            AIActionHistory.user_id == user.id
        ).count()
        items = (
            self.db.query(AIActionHistory)
            .filter(AIActionHistory.user_id == user.id)
            .order_by(AIActionHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def health(self) -> dict[str, Any]:
        return {
            "available": self.client.is_available(),
            "model": settings.GEMINI_MODEL,
        }

    def _find_confirmed(self, action_name: str, idempotency_key: str):
        return (
            self.db.query(AIActionHistory)
            .filter(
                AIActionHistory.action_name == action_name,
                AIActionHistory.idempotency_key == idempotency_key,
                AIActionHistory.status == AIActionStatuses.CONFIRMED,
            )
            .first()
        )

    def _record(
        self,
        *,
        user,
        action_type: str,
        action_name: str,
        status: str,
        payload: dict[str, Any],
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        record = AIActionHistory(
            id=uuid4(),
            user_id=user.id,
            action_type=action_type,
            action_name=action_name,
            status=status,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            result_json=(
                json.dumps(result, ensure_ascii=False, default=str)
                if result is not None
                else None
            ),
            error_code=error_code,
            error_message=error_message,
            idempotency_key=idempotency_key,
        )
        self.db.add(record)
        self.db.commit()
