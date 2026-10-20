"""Huella de máquina de la instalación local.

La huella combina varios atributos estables del equipo. No se usa la MAC sola
(es trivial de falsear): se mezclan sistema, arquitectura, nombre y un
identificador de nodo, y se resume con SHA-256. Copiar la carpeta de la
aplicación a otro equipo produce una huella distinta, lo que obliga a una
reactivación legítima.
"""

from __future__ import annotations

import hashlib
import platform
import uuid

from app.core.config import get_settings


def _machine_components() -> list[str]:
    return [
        platform.system(),
        platform.machine(),
        platform.node(),
        str(uuid.getnode()),
        platform.platform(),
    ]


def machine_fingerprint() -> str:
    """Devuelve la huella cruda (puede sobrescribirse con LICENSE_FINGERPRINT)."""

    override = get_settings().LICENSE_FINGERPRINT.strip()
    if override:
        return override
    raw = "|".join(_machine_components())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_hash(fingerprint: str) -> str:
    """Hash que se firma y se compara (nunca se almacena la huella cruda)."""

    return hashlib.sha256(fingerprint.strip().encode("utf-8")).hexdigest()


def machine_label() -> str:
    return f"{platform.node()} ({platform.system()} {platform.machine()})"
