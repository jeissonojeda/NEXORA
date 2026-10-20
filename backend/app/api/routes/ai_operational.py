"""Rutas de NEXORA AI Operativo (Fase 12).

Endpoints:
  - POST /api/ai/chat                 -> chat con herramientas (solo lectura + propuestas)
  - POST /api/ai/invoice/scan         -> escaneo de facturas (Gemini Vision)
  - POST /api/ai/action/preview       -> previsualización de una acción propuesta
  - POST /api/ai/action/confirm       -> confirmación/EJECUCIÓN (backend autoriza)
  - GET  /api/ai/history              -> historial de auditoría
  - GET  /api/ai/health               -> estado del proveedor IA
  - GET  /api/ai/tools                -> catálogo de tools

La autorización SIEMPRE se valida en backend (permisos ai.* por endpoint y por
acción); la IA nunca ejecuta writes sin confirmación.
"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.ai.gemini_client import GeminiClientError
from app.core.dependencies import require_permission
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_operational import (
    ActionConfirmRequest,
    ActionPreviewRequest,
    ActionPreviewResponse,
    ChatRequest,
    ChatResponse,
    AIHistoryResponse,
    AIHealthResponse,
    InvoiceScanResponse,
    AiToolsResponse,
)
from app.services.ai_operational_service import AIOperationalService

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    request: ChatRequest,
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    try:
        return service.chat(current_user, request.message, request.history)
    except GeminiClientError as e:
        raise AppError(
            status_code=502,
            error_code=e.error_code or "AI_API_ERROR",
            message=e.message,
        )


@router.post("/invoice/scan", response_model=InvoiceScanResponse)
def ai_invoice_scan(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("ai.invoice")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    data = file.file.read()
    try:
        return service.scan_invoice(
            user=current_user,
            file_name=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            file_bytes=data,
        )
    finally:
        file.file.close()


@router.post("/action/preview", response_model=ActionPreviewResponse)
def ai_action_preview(
    request: ActionPreviewRequest,
    current_user: User = Depends(require_permission("ai.execute")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    return service.preview_action(
        user=current_user,
        action_name=request.action_name,
        args=request.args,
        idempotency_key=request.idempotency_key,
    )


@router.post("/action/confirm")
def ai_action_confirm(
    request: ActionConfirmRequest,
    current_user: User = Depends(require_permission("ai.execute")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    return service.confirm_action(
        user=current_user,
        action_name=request.action_name,
        args=request.args,
        idempotency_key=request.idempotency_key,
    )


@router.get("/history", response_model=AIHistoryResponse)
def ai_history(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    items, total = service.list_history(current_user, skip=skip, limit=limit)
    return AIHistoryResponse(items=items, total=total)


@router.get("/health", response_model=AIHealthResponse)
def ai_health(
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db),
):
    service = AIOperationalService(db)
    return AIHealthResponse(**service.health())


@router.get("/tools", response_model=AiToolsResponse)
def ai_tools(
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db),
):
    from app.ai.tools import ACTION_TOOLS, READ_TOOLS

    return AiToolsResponse(read_tools=READ_TOOLS, action_tools=ACTION_TOOLS)
