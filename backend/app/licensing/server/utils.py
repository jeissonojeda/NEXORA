"""Utilidades internas del servicio central."""

from __future__ import annotations

import hashlib
import json
import secrets
import string
from datetime import datetime, timezone

_KEY_ALPHABET = string.ascii_uppercase + string.digits


def generate_license_key() -> str:
    """Genera un código público de licencia legible (``NEXORA-XXXX-...``)."""

    groups = ["".join(secrets.choice(_KEY_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "NEXORA-" + "-".join(groups)


def hash_fingerprint(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.strip().encode("utf-8")).hexdigest()


def hash_text(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def to_utc(value: datetime | None) -> datetime | None:
    """Normaliza a ``datetime`` con zona UTC (SQLite devuelve naive)."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
