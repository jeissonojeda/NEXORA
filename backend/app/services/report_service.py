"""Lógica de negocio de reportes y exportación (Fase 9).

Orquesta ReportRepository (datos agregados sin N+1) con los
renderizadores genéricos de app/reports (PDF/Excel). Cada reporte se
declara en un registro central con sus filtros permitidos; los parámetros
no aplicables al tipo elegido se rechazan con 422 para que ningún filtro
mal enviado silencie datos del reporte. La exportación ignora la
paginación y cubre todo el conjunto filtrado.

Los renderizadores no conocen dominio: este servicio entrega columnas,
filas nativas (Decimal/datetime/int/str) y filas de totales.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from app.core.exceptions import AppError
from app.models.category import Category
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.user import User
from app.repositories.report_repository import ReportRepository
from app.reports.excel import build_excel
from app.reports.pdf import (
    build_pdf,
    format_date_only,
    format_datetime_value,
    format_money,
)


class ReportKeys:
    SALES = "sales"
    PRODUCTS_SOLD = "products-sold"
    INVENTORY = "inventory"
    LOW_STOCK = "low-stock"
    PURCHASES = "purchases"
    CASH_REGISTERS = "cash-registers"
    CUSTOMERS_CREDIT = "customers-credit"
    RECEIVABLES = "receivables"
    UTILITIES = "utilities"


VALID_EXPORT_FORMATS = frozenset({"pdf", "excel"})
VALID_PERIODS = frozenset({"DAY", "MONTH"})
VALID_INVENTORY_STATES = frozenset({"active", "inactive", "all"})
VALID_PAYMENT_METHODS = frozenset({"CASH", "CARD", "TRANSFER", "CREDIT"})
VALID_PURCHASE_STATUSES = frozenset({"DRAFT", "CONFIRMED", "CANCELLED"})
VALID_RECEIVABLE_STATUSES = frozenset(
    {"OPEN", "PARTIALLY_PAID", "PAID", "CANCELLED"}
)

PAYMENT_METHOD_LABELS = {
    "CASH": "Efectivo",
    "CARD": "Tarjeta",
    "TRANSFER": "Transferencia",
    "CREDIT": "Crédito",
}
PURCHASE_STATUS_LABELS = {
    "DRAFT": "Borrador",
    "CONFIRMED": "Confirmada",
    "CANCELLED": "Cancelada",
}
REGISTER_STATUS_LABELS = {
    "OPEN": "Abierta",
    "CLOSED": "Cerrada",
    "CANCELLED": "Cancelada",
}
RECEIVABLE_STATUS_LABELS = {
    "OPEN": "Abierta",
    "PARTIALLY_PAID": "Parcialmente pagada",
    "PAID": "Pagada",
    "CANCELLED": "Anulada",
}
REFERENCE_TYPE_LABELS = {"MANUAL": "Manual", "SALE": "Venta"}
STATE_LABELS = {"active": "Activos", "inactive": "Inactivos", "all": "Todos"}
PERIOD_LABELS = {"DAY": "Día", "MONTH": "Mes"}

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "excel": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
}


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    filters: frozenset[str]


REPORT_DEFINITIONS: dict[str, ReportDefinition] = {
    ReportKeys.SALES: ReportDefinition(
        key=ReportKeys.SALES,
        title="Reporte de ventas",
        filters=frozenset(
            {"user_id", "payment_method", "date_from", "date_to"}
        ),
    ),
    ReportKeys.PRODUCTS_SOLD: ReportDefinition(
        key=ReportKeys.PRODUCTS_SOLD,
        title="Reporte de productos vendidos",
        filters=frozenset({"category_id", "date_from", "date_to"}),
    ),
    ReportKeys.INVENTORY: ReportDefinition(
        key=ReportKeys.INVENTORY,
        title="Reporte de inventario",
        filters=frozenset({"category_id", "state"}),
    ),
    ReportKeys.LOW_STOCK: ReportDefinition(
        key=ReportKeys.LOW_STOCK,
        title="Reporte de stock bajo",
        filters=frozenset({"category_id"}),
    ),
    ReportKeys.PURCHASES: ReportDefinition(
        key=ReportKeys.PURCHASES,
        title="Reporte de compras",
        filters=frozenset(
            {"supplier_id", "status", "date_from", "date_to"}
        ),
    ),
    ReportKeys.CASH_REGISTERS: ReportDefinition(
        key=ReportKeys.CASH_REGISTERS,
        title="Reporte de caja",
        filters=frozenset({"user_id", "date_from", "date_to"}),
    ),
    ReportKeys.CUSTOMERS_CREDIT: ReportDefinition(
        key=ReportKeys.CUSTOMERS_CREDIT,
        title="Reporte de clientes con crédito",
        filters=frozenset({"q", "date_from", "date_to"}),
    ),
    ReportKeys.RECEIVABLES: ReportDefinition(
        key=ReportKeys.RECEIVABLES,
        title="Reporte de cuentas por cobrar",
        filters=frozenset(
            {"customer_id", "status", "date_from", "date_to"}
        ),
    ),
    ReportKeys.UTILITIES: ReportDefinition(
        key=ReportKeys.UTILITIES,
        title="Reporte de utilidades",
        filters=frozenset({"period", "date_from", "date_to"}),
    ),
}

# Parámetros transversales fuera del registro por definición.
COMMON_PARAMS = frozenset({"skip", "limit"})


@dataclass
class ReportContent:
    definition: ReportDefinition
    generated_at: datetime
    filters_applied: list[tuple[str, str]]
    columns: list[dict[str, str]]
    rows: list[dict[str, Any]]
    total: int
    skip: int | None
    limit: int | None
    totals: dict[str, Any]
    totals_rows: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.01"))


class ReportService:
    def __init__(self, db) -> None:
        self.db = db
        self.repo = ReportRepository(db)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def get_definition(self, report_type: str) -> ReportDefinition:
        definition = REPORT_DEFINITIONS.get(report_type)
        if definition is None:
            raise AppError(
                status_code=404,
                error_code="REPORT_NOT_FOUND",
                message=f"Reporte desconocido: {report_type}",
            )
        return definition

    def build(
        self,
        report_type: str,
        params: dict[str, Any],
        skip: int = 0,
        limit: int | None = 50,
    ) -> ReportContent:
        definition = self.get_definition(report_type)
        clean = self._validate_params(definition, params)
        builder = self._builders()[report_type]
        return builder(definition, clean, skip, limit)

    def export(
        self,
        report_type: str,
        export_format: str,
        params: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        """Genera el documento y retorna (bytes, media_type, filename)."""
        if export_format not in VALID_EXPORT_FORMATS:
            raise AppError(
                status_code=422,
                error_code="INVALID_EXPORT_FORMAT",
                message="Formato de exportación inválido; use pdf o excel",
            )
        content = self.build(report_type, params, skip=0, limit=None)
        generated_at = content.generated_at
        header_lines = list(content.filters_applied) + [
            (note, "") for note in content.notes
        ]
        if export_format == "pdf":
            payload = build_pdf(
                title=self._document_title(content),
                generated_at=generated_at,
                filters_applied=header_lines,
                column_labels=[c["label"] for c in content.columns],
                rows=self._pdf_rows(content.columns, content.rows),
                totals_rows=[
                    (
                        label,
                        self._pdf_totals_row(label, content.columns, totals),
                    )
                    for label, totals in content.totals_rows
                ],
            )
        else:
            payload = build_excel(
                title=self._document_title(content),
                generated_at=generated_at,
                filters_applied=header_lines,
                columns=content.columns,
                rows=content.rows,
                totals_rows=content.totals_rows,
            )
        extension = "pdf" if export_format == "pdf" else "xlsx"
        filename = self._file_name(content.definition, extension, generated_at)
        return payload, MEDIA_TYPES[export_format], filename

    # ------------------------------------------------------------------
    # Validación de parámetros
    # ------------------------------------------------------------------
    def _validate_params(
        self, definition: ReportDefinition, params: dict[str, Any]
    ) -> dict[str, Any]:
        provided = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        allowed = set(definition.filters) | COMMON_PARAMS
        unknown = sorted(set(provided) - allowed)
        if unknown:
            raise AppError(
                status_code=422,
                error_code="INVALID_FILTER_FOR_REPORT",
                message=(
                    f"Filtros no aplicables al reporte "
                    f"'{definition.key}': {', '.join(unknown)}"
                ),
            )
        clean = {
            key: provided[key] for key in provided if key in definition.filters
        }

        self._validate_enum(clean, "payment_method",
                            VALID_PAYMENT_METHODS, "método de pago")
        # `status` pertenece a compras o cuentas por cobrar según el
        # reporte; la validación estricta por dominio ocurre en el builder.
        self._validate_enum(
            clean,
            "status",
            VALID_PURCHASE_STATUSES | VALID_RECEIVABLE_STATUSES,
            "estado",
        )
        self._validate_enum(clean, "state", VALID_INVENTORY_STATES, "estado")
        self._validate_enum(clean, "period", VALID_PERIODS, "período")

        date_from = clean.get("date_from")
        date_to = clean.get("date_to")
        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise AppError(
                status_code=422,
                error_code="INVALID_DATE_RANGE",
                message=(
                    "La fecha inicial no puede ser posterior a la fecha final"
                ),
            )

        if "q" in clean:
            clean["q"] = str(clean["q"]).strip()
            if not clean["q"]:
                clean["q"] = None
        if "period" in definition.filters:
            clean.setdefault("period", "MONTH")
        return clean

    @staticmethod
    def _validate_enum(
        clean: dict[str, Any], key: str, valid: frozenset[str], label: str
    ) -> None:
        value = clean.get(key)
        if value is None:
            return
        if value not in valid:
            raise AppError(
                status_code=422,
                error_code="INVALID_FILTER_VALUE",
                message=(
                    f"Valor inválido para {label}: '{value}'. Valores "
                    f"permitidos: {', '.join(sorted(valid))}"
                ),
            )

    def _builders(self) -> dict[str, Callable[..., ReportContent]]:
        return {
            ReportKeys.SALES: self._build_sales,
            ReportKeys.PRODUCTS_SOLD: self._build_products_sold,
            ReportKeys.INVENTORY: self._build_inventory,
            ReportKeys.LOW_STOCK: self._build_low_stock,
            ReportKeys.PURCHASES: self._build_purchases,
            ReportKeys.CASH_REGISTERS: self._build_cash_registers,
            ReportKeys.CUSTOMERS_CREDIT: self._build_customers_credit,
            ReportKeys.RECEIVABLES: self._build_receivables,
            ReportKeys.UTILITIES: self._build_utilities,
        }

    # ------------------------------------------------------------------
    # Helpers comunes
    # ------------------------------------------------------------------
    def _base_content(self, definition: ReportDefinition) -> ReportContent:
        return ReportContent(
            definition=definition,
            generated_at=datetime.now(),
            filters_applied=[],
            columns=[],
            rows=[],
            total=0,
            skip=0,
            limit=None,
            totals={},
        )

    def _apply_common_filters(
        self,
        content: ReportContent,
        params: dict[str, Any],
        user_label: str | None = None,
    ) -> None:
        if params.get("date_from") is not None:
            content.filters_applied.append(
                ("Desde", _format_filter_date(params["date_from"]))
            )
        if params.get("date_to") is not None:
            content.filters_applied.append(
                ("Hasta", _format_filter_date(params["date_to"]))
            )
        if params.get("user_id") is not None and user_label:
            content.filters_applied.append(
                (
                    user_label,
                    self._entity_name(User, params["user_id"], "username"),
                )
            )

    def _entity_name(self, model, entity_id: Any, attribute: str) -> str:
        try:
            key = UUID(str(entity_id))
        except ValueError:
            return str(entity_id)
        instance = self.db.get(model, key)
        if instance is None:
            return str(entity_id)
        return str(getattr(instance, attribute, entity_id))

    @staticmethod
    def _document_title(content: ReportContent) -> str:
        return content.definition.title

    @staticmethod
    def _file_name(
        definition: ReportDefinition, extension: str, generated_at: datetime
    ) -> str:
        stamp = generated_at.strftime("%Y%m%d-%H%M")
        return f"reporte-{definition.key}-{stamp}.{extension}"

    @staticmethod
    def _cell_text(value: Any, column_type: str) -> str:
        if column_type == "money":
            return format_money(value)
        if column_type == "datetime":
            return format_datetime_value(value)
        if column_type == "date":
            return format_date_only(value)
        if value is None:
            return "-"
        return str(value)

    def _pdf_rows(
        self, columns: list[dict[str, str]], rows: list[dict[str, Any]]
    ) -> list[list[str]]:
        formatted: list[list[str]] = []
        for row in rows:
            formatted.append(
                [
                    self._cell_text(row.get(col["key"]), col["type"])
                    for col in columns
                ]
            )
        return formatted

    def _pdf_totals_row(
        self,
        label: str,
        columns: list[dict[str, str]],
        totals_map: dict[str, Any],
    ) -> list[object]:
        values: list[object] = [label]
        for col in columns[1:]:
            value = totals_map.get(col["key"])
            values.append(
                "" if value is None else self._cell_text(value, col["type"])
            )
        return values

    def _totals_row(
        self,
        label: str,
        mapping: dict[str, Any],
        money_keys: tuple[str, ...] = (),
        int_keys: tuple[str, ...] = (),
    ) -> tuple[str, dict[str, Any]]:
        row: dict[str, Any] = {}
        for key in money_keys:
            row[key] = _money(mapping.get(key))
        for key in int_keys:
            row[key] = int(mapping.get(key) or 0)
        return label, row

    # ------------------------------------------------------------------
    # Ventas
    # ------------------------------------------------------------------
    def _build_sales(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params, user_label="Vendedor")
        rows, total = self.repo.sales_rows(
            user_id=params.get("user_id"),
            payment_method=params.get("payment_method"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        if params.get("payment_method"):
            content.filters_applied.append(
                (
                    "Método de pago",
                    PAYMENT_METHOD_LABELS[params["payment_method"]],
                )
            )
        content.columns = [
            {"key": "sale_number", "label": "Número", "type": "text"},
            {"key": "sale_date", "label": "Fecha", "type": "datetime"},
            {"key": "seller", "label": "Vendedor", "type": "text"},
            {"key": "customer_name", "label": "Cliente", "type": "text"},
            {"key": "method_label", "label": "Método", "type": "text"},
            {"key": "subtotal", "label": "Subtotal", "type": "money"},
            {"key": "discount", "label": "Descuento", "type": "money"},
            {"key": "tax", "label": "Impuesto", "type": "money"},
            {"key": "total", "label": "Total", "type": "money"},
        ]
        content.rows = [
            {
                **_row_dict(row),
                "method_label": PAYMENT_METHOD_LABELS.get(
                    row.payment_method, row.payment_method
                ),
            }
            for row in rows
        ]
        totals = self.repo.sales_totals(
            user_id=params.get("user_id"),
            payment_method=params.get("payment_method"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "sales_count": int(totals["count"]),
            "subtotal_sum": _money(totals["subtotal_sum"]),
            "discount_sum": _money(totals["discount_sum"]),
            "tax_sum": _money(totals["tax_sum"]),
            "total_sum": _money(totals["total_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "subtotal": totals["subtotal_sum"],
                    "discount": totals["discount_sum"],
                    "tax": totals["tax_sum"],
                    "total": totals["total_sum"],
                },
                money_keys=("subtotal", "discount", "tax", "total"),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Productos vendidos
    # ------------------------------------------------------------------
    def _build_products_sold(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params)
        if params.get("category_id"):
            content.filters_applied.append(
                (
                    "Categoría",
                    self._entity_name(
                        Category, params["category_id"], "name"
                    ),
                )
            )
        rows, total = self.repo.products_sold_rows(
            category_id=params.get("category_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "product_name", "label": "Producto", "type": "text"},
            {"key": "category_name", "label": "Categoría", "type": "text"},
            {"key": "quantity_sold", "label": "Unidades", "type": "int"},
            {"key": "sales_count", "label": "Ventas", "type": "int"},
            {"key": "revenue", "label": "Ingresos", "type": "money"},
        ]
        content.rows = [_row_dict(row) for row in rows]
        totals = self.repo.products_sold_totals(
            category_id=params.get("category_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "units_sold": int(totals["units_sold"]),
            "revenue_sum": _money(totals["revenue_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "quantity_sold": totals["units_sold"],
                    "revenue": totals["revenue_sum"],
                },
                money_keys=("revenue",),
                int_keys=("quantity_sold",),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Inventario
    # ------------------------------------------------------------------
    def _build_inventory(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        state = params.get("state")
        if state and state != "all":
            content.filters_applied.append(("Estado", STATE_LABELS[state]))
        if params.get("category_id"):
            content.filters_applied.append(
                (
                    "Categoría",
                    self._entity_name(
                        Category, params["category_id"], "name"
                    ),
                )
            )
        rows, total = self.repo.inventory_rows(
            category_id=params.get("category_id"),
            state=state if state and state != "all" else None,
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "product_name", "label": "Producto", "type": "text"},
            {"key": "barcode", "label": "Código", "type": "text"},
            {"key": "category_name", "label": "Categoría", "type": "text"},
            {"key": "supplier_name", "label": "Proveedor", "type": "text"},
            {"key": "stock", "label": "Stock", "type": "int"},
            {"key": "minimum_stock", "label": "Mínimo", "type": "int"},
            {"key": "purchase_price", "label": "Costo unit.", "type": "money"},
            {"key": "sale_price", "label": "Precio venta", "type": "money"},
            {"key": "value_cost", "label": "Valor a costo", "type": "money"},
            {"key": "value_sale", "label": "Valor a venta", "type": "money"},
        ]
        content.rows = []
        for row in rows:
            data = _row_dict(row)
            data["value_cost"] = _money(
                (row.stock or 0) * _money(row.purchase_price)
            )
            data["value_sale"] = _money(
                (row.stock or 0) * _money(row.sale_price)
            )
            content.rows.append(data)
        totals = self.repo.inventory_totals(
            category_id=params.get("category_id"),
            state=state if state and state != "all" else None,
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "products_count": int(totals["products_count"]),
            "total_units": int(totals["total_units"]),
            "total_value_cost": _money(totals["total_value_cost"]),
            "total_value_sale": _money(totals["total_value_sale"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "stock": totals["total_units"],
                    "value_cost": totals["total_value_cost"],
                    "value_sale": totals["total_value_sale"],
                },
                money_keys=("value_cost", "value_sale"),
                int_keys=("stock",),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Stock bajo
    # ------------------------------------------------------------------
    def _build_low_stock(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        if params.get("category_id"):
            content.filters_applied.append(
                (
                    "Categoría",
                    self._entity_name(
                        Category, params["category_id"], "name"
                    ),
                )
            )
        rows, total = self.repo.low_stock_rows(
            category_id=params.get("category_id"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "product_name", "label": "Producto", "type": "text"},
            {"key": "category_name", "label": "Categoría", "type": "text"},
            {"key": "supplier_name", "label": "Proveedor", "type": "text"},
            {"key": "stock", "label": "Stock", "type": "int"},
            {"key": "minimum_stock", "label": "Mínimo", "type": "int"},
            {"key": "shortage", "label": "Faltante", "type": "int"},
        ]
        content.rows = [_row_dict(row) for row in rows]
        totals = self.repo.low_stock_totals(
            category_id=params.get("category_id")
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "products_count": int(totals["products_count"]),
            "total_shortage": int(totals["total_shortage"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "shortage": totals["total_shortage"],
                },
                int_keys=("shortage",),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Compras
    # ------------------------------------------------------------------
    def _build_purchases(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params)
        if params.get("supplier_id"):
            content.filters_applied.append(
                (
                    "Proveedor",
                    self._entity_name(
                        Supplier, params["supplier_id"], "name"
                    ),
                )
            )
        if params.get("status"):
            content.filters_applied.append(
                (
                    "Estado",
                    PURCHASE_STATUS_LABELS[params["status"]],
                )
            )
        rows, total = self.repo.purchases_rows(
            supplier_id=params.get("supplier_id"),
            status=params.get("status"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "purchase_number", "label": "Número", "type": "text"},
            {"key": "purchase_date", "label": "Fecha", "type": "datetime"},
            {"key": "supplier_name", "label": "Proveedor", "type": "text"},
            {"key": "status_label", "label": "Estado", "type": "text"},
            {"key": "subtotal", "label": "Subtotal", "type": "money"},
            {"key": "discount", "label": "Descuento", "type": "money"},
            {"key": "tax", "label": "Impuesto", "type": "money"},
            {"key": "total", "label": "Total", "type": "money"},
        ]
        content.rows = [
            {
                **_row_dict(row),
                "status_label": PURCHASE_STATUS_LABELS.get(
                    row.status, row.status
                ),
            }
            for row in rows
        ]
        totals = self.repo.purchases_totals(
            supplier_id=params.get("supplier_id"),
            status=params.get("status"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "purchases_count": int(totals["count"]),
            "total_sum": _money(totals["total_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {"total": totals["total_sum"]},
                money_keys=("total",),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Caja
    # ------------------------------------------------------------------
    def _build_cash_registers(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params, user_label="Cajero")
        rows, total = self.repo.cash_registers_rows(
            user_id=params.get("user_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "cashier", "label": "Cajero", "type": "text"},
            {"key": "status_label", "label": "Estado", "type": "text"},
            {"key": "opened_at", "label": "Apertura", "type": "datetime"},
            {"key": "closed_at", "label": "Cierre", "type": "datetime"},
            {"key": "opening_amount", "label": "Apertura monto", "type": "money"},
            {"key": "expected_amount", "label": "Esperado", "type": "money"},
            {"key": "counted_amount", "label": "Contado", "type": "money"},
            {"key": "difference", "label": "Diferencia", "type": "money"},
        ]
        content.rows = [
            {
                **_row_dict(row),
                "status_label": REGISTER_STATUS_LABELS.get(
                    row.status, row.status
                ),
            }
            for row in rows
        ]
        totals = self.repo.cash_registers_totals(
            user_id=params.get("user_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "registers_count": int(totals["registers_count"]),
            "closed_count": int(totals["closed_count"]),
            "opening_sum": _money(totals["opening_sum"]),
            "expected_sum": _money(totals["expected_sum"]),
            "counted_sum": _money(totals["counted_sum"]),
            "difference_sum": _money(totals["difference_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "opening_amount": totals["opening_sum"],
                    "expected_amount": totals["expected_sum"],
                    "counted_amount": totals["counted_sum"],
                    "difference": totals["difference_sum"],
                },
                money_keys=(
                    "opening_amount",
                    "expected_amount",
                    "counted_amount",
                    "difference",
                ),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Clientes con crédito
    # ------------------------------------------------------------------
    def _build_customers_credit(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params)
        if params.get("q"):
            content.filters_applied.append(("Búsqueda", params["q"]))
        rows, total = self.repo.customers_credit_rows(
            q=params.get("q"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "customer_name", "label": "Cliente", "type": "text"},
            {"key": "identification", "label": "Identificación", "type": "text"},
            {"key": "active_label", "label": "Estado cliente", "type": "text"},
            {"key": "credit_limit", "label": "Límite", "type": "money"},
            {"key": "current_balance", "label": "Saldo cuenta", "type": "money"},
            {"key": "receivable_balance", "label": "Por cobrar", "type": "money"},
            {"key": "open_accounts", "label": "Cuentas abiertas", "type": "int"},
        ]
        content.rows = [
            {
                **_row_dict(row),
                "active_label": "Activo" if row.is_active else "Inactivo",
            }
            for row in rows
        ]
        totals = self.repo.customers_credit_totals(
            q=params.get("q"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "customers_count": int(totals["customers_count"]),
            "credit_limit_sum": _money(totals["credit_limit_sum"]),
            "balance_sum": _money(totals["balance_sum"]),
            "receivable_balance_sum": _money(totals["receivable_balance_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "credit_limit": totals["credit_limit_sum"],
                    "current_balance": totals["balance_sum"],
                    "receivable_balance": totals["receivable_balance_sum"],
                },
                money_keys=(
                    "credit_limit",
                    "current_balance",
                    "receivable_balance",
                ),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------
    def _build_receivables(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params)
        if params.get("customer_id"):
            content.filters_applied.append(
                (
                    "Cliente",
                    self._entity_name(
                        Customer, params["customer_id"], "name"
                    ),
                )
            )
        if params.get("status"):
            content.filters_applied.append(
                ("Estado", RECEIVABLE_STATUS_LABELS[params["status"]])
            )
        rows, total = self.repo.receivables_rows(
            customer_id=params.get("customer_id"),
            status=params.get("status"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            skip=skip,
            limit=limit,
        )
        content.columns = [
            {"key": "created_at", "label": "Fecha", "type": "date"},
            {"key": "customer_name", "label": "Cliente", "type": "text"},
            {"key": "origin_label", "label": "Origen", "type": "text"},
            {"key": "description", "label": "Descripción", "type": "text"},
            {"key": "due_date", "label": "Vence", "type": "date"},
            {"key": "original_amount", "label": "Original", "type": "money"},
            {"key": "paid_amount", "label": "Abonado", "type": "money"},
            {"key": "balance", "label": "Saldo", "type": "money"},
            {"key": "status_label", "label": "Estado", "type": "text"},
        ]
        content.rows = [
            {
                **_row_dict(row),
                "origin_label": REFERENCE_TYPE_LABELS.get(
                    row.reference_type, row.reference_type
                ),
                "status_label": RECEIVABLE_STATUS_LABELS.get(
                    row.status, row.status
                ),
            }
            for row in rows
        ]
        totals = self.repo.receivables_totals(
            customer_id=params.get("customer_id"),
            status=params.get("status"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.total = total
        content.skip = skip
        content.limit = limit
        content.totals = {
            "accounts_count": int(totals["count"]),
            "original_sum": _money(totals["original_sum"]),
            "paid_sum": _money(totals["paid_sum"]),
            "balance_sum": _money(totals["balance_sum"]),
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "original_amount": totals["original_sum"],
                    "paid_amount": totals["paid_sum"],
                    "balance": totals["balance_sum"],
                },
                money_keys=("original_amount", "paid_amount", "balance"),
            )
        ]
        return content

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _build_utilities(
        self,
        definition: ReportDefinition,
        params: dict[str, Any],
        skip: int | None,
        limit: int | None,
    ) -> ReportContent:
        content = self._base_content(definition)
        self._apply_common_filters(content, params)
        period = params.get("period") or "MONTH"
        content.filters_applied.append(("Período", PERIOD_LABELS[period]))
        content.notes.append(
            "Nota: costo estimado con el precio de compra actual del producto"
        )
        revenue_by_period = self.repo.utilities_revenue_by_period(
            period,
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        cost_by_period = self.repo.utilities_cost_by_period(
            period,
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        content.columns = [
            {"key": "period_label", "label": "Período", "type": "text"},
            {"key": "sales_count", "label": "Ventas", "type": "int"},
            {"key": "revenue", "label": "Ingresos", "type": "money"},
            {"key": "cost", "label": "Costo estimado", "type": "money"},
            {"key": "profit", "label": "Utilidad", "type": "money"},
        ]
        revenue_total = _money(Decimal("0"))
        cost_total = _money(Decimal("0"))
        sales_total = 0
        for period_key in sorted(revenue_by_period, reverse=True):
            entry = revenue_by_period[period_key]
            cost = _money(cost_by_period.get(period_key, {}).get("cost"))
            revenue = _money(entry["revenue"])
            sales_count = int(entry.get("sales_count") or 0)
            revenue_total += revenue
            cost_total += cost
            sales_total += sales_count
            content.rows.append(
                {
                    "period_label": period_key,
                    "sales_count": sales_count,
                    "revenue": revenue,
                    "cost": cost,
                    "profit": revenue - cost,
                }
            )
        content.total = len(content.rows)
        content.skip = 0
        content.limit = None
        content.totals = {
            "periods_count": len(content.rows),
            "sales_count_total": sales_total,
            "revenue_total": revenue_total,
            "cost_total": cost_total,
            "profit_total": revenue_total - cost_total,
        }
        content.totals_rows = [
            self._totals_row(
                "TOTALES",
                {
                    "sales_count": sales_total,
                    "revenue": revenue_total,
                    "cost": cost_total,
                    "profit": revenue_total - cost_total,
                },
                money_keys=("revenue", "cost", "profit"),
                int_keys=("sales_count",),
            )
        ]
        return content


def _format_filter_date(value: datetime) -> str:
    if isinstance(value, datetime):
        if value.hour or value.minute or value.second:
            return value.strftime("%d/%m/%Y %H:%M")
        return value.strftime("%d/%m/%Y")
    return str(value)
