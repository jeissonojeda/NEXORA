"""Schemas Pydantic del módulo de reportes (Fase 9).

Envolvente genérica: cada reporte se describe con columnas tipadas,
filas como diccionarios clave→valor y totales agregados sobre TODO el
conjunto filtrado. Los montos viajan como string en JSON (convención
del proyecto para Decimal) y las fechas en ISO 8601.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ReportColumnType = Literal["text", "money", "int", "datetime", "date"]


class ReportColumn(BaseModel):
    key: str
    label: str
    type: ReportColumnType = "text"


class ReportFilterApplied(BaseModel):
    label: str
    value: str


class ReportDataResponse(BaseModel):
    report_type: str
    title: str
    generated_at: datetime
    filters_applied: list[ReportFilterApplied]
    columns: list[ReportColumn]
    items: list[dict[str, Any]]
    skip: int
    limit: int | None
    total: int
    totals: dict[str, Any]
