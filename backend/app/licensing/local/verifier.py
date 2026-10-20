"""Verificador local del documento firmado (solo clave pública)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.licensing.documents import verify_license_document
from app.licensing.keys import key_id, load_public_key


class LicenseVerifier:
    def __init__(self, public_pem: str) -> None:
        self.public_key_pem = public_pem
        self._public = load_public_key(public_pem)
        self.key_id = key_id(self._public)

    def verify(self, document: dict[str, Any]) -> dict[str, Any]:
        return verify_license_document(
            document, self._public, expected_key_id=self.key_id
        )


def load_verifier_from_settings() -> LicenseVerifier:
    settings = get_settings()
    public_pem = settings.LICENSE_PUBLIC_KEY_PEM.strip()
    if not public_pem and settings.LICENSE_PUBLIC_KEY_PATH.strip():
        public_pem = Path(settings.LICENSE_PUBLIC_KEY_PATH).read_text(encoding="utf-8")
    if not public_pem:
        raise RuntimeError(
            "Clave pública de licencia no configurada: defina "
            "LICENSE_PUBLIC_KEY_PATH o LICENSE_PUBLIC_KEY_PEM."
        )
    return LicenseVerifier(public_pem)


@lru_cache
def get_verifier() -> LicenseVerifier:
    return load_verifier_from_settings()


def reset_verifier_cache() -> None:
    get_verifier.cache_clear()
