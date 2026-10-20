"""Gestión del logotipo del establecimiento.

El archivo se valida por magic bytes (no por extensión), se limita a 1 MB y
se persiste con un nombre generado (nunca el nombre enviado por el cliente),
por lo que no puede escapar del directorio de subidas ni ejecutar contenido.
"""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.settings import Settings
from app.services.settings_service import SettingsService

MAX_LOGO_BYTES = 1024 * 1024  # 1 MB

# Firmas reales de archivo (magic bytes) soportadas.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SOI = b"\xff\xd8\xff"


def _detect_image_type(content: bytes) -> str | None:
    """Devuelve el MIME real detectado por magic bytes o None."""
    if content.startswith(_PNG_SIGNATURE):
        return "image/png"
    if content.startswith(_JPEG_SOI):
        return "image/jpeg"
    return None


_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


class LogoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings_service = SettingsService(db)

    def _uploads_dir(self) -> Path:
        configured = Path(get_settings().UPLOADS_DIR)
        base = configured if configured.is_absolute() else Path.cwd() / configured
        logos = base / "logos"
        logos.mkdir(parents=True, exist_ok=True)
        return logos

    def _absolute_path(self, filename: str) -> Path:
        # El nombre lo genera el servidor (uuid + ext) — sin traversal posible.
        return self._uploads_dir() / Path(filename).name

    def get_logo_file(self) -> tuple[bytes, str]:
        settings = self.settings_service.get_settings()
        if not settings.logo_filename or not settings.logo_mime_type:
            raise AppError(
                status_code=404,
                error_code="LOGO_NOT_FOUND",
                message="No hay logotipo configurado",
            )
        path = self._absolute_path(settings.logo_filename)
        if not path.is_file():
            raise AppError(
                status_code=404,
                error_code="LOGO_NOT_FOUND",
                message="El archivo de logotipo no existe",
            )
        return path.read_bytes(), settings.logo_mime_type

    def set_logo(self, content: bytes, original_name: str | None = None) -> Settings:
        if not content:
            raise AppError(
                status_code=422,
                error_code="LOGO_EMPTY",
                message="El archivo está vacío",
            )
        if len(content) > MAX_LOGO_BYTES:
            raise AppError(
                status_code=413,
                error_code="LOGO_TOO_LARGE",
                message="El logotipo supera el límite de 1 MB",
            )
        mime = _detect_image_type(content)
        if mime is None:
            raise AppError(
                status_code=422,
                error_code="LOGO_INVALID_FORMAT",
                message="Formato no permitido. Use PNG o JPEG.",
            )

        settings = self.settings_service.get_settings()
        self._delete_file_if_exists(settings.logo_filename)

        filename = f"logo-{uuid.uuid4().hex}{_EXT_BY_MIME[mime]}"
        path = self._absolute_path(filename)
        try:
            path.write_bytes(content)
        except OSError as exc:
            raise AppError(
                status_code=500,
                error_code="LOGO_WRITE_FAILED",
                message="No se pudo guardar el logotipo",
            ) from exc

        settings.logo_filename = filename
        settings.logo_mime_type = mime
        settings.logo_size_bytes = len(content)
        settings.business_logo_path = f"/api/settings/logo"
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def delete_logo(self) -> Settings:
        settings = self.settings_service.get_settings()
        self._delete_file_if_exists(settings.logo_filename)
        settings.logo_filename = None
        settings.logo_mime_type = None
        settings.logo_size_bytes = None
        settings.business_logo_path = None
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def _delete_file_if_exists(self, filename: str | None) -> None:
        if not filename:
            return
        path = self._absolute_path(filename)
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            # No es fatal: el registro en BD se actualiza igual.
            pass
