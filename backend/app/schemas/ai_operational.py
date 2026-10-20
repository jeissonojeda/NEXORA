"""Schemas de NEXORA AI Operativo (Fase 12).

Cubren: chat con herramientas, propuesta/confirmación de acciones (AI nunca
ejecuta writes sin confirmación), escaneo de facturas (Gemini Vision),
historial de auditoría, salud y catálogo de tools.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ----------------------------------------------------------------------
# Chat
# ----------------------------------------------------------------------
class ChatMessage(BaseModel):
    """Turno previo de la conversación (contexto para referencias)."""

    role: str = Field(..., pattern="^(user|assistant)$")
    text: str = Field(..., max_length=5000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Turnos previos para mantener el contexto de la conversación",
    )


class ToolResult(BaseModel):
    name: str
    output: Any = None
    error: str | None = None


class ActionProposal(BaseModel):
    action_name: str
    action_type: str
    args: dict[str, Any]
    permission: str


class ChatResponse(BaseModel):
    message: str
    tool_results: list[ToolResult] = []
    action_proposals: list[ActionProposal] = []
    model_used: str | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None


# ----------------------------------------------------------------------
# Acciones (preview / confirm)
# ----------------------------------------------------------------------
class ActionPreviewRequest(BaseModel):
    action_name: str = Field(..., description="nombre de la tool de acción")
    args: dict[str, Any] = Field(..., description="argumentos validados de la acción")
    idempotency_key: str | None = Field(None, max_length=100)


class ActionPreviewResponse(BaseModel):
    action_type: str
    action_name: str
    display: dict[str, Any] = Field(..., description="resumen legible de la acción")
    args: dict[str, Any]
    requires_confirmation: bool = True
    idempotency_key: str | None = None


class ActionConfirmRequest(BaseModel):
    action_name: str = Field(..., description="nombre de la tool de acción")
    args: dict[str, Any] = Field(..., description="argumentos validados de la acción")
    idempotency_key: str = Field(..., min_length=1, max_length=100)


class ActionConfirmResponse(BaseModel):
    status: str = "CONFIRMED"
    action_type: str
    action_name: str
    result: dict[str, Any]
    idempotency_key: str
    reference_id: str | None = None


# ----------------------------------------------------------------------
# Escaneo de facturas
# ----------------------------------------------------------------------
class InvoiceItem(BaseModel):
    product_name: str = ""
    quantity: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class SupplierMatch(BaseModel):
    id: UUID
    name: str
    confidence: float = 0.0


class ProductMatch(BaseModel):
    id: UUID
    name: str
    barcode: str | None = None
    confidence: float = 0.0


class InvoiceScanResponse(BaseModel):
    scan_id: UUID
    file_name: str | None = None
    supplier_name: str | None = None
    invoice_number: str | None = None
    total: Decimal | None = None
    items: list[InvoiceItem] = []
    supplier_matches: list[SupplierMatch] = []
    product_matches: list[ProductMatch] = []
    duplicate: bool = False
    duplicate_of: UUID | None = None
    raw_text: str | None = None


# ----------------------------------------------------------------------
# Historial de auditoría
# ----------------------------------------------------------------------
class AIHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action_type: str
    action_name: str
    status: str
    payload_json: str | None = None
    result_json: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    idempotency_key: str | None = None
    created_at: datetime


class AIHistoryResponse(BaseModel):
    items: list[AIHistoryItem]
    total: int


# ----------------------------------------------------------------------
# Salud y catálogo de tools
# ----------------------------------------------------------------------
class AIHealthResponse(BaseModel):
    available: bool
    model: str | None = None


class AiToolsResponse(BaseModel):
    read_tools: list[dict[str, Any]] = []
    action_tools: list[dict[str, Any]] = []
