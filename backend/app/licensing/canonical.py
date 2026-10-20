"""Canonicalización de datos antes de firmar/verificar.

La firma debe calcularse sobre una representación determinista: mismo orden de
claves, sin espacios innecesarios y codificación UTF-8. Así, el documento
firmado en el servicio central se verifica exactamente en la instalación local.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json(data: Any) -> bytes:
    """Devuelve la representación canónica (JSON estable) en bytes UTF-8."""

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
