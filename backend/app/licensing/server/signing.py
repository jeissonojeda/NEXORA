"""Carga de la clave privada de firma y emisión de documentos.

La clave privada SOLO se carga aquí (servicio central / herramienta
administrativa). La clave pública se expone para integrarla en la instalación
local.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.licensing.canonical import canonical_json
from app.licensing.constants import LICENSE_FORMAT
from app.licensing.keys import (
    generate_keypair_pem,
    key_id,
    load_private_key,
    load_public_key,
    sign_bytes,
)
from app.licensing.server.config import get_license_settings


class LicenseSigner:
    """Firma documentos de licencia con una clave Ed25519."""

    def __init__(self, private_pem: str, public_pem: str) -> None:
        self._private = load_private_key(private_pem)
        self._public = load_public_key(public_pem)
        self.public_key_pem = public_pem
        self.key_id = key_id(self._public)

    def sign(self, payload: dict[str, Any]) -> dict[str, Any]:
        signature = sign_bytes(self._private, canonical_json(payload))
        return {
            "format": LICENSE_FORMAT,
            "payload": payload,
            "key_id": self.key_id,
            "signature": signature,
        }


def _read_pem(inline: str, path: str) -> str:
    if inline.strip():
        return inline
    if path.strip():
        return Path(path).read_text(encoding="utf-8")
    return ""


def load_signer_from_settings() -> LicenseSigner:
    settings = get_license_settings()
    private_pem = _read_pem(
        settings.LICENSE_SIGNING_KEY_PEM, settings.LICENSE_SIGNING_KEY_PATH
    )
    public_pem = _read_pem(
        settings.LICENSE_PUBLIC_KEY_PEM, settings.LICENSE_PUBLIC_KEY_PATH
    )
    if not private_pem or not public_pem:
        raise RuntimeError(
            "Claves de firma no configuradas: defina LICENSE_SIGNING_KEY_PATH/"
            "LICENSE_PUBLIC_KEY_PATH (o los PEM en línea)."
        )
    return LicenseSigner(private_pem, public_pem)


@lru_cache
def get_signer() -> LicenseSigner:
    return load_signer_from_settings()


def reset_signer_cache() -> None:
    get_signer.cache_clear()


def write_keypair(private_path: str, public_path: str, *, overwrite: bool = False) -> None:
    """Genera un par de claves Ed25519 y las guarda en disco."""

    priv_path = Path(private_path)
    pub_path = Path(public_path)
    if not overwrite and (priv_path.exists() or pub_path.exists()):
        raise FileExistsError(
            "Las claves ya existen; use --overwrite para regenerarlas"
        )
    private_pem, public_pem = generate_keypair_pem()
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_text(private_pem, encoding="utf-8")
    pub_path.write_text(public_pem, encoding="utf-8")
    try:
        priv_path.chmod(0o600)
    except OSError:
        pass
