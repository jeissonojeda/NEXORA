"""Importación masiva de productos desde Excel/CSV.

Flujo: plantilla descargable → preview (validación completa sin escribir) →
confirm (aplica en una única transacción) → informe de errores descargable.
El stock inicial entra como movimiento de inventario (ENTRY, referencia
IMPORT); el stock existente NUNCA se sobreescribe en silencio. Duplicados se
resuelven con política explícita SKIP/UPDATE. Auditable vía ProductImportBatch.
"""

import csv
import io
import json
import unicodedata
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.category import Category
from app.models.product import Product
from app.models.product_import import ProductImportBatch
from app.models.supplier import Supplier
from app.models.tax import Tax
from app.repositories.product_repository import ProductRepository
from app.services.inventory_service import InventoryService
from app.services.pricing_service import resolve_prices

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 2000

# Encabezados canónicos de la plantilla (orden fijo).
COLUMNS = (
    "codigo_barras",
    "nombre",
    "categoria",
    "descripcion",
    "proveedor",
    "unidad",
    "precio_compra",
    "margen_utilidad_pct",
    "precio_venta",
    "impuesto",
    "stock_inicial",
    "stock_minimo",
    "activo",
)

REQUIRED_COLUMNS = ("nombre", "categoria")

DUP_POLICIES = ("SKIP_NEW", "UPDATE_EXISTING")

# Encabezados de las hojas auxiliares de la plantilla completa.
SUPPLIER_COLUMNS = (
    "nombre",
    "nit",
    "telefono",
    "email",
    "direccion",
    "contacto",
    "notas",
)

CATEGORY_COLUMNS = (
    "nombre",
    "descripcion",
    "activa",
)

TAX_COLUMNS = (
    "nombre",
    "tasa",
    "activo",
)

# Nombres de hoja aceptados (comparación sin distinguir mayúsculas).
_SHEET_PRODUCTS = "PRODUCTOS"
_SHEET_SUPPLIERS = "PROVEEDORES"
_SHEET_CATEGORIES = "CATEGORIAS"
_SHEET_TAXES = "IMPUESTOS"
_SHEET_INSTRUCTIONS = "INSTRUCCIONES"

# Celdas que empiezan con estos caracteres pueden inyectar fórmulas en
# Excel/LibreOffice; se neutralizan con un prefijo de apóstrofo.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# Mapeo columna de plantilla (español) → clave del dict normalizado (inglés).
_REPORT_KEY_MAP = {
    "codigo_barras": "barcode",
    "nombre": "name",
    "categoria": "category_name",
    "descripcion": "description",
    "proveedor": "supplier_name",
    "unidad": "unit",
    "precio_compra": "purchase_price",
    "margen_utilidad_pct": "profit_percent",
    "precio_venta": "sale_price",
    "impuesto": "tax_name",
    "stock_inicial": "stock_initial",
    "stock_minimo": "minimum_stock",
    "activo": "is_active",
}


def _report_value(data: dict[str, Any], column: str) -> Any:
    """Extrae el valor de una fila normalizada para el informe de errores."""
    key = _REPORT_KEY_MAP.get(column, column)
    if key in data:
        return data.get(key)
    return data.get(column)


