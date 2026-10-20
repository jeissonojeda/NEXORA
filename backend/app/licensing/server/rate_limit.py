"""Limitador de tasa en memoria para los endpoints públicos de activación.

Evita la enumeración de licencias y los intentos por fuerza bruta. Al ser en
memoria, es suficiente para un despliegue de un solo proceso; para varios nodos
se debería sustituir por Redis manteniendo la misma interfaz.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.licensing.server.config import get_license_settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Devuelve ``True`` si la petición está permitida."""

        settings = get_license_settings()
        now = time.monotonic()
        window = settings.LICENSE_RATE_LIMIT_WINDOW_SECONDS
        limit = settings.LICENSE_RATE_LIMIT_MAX_ATTEMPTS
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


rate_limiter = InMemoryRateLimiter()
