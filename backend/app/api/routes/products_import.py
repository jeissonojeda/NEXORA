"""Importación masiva de productos desde Excel/CSV.

Orden de rutas: este router debe registrarse ANTES que ``products_router``
en ``main.py`` (los prefijos fijos ``/products/import/...`` deben ganarle
a ``/products/{product_id}``).
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.product_import import (
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportConfirmResponse,
    ImportEntitiesResponse,
    ImportPreviewResponse,
    ImportRowOverride,
)
from app.services.product_import_service import (
    DUP_POLICIES,
    MAX_FILE_BYTES,
    ProductImportService,
)

router = APIRouter(prefix="/products/import", tags=["Importación de productos"])


def _parse_overrides(raw: str | None) -> list[dict[str, object]] | None:
    """Parsea las correcciones de referencias enviadas por el frontend."""
    if raw is None or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(
            status_code=422,
            error_code="IMPORT_INVALID_OVERRIDES",
            message="Las correcciones enviadas no son JSON válido",
        ) from exc
    if not isinstance(payload, list):
        raise AppError(
            status_code=422,
            error_code="IMPORT_INVALID_OVERRIDES",
            message="Las correcciones deben ser una lista de filas",
        )
    try:
        return [
            ImportRowOverride.model_validate(item).model_dump(
                exclude_none=True
            )
            for item in payload
        ]
    except ValidationError as exc:
        raise AppError(
            status_code=422,
            error_code="IMPORT_INVALID_OVERRIDES",
            message="Corrección inválida; revise la fila y los nombres",
        ) from exc


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise AppError(
            status_code=413,
            error_code="IMPORT_FILE_TOO_LARGE",
            message="El archivo supera el límite de 5 MB",
        )
    if not content:
        raise AppError(
            status_code=422,
            error_code="IMPORT_EMPTY_FILE",
            message="El archivo está vacío",
        )
    return content


@router.get("/template")
def download_template(
    _: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Plantilla XLSX con encabezados e instrucciones de uso."""
    content = ProductImportService(db).generate_template()
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="plantilla_importacion_productos.xlsx"'
            )
        },
    )


@router.get("/entities", response_model=ImportEntitiesResponse)
def list_import_entities(
    _: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
) -> ImportEntitiesResponse:
    """Categorías, proveedores e impuestos existentes para la vista previa."""
    return ImportEntitiesResponse.model_validate(
        ProductImportService(db).available_entities()
    )


@router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(
    current_user: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str | None, Form()] = None,
) -> ImportPreviewResponse:
    """Analiza el archivo y devuelve filas con estado/mensajes. No escribe."""
    content = _read_upload(file)
    result = ProductImportService(db).preview(
        content,
        file.filename or "importacion.xlsx",
        overrides=_parse_overrides(overrides),
        user=current_user,
    )
    return ImportPreviewResponse.model_validate(result)


@router.post("/confirm", response_model=ImportConfirmResponse)
def confirm_import(
    current_user: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    duplicate_policy: Annotated[str, Form()] = "SKIP_NEW",
    overrides: Annotated[str | None, Form()] = None,
) -> ImportConfirmResponse:
    """Aplica la importación en una única transacción y audita el lote.

    Revalida el archivo completo en servidor (no confía en el preview) y
    respeta el RBAC para crear proveedores/categorías nuevas.
    """
    content = _read_upload(file)
    result = ProductImportService(db).confirm(
        content,
        file.filename or "importacion.xlsx",
        duplicate_policy,
        created_by=current_user.id,
        overrides=_parse_overrides(overrides),
        user=current_user,
    )
    return ImportConfirmResponse.model_validate(result)


@router.get("/batches", response_model=ImportBatchListResponse)
def list_batches(
    _: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ImportBatchListResponse:
    """Historial de importaciones (auditoría)."""
    items, total = ProductImportService(db).list_batches(skip=skip, limit=limit)
    return ImportBatchListResponse(
        items=[
            ImportBatchResponse.model_validate(batch) for batch in items
        ],
        total=total,
        page=skip // limit + 1,
        size=limit,
    )


@router.get("/batches/{batch_id}/errors")
def download_error_report(
    batch_id: UUID,
    _: Annotated[User, Depends(require_permission("products.import"))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """XLSX descargable con las filas rechazadas de un lote."""
    content, file_name = ProductImportService(db).error_report(batch_id)
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"'
        },
    )
