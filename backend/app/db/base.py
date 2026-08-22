from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10,
}

if settings.DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    engine_kwargs["connect_args"] = {"connect_timeout": 5}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
