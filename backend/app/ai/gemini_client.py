"""Cliente wrapper para Google Gemini (Fase 12 - NEXORA AI Operativo).

Maneja la conexión, timeout y errores de la API de Gemini (google-genai).
Provee tres capacidades:
  - ``generate``: bajos niveles con soporte de multi-turn tool calling y
    function responses (para loops de herramientas de solo lectura).
  - ``chat``: utilidad de un solo turno sobre ``generate``.
  - ``generate_content``: generación con entrada multimodal (texto + imagen/PDF
    como blob base64) usada para el escaneo de facturas (Gemini Vision).

Nunca expone la API key en respuestas o logs.
"""

import logging
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Límites de seguridad
MAX_INLINE_BYTES = 20 * 1024 * 1024  # 20 MB


class GeminiClientError(Exception):
    """Error del cliente Gemini."""

    def __init__(self, message: str, error_code: str = "AI_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class GeminiClient:
    """Cliente wrapper para Google Gemini con manejo de errores."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self._available: bool | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise GeminiClientError(
                    "La API key de Gemini no está configurada. "
                    "Configure la variable GEMINI_API_KEY en el archivo .env.",
                    error_code="AI_NOT_CONFIGURED",
                )
            try:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("Error creando cliente Gemini: %s", e)
                raise GeminiClientError(
                    "No se pudo inicializar el cliente de Gemini.",
                    error_code="AI_CONNECTION_ERROR",
                ) from e
        return self._client

    def is_available(self) -> bool:
        if self._available is None:
            try:
                self._get_client()
                self._available = True
            except GeminiClientError:
                self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Bajo nivel: generación con multi-turn + tool calling
    # ------------------------------------------------------------------
    def generate(
        self,
        contents: list[Any],
        model: str | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Genera contenido a partir de una lista de ``types.Content``.

        Retorna:
            dict con keys: response, model_used, tokens_used, duration_ms,
            function_calls (lista de {name, args, id}) si Gemini invoca tools.
        """
        client = self._get_client()
        model = model or settings.GEMINI_MODEL
        max_tokens = max_tokens or settings.GEMINI_MAX_TOKENS

        config: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": 0.3,
        }
        if tools:
            config["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t.get("description"),
                            parameters=self._schema_from_json_schema(
                                t.get("parameters")
                            )
                            if t.get("parameters")
                            else None,
                        )
                        for t in tools
                    ]
                )
            ]

        start = time.monotonic()
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config),
            )
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            raise GeminiClientError(
                f"Error de la API de Gemini: {type(e).__name__}",
                error_code="AI_API_ERROR",
            ) from e

        duration_ms = int((time.monotonic() - start) * 1000)

        text = ""
        function_calls: list[dict[str, Any]] = []
        if response.candidates:
            parts = (
                response.candidates[0].content.parts
                if response.candidates[0].content is not None
                else []
            )
            for part in parts:
                if part.text:
                    text += part.text
                elif part.function_call is not None:
                    call = part.function_call
                    args = call.args or {}
                    function_calls.append(
                        {
                            "name": call.name,
                            "args": dict(args),
                            "id": getattr(call, "id", None),
                        }
                    )

        tokens_used = None
        if response.usage_metadata is not None:
            tokens_used = response.usage_metadata.total_token_count

        return {
            "response": text.strip(),
            "model_used": model,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
            "function_calls": function_calls,
        }

    # ------------------------------------------------------------------
    # Chat de un solo turno (conveniencia)
    # ------------------------------------------------------------------
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Envía un mensaje de un turno a Gemini."""
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=system_prompt)],
            ),
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            ),
        ]
        return self.generate(
            contents=contents,
            model=model,
            max_tokens=max_tokens,
            tools=tools,
        )

    # ------------------------------------------------------------------
    # Multimodal (escaneo de facturas)
    # ------------------------------------------------------------------
    def generate_content(
        self,
        prompt: str,
        file_bytes: bytes,
        mime_type: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Envía texto + archivo (imagen/PDF) a Gemini Vision."""
        if len(file_bytes) > MAX_INLINE_BYTES:
            raise GeminiClientError(
                "El archivo es demasiado grande para el escaneo.",
                error_code="AI_FILE_TOO_LARGE",
            )

        client = self._get_client()
        model = model or settings.GEMINI_MODEL
        max_tokens = max_tokens or settings.GEMINI_MAX_TOKENS

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=file_bytes,
                        )
                    ),
                    types.Part(text=prompt),
                ],
            )
        ]

        config: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": 0.1,
        }

        start = time.monotonic()
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config),
            )
        except Exception as e:
            logger.error("Gemini Vision API error: %s", e)
            raise GeminiClientError(
                f"Error de la API de Gemini: {type(e).__name__}",
                error_code="AI_API_ERROR",
            ) from e

        duration_ms = int((time.monotonic() - start) * 1000)

        text = ""
        if response.candidates and response.candidates[0].content is not None:
            text = "".join(
                p.text or "" for p in response.candidates[0].content.parts
            )

        tokens_used = None
        if response.usage_metadata is not None:
            tokens_used = response.usage_metadata.total_token_count

        return {
            "response": text.strip(),
            "model_used": model,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _schema_from_json_schema(json_schema: dict[str, Any]) -> "types.Schema":
        """Convierte un JSON Schema simple a types.Schema de genai."""
        from google.genai import types as gt

        type_map = {
            "string": gt.Type.STRING,
            "integer": gt.Type.INTEGER,
            "number": gt.Type.NUMBER,
            "boolean": gt.Type.BOOLEAN,
            "array": gt.Type.ARRAY,
            "object": gt.Type.OBJECT,
        }
        props = (json_schema.get("properties") or {}).items()
        return gt.Schema(
            type=gt.Type.OBJECT,
            properties={
                name: gt.Schema(type=type_map.get(prop.get("type"), gt.Type.OBJECT))
                for name, prop in props
            },
            required=json_schema.get("required"),
        )


# Instancia singleton
gemini_client = GeminiClient()
