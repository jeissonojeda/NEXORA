from sqlalchemy.orm import Session

from app.models.settings import Settings


class SettingsRepository:
    """Acceso a la fila única de configuración global (id=1)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> Settings | None:
        return self.db.get(Settings, 1)

    def add(self, settings: Settings) -> Settings:
        self.db.add(settings)
        self.db.flush()
        return settings
