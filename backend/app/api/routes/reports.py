"""Endpoints HTTP de reportes y exportación (Fase 9).

Sin lógica de negocio: recolecta parámetros, delega en ReportService y
devuelve JSON (consulta) o binario (PDF/Excel). Consulta requiere
``reports.read``; exportar requiere ``reports.export``.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import (
    ReportColumn,
    ReportDataResponse,
    ReportFilterApplied,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reportes"])


def _collect_params(
    date_from: datetime | None,
    date_to: datetime | None,
    category_id: UUID | None,
    supplier_id: UUID | None,
    customer_id: UUID | None,
    user_id: UUID | None,
    payment_method: str | None,
    status_filter: str | None,
    state: str | None,
    q: str | None,
    period: str | None,
) -> dict[str, object]:
    return {
        "date_from": date_from,
        "date_to": date_to,
        "category_id": category_id,
        "supplier_id": supplier_id,
        "customer_id": customer_id,
        "user_id": user_id,
        "payment_method": payment_method,
        "status": status_filter,
        "state": state,
        "q": q,
        "period": period,
    }


@router.get("/{report_type}", response_model=ReportDataResponse)
def get_report(
    report_type: str,
    _: Annotated[User, Depends(require_permission("reports.read"))],
    db: Annotated[Session, Depends(get_db)],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: UUID | None = None,
    supplier_id: UUID | None = None,
    customer_id: UUID | None = None,
    user_id: UUID | None = None,
    payment_method: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    state: str | None = None,
    q: str | None = None,
    period: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ReportDataResponse:
    params = _collect_params(
        date_from,
        date_to,
        category_id,
        supplier_id,
        customer_id,
        user_id,
        payment_method,
        status_filter,
        state,
        q,
        period,
    )
    content = ReportService(db).build(
        report_type, params, skip=skip, limit=limit
    )
    return ReportDataResponse(
        report_type=content.definition.key,
        title=content.definition.title,
        generated_at=content.generated_at,
        filters_applied=[
            ReportFilterApplied(label=label, value=value)
            for label, value in content.filters_applied
        ],
        columns=[ReportColumn(**column) for column in content.columns],
        items=content.rows,
        skip=content.skip or 0,
        limit=content.limit,
        total=content.total,
        totals=content.totals,
    )


@router.get("/{report_type}/export")
def export_report(
    report_type: str,
    _: Annotated[User, Depends(require_permission("reports.export"))],
    db: Annotated[Session, Depends(get_db)],
    export_format: Annotated[str, Query(alias="format")],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: UUID | None = None,
    supplier_id: UUID | None = None,
    customer_id: UUID | None = None,
    user_id: UUID | None = None,
    payment_method: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    state: str | None = None,
    q: str | None = None,
    period: str | None = None,
) -> Response:
    params = _collect_params(
        date_from,
        date_to,
        category_id,
        supplier_id,
        customer_id,
        user_id,
        payment_method,
        status_filter,
        state,
        q,
        period,
    )
    payload, media_type, filename = ReportService(db).export(
        report_type, export_format, params
    )
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
