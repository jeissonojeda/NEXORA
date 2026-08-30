"""Cliente wrapper para OpenAI API (Fase 10).

Maneja la conexión, reintentos, timeout y errores de la API de OpenAI.
Nunca expone la API key en respuestas o logs.
"""

import logging
import time
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Límites de seguridad
MAX_RETRIES = 2
DEFAULT_TIMEOUT = 30.0


class AIClientError(Exception):
    """Error del cliente IA."""

    def __init__(self, message: str, error_code: str = "AI_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AIClient:
    """Cliente wrapper para OpenAI con manejo de errores y reintentos."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._available: bool | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise AIClientError(
                    "La API key de OpenAI no está configurada. "
                    "Configure la variable OPENAI_API_KEY en el archivo .env.",
                    error_code="AI_NOT_CONFIGURED",
                )
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=DEFAULT_TIMEOUT,
                max_retries=MAX_RETRIES,
            )
        return self._client

    def is_available(self) -> bool:
        if self._available is None:
            try:
                self._get_client()
                self._available = True
            except AIClientError:
                self._available = False
        return self._available

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Envía un mensaje y retorna la respuesta de OpenAI.

        Returns:
            dict con keys: response, model_used, tokens_used, duration_ms
        """
        client = self._get_client()
        model = model or settings.OPENAI_MODEL
        max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS

        start = time.monotonic()
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            content = completion.choices[0].message.content or ""
            tokens_used = (
                completion.usage.total_tokens if completion.usage else None
            )

            return {
                "response": content.strip(),
                "model_used": model,
                "tokens_used": tokens_used,
                "duration_ms": duration_ms,
            }

        except APITimeoutError as e:
            logger.error("OpenAI timeout: %s", e)
            raise AIClientError(
                "La consulta a OpenAI tardó demasiado. Intente de nuevo.",
                error_code="AI_TIMEOUT",
            ) from e
        except APIConnectionError as e:
            logger.error("OpenAI connection error: %s", e)
            raise AIClientError(
                "No se pudo conectar con OpenAI. Verifique su conexión a internet.",
                error_code="AI_CONNECTION_ERROR",
            ) from e
        except OpenAIError as e:
            logger.error("OpenAI API error: %s", e)
            raise AIClientError(
                f"Error de la API de OpenAI: {type(e).__name__}",
                error_code="AI_API_ERROR",
            ) from e


# Instancia singleton
ai_client = AIClient()
