"""Gestión de claves de firma Ed25519.

La clave privada SOLO existe en el servicio central / herramienta
administrativa. La instalación local incorpora únicamente la clave pública de
verificación. Este módulo no decide dónde se guardan las claves: solo las
carga, genera, firma y verifica.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair_pem() -> tuple[str, str]:
    """Genera un par Ed25519 y devuelve ``(private_pem, public_pem)``."""

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def load_private_key(private_pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(
        private_pem.encode("utf-8"), password=None
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("La clave privada no es Ed25519")
    return key


def load_public_key(public_pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("La clave pública no es Ed25519")
    return key


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_bytes(private_key: Ed25519PrivateKey, data: bytes) -> str:
    """Firma ``data`` y devuelve la firma en base64url."""

    return _b64url_encode(private_key.sign(data))


def verify_bytes(
    public_key: Ed25519PublicKey, data: bytes, signature: str
) -> bool:
    """Verifica una firma base64url sobre ``data``."""

    try:
        public_key.verify(_b64url_decode(signature), data)
        return True
    except Exception:
        return False


def key_id(public_key: Ed25519PublicKey) -> str:
    """Identificador corto y estable de la clave pública (para rotación).

    Se calcula sobre los bytes DER de la clave pública. NO es secreto.
    """

    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]
