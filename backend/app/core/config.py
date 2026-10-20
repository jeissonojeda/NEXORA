import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "Sistema de Facturación e Inventario con IA"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sistema_facturacion"

    SECRET_KEY: str = "change-this-to-a-strong-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2000

    # Google Gemini (Fase 12 - NEXORA AI Operativo)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TIMEOUT: float = 60.0

    CORS_ORIGINS: str = '["http://localhost:5173"]'

    # Licenciamiento (Fase 13 - producto comercial)
    LICENSE_SERVER_URL: str = "http://localhost:8100"
    LICENSE_PUBLIC_KEY_PATH: str = ""
    LICENSE_PUBLIC_KEY_PEM: str = ""
    LICENSE_ENFORCEMENT_ENABLED: bool = False
    LICENSE_APP_VERSION: str = "1.0.0"
    LICENSE_HTTP_TIMEOUT: float = 15.0
    # Solo para pruebas/despliegues controlados: fuerza la huella de máquina.
    LICENSE_FINGERPRINT: str = ""

    # Directorio para archivos subidos (logos, etc.). Relativo a backend/.
    UPLOADS_DIR: str = "uploads"

    @property
    def cors_origins_list(self) -> list[str]:
        return json.loads(self.CORS_ORIGINS)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_license_enforcement_enabled(self) -> bool:
        return self.is_production or self.LICENSE_ENFORCEMENT_ENABLED


@lru_cache
def get_settings() -> Settings:
    return Settings()
