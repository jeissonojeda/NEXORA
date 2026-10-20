"""Schemas de importación masiva de productos (preview/confirm/historial)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DuplicatePolicy = Literal["SKIP_NEW", "UPDATE_EXISTING"]
ImportRowStatus = Literal["VALID", "WARNING", "ERROR"]


class ImportRowData(BaseModel):
    """Datos normalizados de una fila de importación.

    Los IDs de entidades resueltas (categoría/proveedor/impuesto) solo se
    envían de vuelta al confirmar; el backend los revalida en la BD.
    """

    name: str = ""
    barcode: str | None = None
    description: str | None = None
    unit: str | None = None
    category_name: str | None = None
    category_id: str | None = None
    category_declared: bool = False
    supplier_name: str | None = None
    supplier_id: str | None = None
    supplier_declared: bool = False
    tax_name: str | None = None
    tax_id: str | None = None
    purchase_price: str | None = None
    profit_percent: str | None = None
    sale_price: str | None = None
    stock_initial: int | None = None
    minimum_stock: int | None = None
    is_active: bool | None = None
    # Coincidencias inequívocas (sin distinguir mayúsculas/acentos) para que
    # el usuario pueda corregir la referencia antes de confirmar.
    suggested_category: str | None = None
    suggested_supplier: str | None = None
    suggested_tax: str | None = None


class ImportRow(BaseModel):
    row_number: int
    status: ImportRowStatus
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duplicate_of: str | None = None
    existing_product_id: str | None = None
    data: ImportRowData


class ImportEntitySummaryItem(BaseModel):
    """Estado de una entidad declarada en las hojas auxiliares."""

    name: str
    status: Literal["EXISTING", "NEW", "MISSING"]
    can_create: bool = False


class ImportEntitySummary(BaseModel):
    """Resumen de proveedores/categorías/impuestos de la importación."""

    existing: int = 0
    new: int = 0
    total: int = 0
    items: list[ImportEntitySummaryItem] = Field(default_factory=list)


class ImportEntitySummaries(BaseModel):
    suppliers: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    categories: ImportEntitySummary = Field(default_factory=ImportEntitySummary)
    taxes: ImportEntitySummary = Field(default_factory=ImportEntitySummary)


class ImportPreviewResponse(BaseModel):
    """Resultado del análisis previo; no escribe nada en la BD."""

    file_name: str
    total_rows: int
    valid: int
    warnings: int
    errors: int
    rows: list[ImportRow]
    entities: ImportEntitySummaries = Field(default_factory=ImportEntitySummaries)
    declaration_errors: list[str] = Field(default_factory=list)


class ImportConfirmResponse(BaseModel):
    batch_id: UUID
    file_name: str
    total_rows: int
    created: int
    updated: int
    skipped: int
    rejected: int
    rejected_rows: list[ImportRow] = Field(default_factory=list)
    suppliers_created: int = 0
    categories_created: int = 0


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    row_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    rejected_count: int
    created_by_username: str | None = None
    created_at: datetime


class ImportBatchListResponse(BaseModel):
    items: list[ImportBatchResponse]
    total: int
    page: int
    size: int


class ImportEntityItem(BaseModel):
    id: UUID
    name: str
    is_active: bool = True


class ImportEntitiesResponse(BaseModel):
    """Valores existentes para corregir referencias en la vista previa."""

    categories: list[ImportEntityItem] = Field(default_factory=list)
    suppliers: list[ImportEntityItem] = Field(default_factory=list)
    taxes: list[ImportEntityItem] = Field(default_factory=list)


class ImportRowOverride(BaseModel):
    """Corrección de referencias de una fila antes de confirmar."""

    row_number: int = Field(ge=1)
    category: str | None = Field(default=None, max_length=150)
    supplier: str | None = Field(default=None, max_length=150)
    tax: str | None = Field(default=None, max_length=150)
