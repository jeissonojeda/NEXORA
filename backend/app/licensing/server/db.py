"""Base de datos propia del servicio central de licencias.

Deliberadamente separada de ``app.db.base`` para no compartir metadatos ni
migraciones con la base de datos del supermercado.
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.licensing.server.config import get_license_settings

settings = get_license_settings()

engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if settings.LICENSE_DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    engine_kwargs.update({"pool_size": 5, "max_overflow": 10})
    engine_kwargs["connect_args"] = {"connect_timeout": 5}

engine = create_engine(settings.LICENSE_DATABASE_URL, **engine_kwargs)
LicenseSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class LicenseBase(DeclarativeBase):
    pass


def get_license_db() -> Generator[Session, None, None]:
    db = LicenseSessionLocal()
    try:
        yield db
    finally:
        db.close()
