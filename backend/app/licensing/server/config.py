"""Configuración del servicio central de licencias.

Usa variables de entorno con prefijo ``LICENSE_`` y un archivo ``.env``
opcional. No reutiliza la configuración de la instalación local.
"""

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LicenseServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LICENSE_APP_ENV: str = "development"
    LICENSE_DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/nexora_licenses"
    )

    # Claves Ed25519. Preferir rutas a archivos fuera del repositorio.
    LICENSE_SIGNING_KEY_PATH: str = ""
    LICENSE_PUBLIC_KEY_PATH: str = ""
    LICENSE_SIGNING_KEY_PEM: str = ""
    LICENSE_PUBLIC_KEY_PEM: str = ""

    # Autenticación del panel administrativo global (propietario de NEXORA).
    LICENSE_JWT_SECRET: str = "change-this-license-jwt-secret"
    LICENSE_ALGORITHM: str = "HS256"
    LICENSE_ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # Límite de intentos de activación (anti fuerza bruta / enumeración).
    LICENSE_RATE_LIMIT_MAX_ATTEMPTS: int = 10
    LICENSE_RATE_LIMIT_WINDOW_SECONDS: int = 300

    LICENSE_CORS_ORIGINS: str = '["http://localhost:5174"]'

    @property
    def is_production(self) -> bool:
        return self.LICENSE_APP_ENV == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return json.loads(self.LICENSE_CORS_ORIGINS)


@lru_cache
def get_license_settings() -> LicenseServerSettings:
    return LicenseServerSettings()
