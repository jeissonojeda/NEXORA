"""Ayudantes compartidos para tests de IA operativa (Fase 12).

Un cliente Gemini falso que reproduce las respuestas de ``GeminiClient.generate``
y ``GeminiClient.generate_content`` sin hacer llamadas reales a la API.
"""

from __future__ import annotations

from typing import Any

from app.ai.gemini_client import GeminiClientError


class FakeGeminiClient:
    """Cliente Gemini falso con guion de llamadas configurable.

    ``generate_script``: lista de respuestas a devolver en orden por ``generate``.
    ``vision_text``: texto a devolver desde ``generate_content``.
    """

    def __init__(
        self,
        generate_script: list[dict[str, Any]] | None = None,
        vision_text: str = "{}",
        available: bool = True,
    ) -> None:
        self.generate_script = list(generate_script or [])
        self.vision_text = vision_text
        self._available = available
        self.generate_calls = 0
        self.vision_calls = 0

    def is_available(self) -> bool:
        return self._available

    def generate(self, contents: list[Any], **kwargs: Any) -> dict[str, Any]:
        if not self._available:
            raise GeminiClientError(
                "La API key de Gemini no está configurada.",
                error_code="AI_NOT_CONFIGURED",
            )
        self.generate_calls += 1
        if self.generate_script:
            return self.generate_script.pop(0)
        return {"response": "respuesta de prueba", "function_calls": []}

    def generate_content(
        self,
        prompt: str,
        file_bytes: bytes,
        mime_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not self._available:
            raise GeminiClientError(
                "La API key de Gemini no está configurada.",
                error_code="AI_NOT_CONFIGURED",
            )
        self.vision_calls += 1
        return {"response": self.vision_text.strip()}


def fc_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Respuesta de generation con una llamada a función."""
    return {
        "response": "",
        "model_used": "gemini-2.0-flash",
        "tokens_used": 1,
        "duration_ms": 1,
        "function_calls": [{"name": name, "args": args, "id": "call-1"}],
    }


def text_response(message: str) -> dict[str, Any]:
    """Respuesta de generation solo texto (sin function calls)."""
    return {
        "response": message,
        "model_used": "gemini-2.0-flash",
        "tokens_used": 1,
        "duration_ms": 1,
        "function_calls": [],
    }