def _sanitize_cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalize_entity_name(text: str) -> str:
    """Clave de comparación sin mayúsculas ni acentos (p. ej. 'Aéreo'→'aereo')."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    ).strip()


def _unique_suggestion(text: str, known_names: list[str]) -> str | None:
    """Devuelve el nombre existente al que coincide exactamente 'text'.

    Solo sugiere coincidencias inequívocas (una única entidad distinta con la
    misma forma normalizada); ante la duda no se propone nada.
    """
    key = _normalize_entity_name(text)
    if not key:
        return None
    matches = {
        name for name in known_names if _normalize_entity_name(name) == key
    }
    if len(matches) == 1:
        return matches.pop()
    return None



def _parse_decimal(value: Any, field: str, row_errors: list[str]) -> Decimal | None:
    text = _cell_text(value)
    if not text:
        return None
    normalized = text.replace(",", ".") if "," in text and "." not in text else text
    try:
        result = Decimal(normalized)
    except InvalidOperation:
        row_errors.append(f"{field}: valor numérico inválido ({text!r})")
        return None
    if result < 0:
        row_errors.append(f"{field}: no puede ser negativo")
        return None
    return result


def _parse_int(value: Any, field: str, row_errors: list[str]) -> int | None:
    text = _cell_text(value)
    if not text:
        return None
    normalized = text.replace(",", ".") if "," in text and "." not in text else text
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        row_errors.append(f"{field}: valor numérico inválido ({text!r})")
        return None
    if number != number.to_integral_value():
        row_errors.append(f"{field}: debe ser un número entero")
        return None
    result = int(number)
    if result < 0:
        row_errors.append(f"{field}: no puede ser negativo")
        return None
    return result


def _parse_bool(value: Any) -> bool | None:
    text = _cell_text(value).lower()
    if not text:
        return None
    if text in ("si", "sí", "s", "true", "1", "verdadero", "yes", "y"):
        return True
    if text in ("no", "false", "0", "falso", "n"):
        return False
    return None


class _DeclaredEntity:
    """Entidad declarada en la hoja auxiliar que se creará al confirmar.

    Sustituye a la entidad ORM en la resolución de referencias para que la
    vista previa pueda mostrar la fila como válida sin escribir en la BD.
    El ``id`` es ``None`` hasta que la confirmación la cree.
    """

    __slots__ = ("id", "name", "declaration")

    def __init__(self, declaration: dict[str, Any]) -> None:
        self.id = None
        self.name = declaration.get("name", "")
        self.declaration = declaration

    @property
    def is_declared(self) -> bool:
        return True


class ProductImportService:
    """Preview/confirm de importaciones masivas de productos."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)
        self.inventory = InventoryService(db)

    # ------------------------------------------------------------------
    # Plantilla
    # ------------------------------------------------------------------
    def generate_template(self) -> bytes:
        """XLSX con múltiples hojas para importar productos, proveedores, categorías e impuestos."""
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        # Hoja 1: PRODUCTOS
        ws = wb.active
        ws.title = "Productos"
        product_headers = [
            "codigo_barras",
            "nombre",
            "categoria",
            "descripcion",
            "proveedor",
            "unidad",
            "precio_compra",
            "margen_utilidad",
            "precio_venta",
            "impuesto",
            "stock_inicial",
            "stock_minimo",
            "activo",
        ]
        ws.append([c.upper() for c in product_headers])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for column in ws.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 4
            ws.column_dimensions[column[0].column_letter].width = min(
                max(width, 14), 30
            )

        # Hoja 2: PROVEEDORES
        ws_prov = wb.create_sheet("PROVEEDORES")
        prov_headers = ["nombre", "nit", "telefono", "email", "direccion", "contacto", "notas"]
        ws_prov.append([c.upper() for c in prov_headers])
        for cell in ws_prov[1]:
            cell.font = Font(bold=True)
        # Ejemplo
        ws_prov.append(["Distribuidora X", "900123456-1", "3001234567", "ventas@distribuidorax.com", "Calle 10 #20-30", "Carlos", ""])
        for column in ws_prov.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 4
            ws_prov.column_dimensions[column[0].column_letter].width = min(max(width, 16), 40)

        # Hoja 3: CATEGORIAS
        ws_cat = wb.create_sheet("CATEGORIAS")
        cat_headers = ["nombre", "descripcion", "activa"]
        ws_cat.append([c.upper() for c in cat_headers])
        for cell in ws_cat[1]:
            cell.font = Font(bold=True)
        ws_cat.append(["Abarrotes", "Productos de supermercado", "SI"])
        ws_cat.append(["Bebidas", "Gaseosas y bebidas", "SI"])
        ws_cat.append(["Aseo", "Productos de limpieza", "SI"])
        for column in ws_cat.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 4
            ws_cat.column_dimensions[column[0].column_letter].width = min(max(width, 16), 40)

        # Hoja 4: IMPUESTOS (solo lectura/consulta)
        ws_tax = wb.create_sheet("IMPUESTOS")
        tax_headers = ["nombre", "tasa", "activo"]
        ws_tax.append([c.upper() for c in tax_headers])
        for cell in ws_tax[1]:
            cell.font = Font(bold=True)
        # Agregar impuestos existentes
        for tax in self.db.scalars(select(Tax).order_by(Tax.name)).all():
            ws_tax.append([tax.name, float(tax.rate) if tax.rate is not None else 0, "SI" if tax.is_active else "NO"])
        if ws_tax.max_row == 1:
            ws_tax.append(["IVA 19%", 19, "SI"])
        for column in ws_tax.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 4
            ws_tax.column_dimensions[column[0].column_letter].width = min(max(width, 16), 40)

        # Hoja 5: INSTRUCCIONES
        info = wb.create_sheet("Instrucciones")
        lines = [
            "INSTRUCCIONES DE IMPORTACIÓN - NEXORA",
            "",
            "1. Registre primero los proveedores en la hoja PROVEEDORES.",
            "2. Registre las categorías en la hoja CATEGORIAS.",
            "3. En Productos escriba exactamente el nombre del proveedor y categoría.",
            "4. Utilice los impuestos disponibles en la hoja IMPUESTOS.",
            "5. No modifique los encabezados.",
            "6. No utilice códigos de barras duplicados.",
            "7. El precio de venta puede calcularse mediante el margen de utilidad.",
            "8. El stock inicial solo se aplicará correctamente mediante el proceso de importación.",
            "9. Guarde el archivo como XLSX.",
            "10. Súbalo nuevamente a NEXORA.",
            "",
            "NOTAS:",
            "- Si el proveedor/categoría no existe, podrá crearse durante la importación si tiene permisos.",
            "- Los impuestos NO se crean automáticamente por seguridad. Debe usar uno existente.",
            "- Columnas obligatorias en PRODUCTOS: NOMBRE, CATEGORIA",
            "- Los cambios se aplican en una sola transacción (rollback si hay error).",
        ]
        for line in lines:
            info.append([line])
        info.column_dimensions["A"].width = 90

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Parseo (compartido por preview y confirm)
    # ------------------------------------------------------------------
    def _read_rows(self, content: bytes, file_name: str) -> list[dict[str, Any]]:
        """Lee el archivo y retorna filas crudas con fila de origen."""
        if len(content) > MAX_FILE_BYTES:
            raise AppError(
                status_code=413,
                error_code="IMPORT_FILE_TOO_LARGE",
                message=(
                    f"El archivo supera el límite de "
                    f"{MAX_FILE_BYTES // (1024 * 1024)} MB"
                ),
            )
        lowered = file_name.lower()
        if lowered.endswith(".csv"):
            return self._read_csv(content)
        if lowered.endswith((".xlsx", ".xlsm")):
            return self._read_xlsx(content)
        raise AppError(
            status_code=422,
            error_code="IMPORT_UNSUPPORTED_FORMAT",
            message="Formato no soportado; use .xlsx o .csv",
        )

    def _read_csv(self, content: bytes) -> list[dict[str, Any]]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            raise AppError(
                status_code=422,
                error_code="IMPORT_EMPTY_FILE",
                message="El archivo está vacío",
            )
        header = [_cell_text(h).lower() for h in rows[0]]
        return [
            {"row_number": index, "cells": dict(zip(header, row))}
            for index, row in enumerate(rows[1:], start=2)
            if any(_cell_text(c) for c in row)
        ]

    def _read_xlsx(self, content: bytes) -> list[dict[str, Any]]:
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise AppError(
                status_code=422,
                error_code="IMPORT_INVALID_FILE",
                message=f"No se pudo leer el archivo Excel: {exc}",
            ) from exc
        # Try to find Products sheet (support both old and new naming)
        sheet_name = None
        for name in wb.sheetnames:
            if name.upper() == "PRODUCTOS":
                sheet_name = name
                break
        if sheet_name is None and "Productos" in wb.sheetnames:
            sheet_name = "Productos"
        if sheet_name is None:
            sheet_name = wb.active.title
        ws = wb[sheet_name]
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            raise AppError(
                status_code=422,
                error_code="IMPORT_EMPTY_FILE",
                message="El archivo está vacío",
            )
        header = [_cell_text(h).lower() for h in header_row]
        result: list[dict[str, Any]] = []
        for index, row in enumerate(rows_iter, start=2):
            if not any(_cell_text(c) for c in row):
                continue
            cells = {}
            for key, value in zip(header, row):
                cells[key] = value
            result.append({"row_number": index, "cells": cells})
        wb.close()
        return result

    # ------------------------------------------------------------------
    # Lectura de hojas auxiliares (proveedores / categorías / impuestos)
    # ------------------------------------------------------------------
    @staticmethod
    def _find_sheet(wb, canonical: str) -> Any | None:
        """Busca una hoja por nombre sin distinguir mayúsculas ni acentos."""
        target = _normalize_entity_name(canonical)
        for name in wb.sheetnames:
            if _normalize_entity_name(name) == target:
                return wb[name]
        return None

    def _read_aux_sheets(self, content: bytes) -> dict[str, list[dict[str, Any]]]:
        """Lee las hojas auxiliares de proveedores, categorías e impuestos.

        Devuelve listas de filas crudas con ``row_number`` y ``cells``. Las
        hojas ausentes devuelven lista vacía (compatibilidad con la plantilla
        anterior de una sola hoja).
        """
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise AppError(
                status_code=422,
                error_code="IMPORT_INVALID_FILE",
                message=f"No se pudo leer el archivo Excel: {exc}",
            ) from exc

        def read(ws: Any) -> list[dict[str, Any]]:
            rows_iter = ws.iter_rows(values_only=True)
            try:
                header_row = next(rows_iter)
            except StopIteration:
                return []
            header = [_cell_text(h).lower() for h in header_row]
            rows: list[dict[str, Any]] = []
            for index, row in enumerate(rows_iter, start=2):
                if not any(_cell_text(c) for c in row):
                    continue
                cells = {key: value for key, value in zip(header, row)}
                rows.append({"row_number": index, "cells": cells})
            return rows

        suppliers_ws = self._find_sheet(wb, _SHEET_SUPPLIERS)
        categories_ws = self._find_sheet(wb, _SHEET_CATEGORIES)
        taxes_ws = self._find_sheet(wb, _SHEET_TAXES)
        result = {
            "suppliers": read(suppliers_ws) if suppliers_ws is not None else [],
            "categories": read(categories_ws) if categories_ws is not None else [],
            "taxes": read(taxes_ws) if taxes_ws is not None else [],
        }
        wb.close()
        return result

    # ------------------------------------------------------------------
    # Declaraciones de entidades (proveedores / categorías)
    # ------------------------------------------------------------------
    def _parse_declarations(
        self, aux: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Convierte las hojas auxiliares en declaraciones normalizadas.

        Devuelve {suppliers, categories, taxes} donde cada ítem incluye los
        campos sanityzados y la clave normalizada usada para evitar duplicados.
        Las filas con errores se guardan aparte en ``errors`` para informar
        al usuario sin abortar la vista previa.
        """
        declarations: dict[str, dict[str, dict[str, Any]]] = {
            "suppliers": {},
            "categories": {},
            "taxes": {},
        }
        errors: list[str] = []

        for raw in aux.get("suppliers", []):
            cells = raw["cells"]
            name = _cell_text(cells.get("nombre"))
            if not name:
                errors.append(
                    f"Proveedores fila {raw['row_number']}: falta el nombre"
                )
                continue
            key = _normalize_entity_name(name)
            if key in declarations["suppliers"]:
                errors.append(
                    f"Proveedores fila {raw['row_number']}: "
                    f"'{name}' duplicado dentro de la hoja"
                )
                continue
            declarations["suppliers"][key] = {
                "name": name[:150],
                "identification": (_cell_text(cells.get("nit")) or None),
                "phone": (_cell_text(cells.get("telefono")) or None),
                "email": (_cell_text(cells.get("email")) or None),
                "address": (_cell_text(cells.get("direccion")) or None),
                "contact_name": (_cell_text(cells.get("contacto")) or None),
                "notes": (_cell_text(cells.get("notas")) or None),
                "row_number": raw["row_number"],
            }

        for raw in aux.get("categories", []):
            cells = raw["cells"]
            name = _cell_text(cells.get("nombre"))
            if not name:
                errors.append(
                    f"Categorías fila {raw['row_number']}: falta el nombre"
                )
                continue
            key = _normalize_entity_name(name)
            if key in declarations["categories"]:
                errors.append(
                    f"Categorías fila {raw['row_number']}: "
                    f"'{name}' duplicado dentro de la hoja"
                )
                continue
            active_text = _cell_text(cells.get("activa"))
            is_active = _parse_bool(active_text) if active_text else True
            if active_text and is_active is None:
                errors.append(
                    f"Categorías fila {raw['row_number']}: "
                    f"'activa' inválido ({active_text!r}); use SI o NO"
                )
                continue
            declarations["categories"][key] = {
                "name": name[:100],
                "description": (_cell_text(cells.get("descripcion")) or None),
                "is_active": is_active,
                "row_number": raw["row_number"],
            }

        # Los impuestos NO se crean: solo se registran para validarlos contra
        # los existentes. Se guardan por su nombre normalizado.
        for raw in aux.get("taxes", []):
            cells = raw["cells"]
            name = _cell_text(cells.get("nombre"))
            if not name:
                errors.append(
                    f"Impuestos fila {raw['row_number']}: falta el nombre"
                )
                continue
            declarations["taxes"][_normalize_entity_name(name)] = {
                "name": name[:80],
                "row_number": raw["row_number"],
            }

        return {"declarations": declarations, "errors": errors}

    def _resolve_declared_entities(self) -> dict[str, dict[str, Any]]:
        """Mapa nombre normalizado → entidad existente en la BD.

        Se usa para saber si una referencia del archivo coincide con una
        entidad ya registrada (sin distinguir mayúsculas ni acentos).
        """

        def mapping(model) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for entity in self.db.scalars(select(model)).all():
                result[_normalize_entity_name(entity.name)] = entity
            return result

        return {
            "categoria": mapping(Category),
            "proveedor": mapping(Supplier),
            "impuesto": mapping(Tax),
        }

    def _validate_header(self, raw_rows: list[dict[str, Any]]) -> None:
        if not raw_rows:
            raise AppError(
                status_code=422,
                error_code="IMPORT_EMPTY_FILE",
                message="El archivo no tiene filas de datos",
            )
        header = set(raw_rows[0]["cells"].keys())
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise AppError(
                status_code=422,
                error_code="IMPORT_MISSING_COLUMNS",
                message=(
                    "Faltan columnas obligatorias: "
                    + ", ".join(m.upper() for m in missing)
                ),
            )

    def _build_suggestion_maps(self) -> dict[str, dict[str, str]]:
        """Mapa normalizado → nombre único para categorías/proveedores/impuestos.

        Si dos entidades distintas comparten la misma forma normalizada se
        marca como ambigua (valor vacío) para no sugerir nada por error.
        """

        def mapping(model) -> dict[str, str]:
            result: dict[str, str] = {}
            for name in self.db.scalars(select(model.name)).all():
                key = _normalize_entity_name(name)
                if key in result:
                    result[key] = ""  # ambiguo: no se sugiere
                else:
                    result[key] = name
            return result

        return {
            "categoria": mapping(Category),
            "proveedor": mapping(Supplier),
            "impuesto": mapping(Tax),
        }

    @staticmethod
    def _apply_overrides(
        raw_rows: list[dict[str, Any]],
        overrides: list[dict[str, Any]] | None,
    ) -> None:
        """Aplica correcciones de usuario (categoría/proveedor/impuesto).

        Las correcciones se envían como JSON en la confirmación y se aplican
        ANTES de la validación, de modo que el backend sigue siendo la
        autoridad sobre lo que realmente se importa.
        """
        if not overrides:
            return
        by_row: dict[int, dict[str, Any]] = {}
        for override in overrides:
            if not isinstance(override, dict) or "row_number" not in override:
                raise AppError(
                    status_code=422,
                    error_code="IMPORT_INVALID_OVERRIDES",
                    message="Cada corrección debe incluir 'row_number'",
                )
            try:
                by_row[int(override["row_number"])] = override
            except (TypeError, ValueError) as exc:
                raise AppError(
                    status_code=422,
                    error_code="IMPORT_INVALID_OVERRIDES",
                    message="'row_number' debe ser un número de fila válido",
                ) from exc

        field_map = (
            ("category", "categoria"),
            ("supplier", "proveedor"),
            ("tax", "impuesto"),
        )
        for raw in raw_rows:
            override = by_row.get(raw["row_number"])
            if not override:
                continue
            for source, target in field_map:
                value = override.get(source)
                if value is not None:
                    raw["cells"][target] = value

    def _normalize_row(
        self,
        raw: dict[str, Any],
        seen_barcodes: set[str],
        suggestions: dict[str, dict[str, str]],
        seen_name_categories: set[tuple[str, str]],
        declared: dict[str, dict[str, Any]] | None = None,
        can_create: dict[str, bool] | None = None,
        file_created: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Normaliza y valida una fila; resuelve entidades por nombre.

        ``declared`` contiene las entidades declaradas en las hojas auxiliares
        (nombre normalizado → datos); ``can_create`` indica si el usuario puede
        crearlas. ``file_created`` acumula los IDs de entidades nuevas que se
        irán creando durante la confirmación.
        """
        cells = raw["cells"]
        errors: list[str] = []
        warnings: list[str] = []
        declared = declared or {}
        can_create = can_create or {}
        suggested: dict[str, str | None] = {
            "category": None,
            "supplier": None,
            "tax": None,
        }

        field_kind = {
            "categoria": "categories",
            "proveedor": "suppliers",
            "impuesto": "taxes",
        }

        def resolve_entity(
            field: str,
            model,
            required: bool,
        ):
            """Resuelve una entidad por nombre y sugiere si es inequívoca.

            Orden de resolución: entidad ya creada en BD → entidad declarada
            en el mismo archivo (se creará) → sugerencia (coincidencia
            inequívoca) → error.
            """
            kind = field_kind[field]
            text = _cell_text(cells.get(field))
            if not text:
                if required:
                    errors.append(f"{field}: es obligatoria")
                return None, text, None

            key = _normalize_entity_name(text)

            # 1. Entidad ya creada (por confirmaciones previas o en BD).
            if file_created and key in file_created.get(field, {}):
                return file_created[field][key], text, None

            # 2. Entidad existente en la BD (sin distinguir mayúsculas/acentos).
            entity = self.db.scalars(
                select(model).where(func.lower(model.name) == text.lower())
            ).first()
            if entity is not None:
                return entity, text, None

            # 3. Entidad declarada en el archivo (hoja auxiliar).
            declaration = declared.get(kind, {}).get(key)
            if declaration is not None:
                if model is Tax:
                    # Los impuestos NO se crean automáticamente.
                    errors.append(
                        f"impuesto: '{text}' no existe y no se puede crear "
                        "automáticamente; use un impuesto existente"
                    )
                    return None, text, None
                if not can_create.get(field, False):
                    errors.append(
                        f"{field}: '{text}' no existe y su usuario no tiene "
                        "permisos para crearla"
                    )
                    return None, text, None
                return _DeclaredEntity(declaration), text, None

            # 4. Coincidencia sugerida (nombre parecido ya existente).
            suggestion = suggestions[field].get(key) or None
            if suggestion:
                errors.append(
                    f"{field}: no existe '{text}' "
                    f"(¿quiso decir '{suggestion}'?)"
                )
            else:
                errors.append(f"{field}: no existe '{text}'")
            return None, text, suggestion

        name = _cell_text(cells.get("nombre"))
        if not name:
            errors.append("nombre: es obligatorio")
        elif len(name) > 150:
            errors.append("nombre: máximo 150 caracteres")

        category, category_text, suggested["category"] = resolve_entity(
            "categoria", Category, required=True
        )

        barcode = _cell_text(cells.get("codigo_barras")) or None
        if barcode and len(barcode) > 64:
            errors.append("codigo_barras: máximo 64 caracteres")
            barcode = None
        if barcode:
            if barcode in seen_barcodes:
                errors.append(
                    f"codigo_barras: '{barcode}' duplicado dentro del archivo"
                )
            else:
                seen_barcodes.add(barcode)

        supplier, supplier_text, suggested["supplier"] = resolve_entity(
            "proveedor", Supplier, required=False
        )

        tax, tax_text, suggested["tax"] = resolve_entity(
            "impuesto", Tax, required=False
        )

        description = _cell_text(cells.get("descripcion")) or None
        if description and len(description) > 500:
            warnings.append("descripcion: truncada a 500 caracteres")
            description = description[:500]

        unit = _cell_text(cells.get("unidad")) or None
        if unit and len(unit) > 20:
            warnings.append("unidad: truncada a 20 caracteres")
            unit = unit[:20]

        purchase_price = _parse_decimal(
            cells.get("precio_compra"), "precio_compra", errors
        )
        profit_percent = _parse_decimal(
            cells.get("margen_utilidad_pct"), "margen_utilidad_pct", errors
        )
        if profit_percent is not None and profit_percent > 1000:
            errors.append("margen_utilidad_pct: máximo 1000")
        sale_price = _parse_decimal(
            cells.get("precio_venta"), "precio_venta", errors
        )
        if (
            purchase_price is None
            and profit_percent is None
            and sale_price is None
        ):
            warnings.append(
                "precios: sin precio_compra/margen/venta; se usan ceros"
            )

        stock_initial = _parse_int(
            cells.get("stock_inicial"), "stock_inicial", errors
        )
        minimum_stock = _parse_int(
            cells.get("stock_minimo"), "stock_minimo", errors
        )

        is_active_text = _cell_text(cells.get("activo"))
        is_active = _parse_bool(is_active_text) if is_active_text else None
        if is_active_text and is_active is None:
            errors.append(
                f"activo: valor inválido ({is_active_text!r}); use SI o NO"
            )

        # Duplicados: por código de barras (identificador único) y, si la fila
        # no trae uno, por nombre + categoría. Así un reintento del mismo lote
        # no duplica productos aunque el archivo no lleve códigos de barras.
        existing = None
        duplicate_of = None
        if barcode:
            existing = self.products.get_by_barcode(barcode)
            if existing is not None:
                duplicate_of = str(existing.id)
                warnings.append(
                    f"codigo_barras: ya registrado en '{existing.name}'"
                )
        elif name and category is not None:
            category_key = (
                str(category.id)
                if category.id is not None
                else f"declared:{_normalize_entity_name(category.name)}"
            )
            identity = (_normalize_entity_name(name), category_key)
            if identity in seen_name_categories:
                errors.append(
                    "nombre: duplicado dentro del archivo "
                    "(mismo nombre y categoría)"
                )
            else:
                seen_name_categories.add(identity)
                if category.id is not None:
                    existing = self.db.scalars(
                        select(Product).where(
                            Product.category_id == category.id,
                            func.lower(Product.name) == name.lower(),
                        )
                    ).first()
                    if existing is not None:
                        duplicate_of = str(existing.id)
                        warnings.append(
                            f"nombre: ya registrado como '{existing.name}' en la "
                            "misma categoría; se tratará como duplicado"
                        )

        category_id_str = (
            str(category.id) if category is not None and category.id is not None
            else None
        )
        supplier_id_str = (
            str(supplier.id) if supplier is not None and supplier.id is not None
            else None
        )
        tax_id_str = (
            str(tax.id) if tax is not None and tax.id is not None else None
        )
        category_declared = (
            isinstance(category, _DeclaredEntity) or None
        )
        supplier_declared = (
            isinstance(supplier, _DeclaredEntity) or None
        )

        if category_declared:
            warnings.append(
                f"categoria: '{category.name}' es nueva y se creará"
            )
        if supplier_declared:
            warnings.append(
                f"proveedor: '{supplier.name}' es nuevo y se creará"
            )

        status = "ERROR" if errors else ("WARNING" if warnings else "VALID")
        return {
            "row_number": raw["row_number"],
            "status": status,
            "messages": errors + warnings,
            "errors": errors,
            "duplicate_of": duplicate_of,
            "existing_product_id": duplicate_of,
            "data": {
                "name": name,
                "barcode": barcode,
                "description": description,
                "unit": unit,
                "category_name": category_text or None,
                "category_id": category_id_str,
                "category_declared": bool(category_declared),
                "supplier_name": supplier_text or None,
                "supplier_id": supplier_id_str,
                "supplier_declared": bool(supplier_declared),
                "tax_name": tax_text or None,
                "tax_id": tax_id_str,
                "purchase_price": str(purchase_price)
                if purchase_price is not None
                else None,
                "profit_percent": str(profit_percent)
                if profit_percent is not None
                else None,
                "sale_price": str(sale_price)
                if sale_price is not None
                else None,
                "stock_initial": stock_initial,
                "minimum_stock": minimum_stock,
                "is_active": is_active,
                "suggested_category": suggested["category"],
                "suggested_supplier": suggested["supplier"],
                "suggested_tax": suggested["tax"],
            },
        }

    def _can_create_flags(self, user: Any) -> dict[str, bool]:
        """Permisos para crear entidades desde la importación (RBAC)."""
        if user is None:
            # Sin contexto de usuario (uso interno/tests) se asume conservador.
            return {"categoria": False, "proveedor": False}
        from app.services.rbac_service import RbacService

        rbac = RbacService(self.db)
        return {
            "categoria": rbac.user_has_permission(user, "categories.create"),
            "proveedor": rbac.user_has_permission(user, "suppliers.create"),
        }

    def _entity_summary(
        self,
        declarations: dict[str, dict[str, dict[str, Any]]],
        can_create: dict[str, bool],
        from_file: bool,
    ) -> dict[str, Any]:
        """Resumen de entidades declaradas: existentes vs. nuevas."""
        resolved = self._resolve_declared_entities()

        def summarize(kind: str, field: str) -> dict[str, Any]:
            declared = declarations.get(kind, {})
            existing = 0
            new = 0
            items: list[dict[str, Any]] = []
            for key, declaration in declared.items():
                match = resolved[field].get(key)
                if match is not None:
                    existing += 1
                    items.append(
                        {
                            "name": declaration["name"],
                            "status": "EXISTING",
                            "can_create": True,
                        }
                    )
                else:
                    new += 1
                    items.append(
                        {
                            "name": declaration["name"],
                            "status": "NEW",
                            "can_create": can_create.get(field, False),
                        }
                    )
            return {
                "existing": existing,
                "new": new,
                "total": existing + new,
                "items": items,
            }

        return {
            "suppliers": summarize("suppliers", "proveedor"),
            "categories": summarize("categories", "categoria"),
            # Los impuestos nunca se crean; se reportan como válidos o faltantes.
            "taxes": {
                "existing": len(
                    [
                        d
                        for key, d in declarations.get("taxes", {}).items()
                        if resolved["impuesto"].get(key) is not None
                    ]
                ),
                "new": len(
                    [
                        d
                        for key, d in declarations.get("taxes", {}).items()
                        if resolved["impuesto"].get(key) is None
                    ]
                ),
                "total": len(declarations.get("taxes", {})),
                "items": [
                    {
                        "name": d["name"],
                        "status": (
                            "EXISTING"
                            if resolved["impuesto"].get(key) is not None
                            else "MISSING"
                        ),
                        "can_create": False,
                    }
                    for key, d in declarations.get("taxes", {}).items()
                ],
            },
        }

    def _validate_and_normalize(
        self,
        content: bytes,
        file_name: str,
        overrides: list[dict[str, Any]] | None = None,
        user: Any = None,
    ) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
        raw_rows = self._read_rows(content, file_name)
        if len(raw_rows) > MAX_ROWS:
            raise AppError(
                status_code=413,
                error_code="IMPORT_TOO_MANY_ROWS",
                message=(
                    f"El archivo tiene {len(raw_rows)} filas; el límite es "
                    f"{MAX_ROWS}"
                ),
            )
        self._validate_header(raw_rows)
        self._apply_overrides(raw_rows, overrides)

        can_create = self._can_create_flags(user)

        # Hojas auxiliares (solo .xlsx multi-hoja). En CSV no hay.
        aux: dict[str, list[dict[str, Any]]] = {}
        declarations: dict[str, dict[str, dict[str, Any]]] = {
            "suppliers": {},
            "categories": {},
            "taxes": {},
        }
        declaration_errors: list[str] = []
        if file_name.lower().endswith((".xlsx", ".xlsm")):
            aux = self._read_aux_sheets(content)
            parsed = self._parse_declarations(aux)
            declarations = parsed["declarations"]
            declaration_errors = parsed["errors"]

        suggestions = self._build_suggestion_maps()
        seen_barcodes: set[str] = set()
        seen_name_categories: set[tuple[str, str]] = set()
        rows = [
            self._normalize_row(
                raw,
                seen_barcodes,
                suggestions,
                seen_name_categories,
                declared=declarations,
                can_create=can_create,
            )
            for raw in raw_rows
        ]
        summary = {
            "total_rows": len(rows),
            "valid": sum(1 for r in rows if r["status"] == "VALID"),
            "warnings": sum(1 for r in rows if r["status"] == "WARNING"),
            "errors": sum(1 for r in rows if r["status"] == "ERROR"),
        }
        entities = self._entity_summary(declarations, can_create, bool(aux))
        return rows, summary, {
            "entities": entities,
            "declarations": declarations,
            "declaration_errors": declaration_errors,
        }

    # ------------------------------------------------------------------
    # Entidades disponibles (para corregir referencias antes de importar)
    # ------------------------------------------------------------------
    def available_entities(self) -> dict[str, list[dict[str, Any]]]:
        """Lista categorías, proveedores e impuestos existentes en NEXORA."""

        def serialize(model) -> list[dict[str, Any]]:
            items = self.db.scalars(
                select(model).order_by(model.name)
            ).all()
            return [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "is_active": item.is_active,
                }
                for item in items
            ]

        return {
            "categories": serialize(Category),
            "suppliers": serialize(Supplier),
            "taxes": serialize(Tax),
        }

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def preview(
        self,
        content: bytes,
        file_name: str,
        overrides: list[dict[str, Any]] | None = None,
        user: Any = None,
    ) -> dict[str, Any]:
        rows, summary, extra = self._validate_and_normalize(
            content, file_name, overrides, user=user
        )
        return {
            "file_name": file_name,
            **summary,
            "rows": rows,
            "entities": extra["entities"],
            "declaration_errors": extra["declaration_errors"],
        }

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------
    def _create_new_entities(
        self,
        declarations: dict[str, dict[str, dict[str, Any]]],
        can_create: dict[str, bool],
    ) -> tuple[dict[str, dict[str, uuid.UUID]], int, int]:
        """Crea proveedores y categorías nuevas declaradas en el archivo.

        Devuelve (mapa nombre normalizado → UUID, proveedores creados,
        categorías creadas). Nunca crea impuestos. No hace commit: participa
        de la transacción de la confirmación.
        """
        created_map: dict[str, dict[str, uuid.UUID]] = {
            "categoria": {},
            "proveedor": {},
            "impuesto": {},
        }
        resolved = self._resolve_declared_entities()
        suppliers_created = 0
        categories_created = 0

        for key, declaration in declarations.get("suppliers", {}).items():
            existing = resolved["proveedor"].get(key)
            if existing is not None:
                created_map["proveedor"][key] = existing.id
                continue
            if not can_create.get("proveedor", False):
                raise AppError(
                    status_code=403,
                    error_code="IMPORT_ENTITY_PERMISSION_DENIED",
                    message=(
                        "Este archivo contiene proveedores nuevos. Tu usuario "
                        "no tiene permisos para crearlos."
                    ),
                )
            supplier = Supplier(
                name=declaration["name"],
                identification=declaration.get("identification"),
                contact_name=declaration.get("contact_name"),
                phone=declaration.get("phone"),
                email=declaration.get("email"),
                address=declaration.get("address"),
                notes=declaration.get("notes"),
                is_active=True,
            )
            self.db.add(supplier)
            self.db.flush()
            created_map["proveedor"][key] = supplier.id
            suppliers_created += 1

        for key, declaration in declarations.get("categories", {}).items():
            existing = resolved["categoria"].get(key)
            if existing is not None:
                created_map["categoria"][key] = existing.id
                continue
            if not can_create.get("categoria", False):
                raise AppError(
                    status_code=403,
                    error_code="IMPORT_ENTITY_PERMISSION_DENIED",
                    message=(
                        "Este archivo contiene categorías nuevas. Tu usuario "
                        "no tiene permisos para crearlas."
                    ),
                )
            category = Category(
                name=declaration["name"],
                description=declaration.get("description"),
                is_active=declaration.get("is_active", True),
            )
            self.db.add(category)
            self.db.flush()
            created_map["categoria"][key] = category.id
            categories_created += 1

        return created_map, suppliers_created, categories_created

    def confirm(
        self,
        content: bytes,
        file_name: str,
        duplicate_policy: str,
        created_by: uuid.UUID,
        overrides: list[dict[str, Any]] | None = None,
        user: Any = None,
    ) -> dict[str, Any]:
        if duplicate_policy not in DUP_POLICIES:
            raise AppError(
                status_code=422,
                error_code="INVALID_DUPLICATE_POLICY",
                message=(
                    "Política inválida. Use una de: " + ", ".join(DUP_POLICIES)
                ),
            )

        # La revalidación completa ocurre en el servidor (no confía en el
        # preview del cliente). Aquí se vuelven a resolver las entidades.
        can_create = self._can_create_flags(user)
        aux: dict[str, list[dict[str, Any]]] = {}
        declarations: dict[str, dict[str, dict[str, Any]]] = {
            "suppliers": {},
            "categories": {},
            "taxes": {},
        }
        if file_name.lower().endswith((".xlsx", ".xlsm")):
            aux = self._read_aux_sheets(content)
            declarations = self._parse_declarations(aux)["declarations"]

        rows, _summary, _extra = self._validate_and_normalize(
            content, file_name, overrides, user=user
        )

        created = 0
        updated = 0
        skipped = 0
        rejected_rows: list[dict[str, Any]] = []
        suppliers_created = 0
        categories_created = 0

        try:
            # PASO 1-2: crear/reutilizar proveedores y categorías primero.
            created_map, suppliers_created, categories_created = (
                self._create_new_entities(declarations, can_create)
            )

            for row in rows:
                if row["status"] == "ERROR":
                    rejected_rows.append(row)
                    continue
                data = row["data"]
                # Resolver referencias declaradas a los IDs recién creados.
                self._resolve_declared_ids(data, created_map)
                if row["existing_product_id"] is not None:
                    if duplicate_policy == "SKIP_NEW":
                        skipped += 1
                        continue
                    self._update_existing(
                        row["existing_product_id"], data, created_by
                    )
                    updated += 1
                else:
                    self._create_one(data, created_by)
                    created += 1

            batch = ProductImportBatch(
                file_name=file_name[:255],
                row_count=len(rows),
                created_count=created,
                updated_count=updated,
                skipped_count=skipped,
                rejected_count=len(rejected_rows),
                details=json.dumps(
                    {"rejected_rows": rejected_rows}, ensure_ascii=False
                )
                if rejected_rows
                else None,
                created_by=created_by,
            )
            self.db.add(batch)
            self.db.commit()
        except Exception:
            # Rollback total: nada de proveedores/categorías/productos
            # parcialmente creados.
            self.db.rollback()
            raise

        self.db.refresh(batch)
        return {
            "batch_id": str(batch.id),
            "file_name": file_name,
            "total_rows": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "rejected": len(rejected_rows),
            "rejected_rows": rejected_rows,
            "suppliers_created": suppliers_created,
            "categories_created": categories_created,
        }

    @staticmethod
    def _resolve_declared_ids(
        data: dict[str, Any],
        created_map: dict[str, dict[str, uuid.UUID]],
    ) -> None:
        """Traduce referencias declaradas (nuevas) a los IDs recién creados."""
        if data.get("category_declared") and not data.get("category_id"):
            key = _normalize_entity_name(data.get("category_name") or "")
            new_id = created_map["categoria"].get(key)
            if new_id is not None:
                data["category_id"] = str(new_id)
        if data.get("supplier_declared") and not data.get("supplier_id"):
            key = _normalize_entity_name(data.get("supplier_name") or "")
            new_id = created_map["proveedor"].get(key)
            if new_id is not None:
                data["supplier_id"] = str(new_id)

    def _create_one(self, data: dict[str, Any], created_by: uuid.UUID) -> None:
        """Crea un producto; el stock inicial entra como movimiento ENTRY."""
        try:
            purchase, percent, sale = resolve_prices(
                Decimal(data["purchase_price"] or "0"),
                Decimal(data["profit_percent"]) if data["profit_percent"] else None,
                Decimal(data["sale_price"]) if data["sale_price"] else None,
            )
        except ValueError as exc:
            raise AppError(
                status_code=422,
                error_code="INVALID_PRICE",
                message=str(exc),
            ) from exc

        product = Product(
            name=data["name"],
            barcode=data["barcode"],
            description=data["description"],
            unit=data["unit"],
            purchase_price=purchase,
            profit_percent=percent,
            sale_price=sale,
            category_id=uuid.UUID(data["category_id"]),
            supplier_id=uuid.UUID(data["supplier_id"])
            if data["supplier_id"]
            else None,
            tax_id=uuid.UUID(data["tax_id"]) if data["tax_id"] else None,
            stock=0,
            minimum_stock=data["minimum_stock"] or 0,
            is_active=True if data["is_active"] is None else data["is_active"],
        )
        self.db.add(product)
        self.db.flush()

        stock_initial = data["stock_initial"] or 0
        if stock_initial > 0:
            # Stock inicial auditable: movimiento ENTRY con referencia IMPORT.
            self.inventory.apply_entry(
                product_id=product.id,
                quantity=stock_initial,
                created_by=created_by,
                reason="Stock inicial por importación",
                reference_id=None,
                reference_type="IMPORT",
            )

    def _update_existing(
        self, product_id: str, data: dict[str, Any], created_by: uuid.UUID
    ) -> None:
        """Actualiza un producto existente; el stock NUNCA se toca."""
        product = self.products.get_by_id(uuid.UUID(product_id))
        assert product is not None  # validado en preview

        if data["purchase_price"] is not None or data["sale_price"] is not None \
                or data["profit_percent"] is not None:
            purchase_arg = (
                Decimal(data["purchase_price"])
                if data["purchase_price"] is not None
                else product.purchase_price
            )
            sale_provided = (
                Decimal(data["sale_price"])
                if data["sale_price"] is not None
                else None
            )
            profit_provided = (
                Decimal(data["profit_percent"])
                if data["profit_percent"] is not None
                else None
            )
            if sale_provided is not None:
                profit_arg = None
            elif profit_provided is not None:
                profit_arg = profit_provided
            else:
                profit_arg = product.profit_percent
            try:
                purchase, percent, sale = resolve_prices(
                    purchase_arg, profit_arg, sale_provided
                )
            except ValueError as exc:
                raise AppError(
                    status_code=422,
                    error_code="INVALID_PRICE",
                    message=str(exc),
                ) from exc
            product.purchase_price = purchase
            product.profit_percent = percent
            product.sale_price = sale

        product.description = data["description"] or product.description
        product.unit = data["unit"] or product.unit
        if data["category_id"]:
            product.category_id = uuid.UUID(data["category_id"])
        if data["supplier_id"]:
            product.supplier_id = uuid.UUID(data["supplier_id"])
        if data["tax_id"]:
            product.tax_id = uuid.UUID(data["tax_id"])
        if data["minimum_stock"] is not None:
            product.minimum_stock = data["minimum_stock"]
        if data["is_active"] is not None:
            product.is_active = data["is_active"]
        self.db.flush()

    # ------------------------------------------------------------------
    # Historial e informe de errores
    # ------------------------------------------------------------------
    def list_batches(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[ProductImportBatch], int]:
        count_stmt = select(func.count()).select_from(ProductImportBatch)
        total = int(self.db.scalar(count_stmt) or 0)
        stmt = (
            select(ProductImportBatch)
            .order_by(ProductImportBatch.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def error_report(self, batch_id: uuid.UUID) -> tuple[bytes, str]:
        """Genera XLSX con las filas rechazadas de un lote."""
        from openpyxl import Workbook

        batch = self.db.get(ProductImportBatch, batch_id)
        if batch is None:
            raise AppError(
                status_code=404,
                error_code="IMPORT_BATCH_NOT_FOUND",
                message="Lote de importación no encontrado",
            )
        if not batch.details:
            raise AppError(
                status_code=404,
                error_code="IMPORT_BATCH_NO_ERRORS",
                message="El lote no tiene filas rechazadas",
            )
        payload = json.loads(batch.details)
        rejected = payload.get("rejected_rows", [])

        wb = Workbook()
        ws = wb.active
        ws.title = "Rechazadas"
        header = ["fila", "errores"] + list(COLUMNS)
        ws.append([_sanitize_cell(h) for h in header])
        for row in rejected:
            data = row.get("data", {})
            ws.append(
                [_sanitize_cell(row.get("row_number"))]
                + [_sanitize_cell("; ".join(row.get("errors", [])))]
                + [_sanitize_cell(_report_value(data, col)) for col in COLUMNS]
            )
        buffer = io.BytesIO()
        wb.save(buffer)
        file_name = f"errores_importacion_{batch.created_at:%Y%m%d_%H%M%S}.xlsx"
        return buffer.getvalue(), file_name
