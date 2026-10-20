"""Formato versionado de los documentos firmados de licencia.

Documento de licencia (firmado por el servicio central)::

    {
      "format": "nexora-license-v1",
      "payload": { ...campos autorizados... },
      "key_id": "<id de la clave pública>",
      "signature": "<base64url de la firma Ed25519 sobre canonical(payload)>"
    }

Solicitud de activación manual (generada por la instalación local, SIN firma)::

    { "format": "nexora-activation-request-v1", ...campos... }

La solicitud se codifica en base64url para que el cliente la pueda copiar/pegar
o exportar como archivo de texto.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from app.licensing.canonical import canonical_json
from app.licensing.constants import LICENSE_FORMAT, REQUEST_FORMAT
from app.licensing.errors import (
    FORMAT_MISMATCH,
    INVALID_DOCUMENT,
    INVALID_SIGNATURE,
    LicenseError,
)
from app.licensing.keys import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
    key_id,
    sign_bytes,
    verify_bytes,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_license_payload(
    *,
    license_id: str,
    license_key: str,
    customer_name: str,
    plan_code: str,
    license_type: str,
    issued_at: str | None = None,
    activated_at: str | None = None,
    expires_at: str | None = None,
    grace_days: int = 0,
    updates_until: str | None = None,
    max_installations: int = 1,
    features: list[str] | None = None,
    min_version: str | None = None,
    max_version: str | None = None,
    installation_id: str | None = None,
    installation_fingerprint: str | None = None,
    nonce: str | None = None,
    issued_by: str = "nexora-central",
) -> dict[str, Any]:
    """Construye el payload autorizado (sin firmar) de una licencia."""

    return {
        "license_id": license_id,
        "license_key": license_key,
        "customer_name": customer_name,
        "plan_code": plan_code,
        "license_type": license_type,
        "issued_at": issued_at or _utc_now_iso(),
        "activated_at": activated_at,
        "expires_at": expires_at,
        "grace_days": grace_days,
        "updates_until": updates_until,
        "max_installations": max_installations,
        "features": sorted(features or []),
        "min_version": min_version,
        "max_version": max_version,
        "installation_id": installation_id,
        "installation_fingerprint": installation_fingerprint,
        "nonce": nonce,
        "issued_by": issued_by,
    }


def sign_license_document(
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    *,
    public_key: Ed25519PublicKey | None = None,
) -> dict[str, Any]:
    """Firma un payload y devuelve el documento de licencia completo."""

    signature = sign_bytes(private_key, canonical_json(payload))
    kid = key_id(public_key) if public_key is not None else key_id(
        private_key.public_key()
    )
    return {
        "format": LICENSE_FORMAT,
        "payload": payload,
        "key_id": kid,
        "signature": signature,
    }


def verify_license_document(
    document: dict[str, Any],
    public_key: Ed25519PublicKey,
    *,
    expected_key_id: str | None = None,
) -> dict[str, Any]:
    """Verifica el documento y devuelve su payload.

    Rechaza documentos alterados, malformados o firmados con otra clave.
    """

    if not isinstance(document, dict):
        raise LicenseError(INVALID_DOCUMENT, "Documento de licencia inválido")

    if document.get("format") != LICENSE_FORMAT:
        raise LicenseError(FORMAT_MISMATCH, "Formato de licencia no soportado")

    payload = document.get("payload")
    signature = document.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise LicenseError(INVALID_DOCUMENT, "Documento de licencia incompleto")

    if expected_key_id is not None and document.get("key_id") != expected_key_id:
        # Clave desconocida: no confiamos en el documento.
        from app.licensing.errors import UNKNOWN_KEY

        raise LicenseError(UNKNOWN_KEY, "La licencia fue firmada con otra clave")

    if not verify_bytes(public_key, canonical_json(payload), signature):
        raise LicenseError(INVALID_SIGNATURE, "Firma de licencia inválida")

    return payload


# ----------------------------------------------------------------------
# Solicitud de activación manual
# ----------------------------------------------------------------------
def build_activation_request(
    *,
    license_key: str,
    installation_id: str,
    fingerprint: str,
    nonce: str,
    app_version: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "format": REQUEST_FORMAT,
        "license_key": license_key,
        "installation_id": installation_id,
        "fingerprint": fingerprint,
        "nonce": nonce,
        "app_version": app_version,
        "created_at": created_at or _utc_now_iso(),
    }


def encode_activation_request(request: dict[str, Any]) -> str:
    """Codifica la solicitud como texto base64url exportable."""

    raw = canonical_json(request)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def encode_license_document(document: dict[str, Any]) -> str:
    """Codifica un documento firmado como texto base64url transportable."""

    raw = canonical_json(document)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_license_document(code: str) -> dict[str, Any]:
    """Decodifica un documento firmado desde su representación base64url."""

    try:
        padding = "=" * (-len(code.strip()) % 4)
        raw = base64.urlsafe_b64decode(code.strip() + padding)
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise LicenseError(
            INVALID_DOCUMENT, "Documento de licencia ilegible"
        ) from exc
    if not isinstance(data, dict) or data.get("format") != LICENSE_FORMAT:
        raise LicenseError(FORMAT_MISMATCH, "Formato de licencia no soportado")
    return data


def decode_activation_request(code: str) -> dict[str, Any]:
    """Decodifica y valida el formato de una solicitud de activación."""

    try:
        padding = "=" * (-len(code.strip()) % 4)
        raw = base64.urlsafe_b64decode(code.strip() + padding)
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - se traduce a error de dominio
        raise LicenseError(
            INVALID_DOCUMENT, "Solicitud de activación ilegible"
        ) from exc

    if not isinstance(data, dict) or data.get("format") != REQUEST_FORMAT:
        raise LicenseError(FORMAT_MISMATCH, "Formato de solicitud no soportado")
    for field in ("license_key", "installation_id", "fingerprint", "nonce"):
        if not data.get(field):
            raise LicenseError(INVALID_DOCUMENT, "Solicitud de activación incompleta")
    return data
