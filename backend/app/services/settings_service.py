from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.currencies import DEFAULT_CURRENCY_CODE, currency_info, is_supported
from app.core.exceptions import AppError
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.settings import Settings
from app.repositories.settings_repository import SettingsRepository

DEFAULT_FOOTER_TEXT = "¡Gracias por su compra!"

# Campos editables y que admiten None explícito (para "vaciar" un dato).
_NULLABLE_TEXT_FIELDS = {
    "business_name",
    "business_tax_id",
    "business_address",
    "business_phone",
    "business_email",
    "business_logo_path",
    "business_legal_name",
    "business_header_text",
    "business_additional_info",
    "printer_name",
    "print_footer_text",
    "print_logo_size",
    "print_logo_align",
    "print_alignment",
    "print_margin_mm",
}


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SettingsRepository(db)

    def _create_defaults(self) -> Settings:
        info = currency_info(DEFAULT_CURRENCY_CODE)
        settings = Settings(
            id=1,
            currency_code=DEFAULT_CURRENCY_CODE,
            currency_symbol=info["symbol"],
            currency_locale=info["locale"],
            decimal_places=info["decimals"],
            use_thousand_separator=True,
            business_name="NEXORA",
            paper_width="80mm",
            print_copies=1,
            print_font_size="12px",
            print_show_logo=True,
            print_show_contact=True,
            print_show_tax_id=False,
            print_footer_text=DEFAULT_FOOTER_TEXT,
        )
        self.repo.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_settings(self) -> Settings:
        settings = self.repo.get()
        if settings is None:
            settings = self._create_defaults()
        return settings

    def _count_transactions(self) -> int:
        sales = self.db.scalar(select(func.count()).select_from(Sale)) or 0
        purchases = self.db.scalar(select(func.count()).select_from(Purchase)) or 0
        return int(sales) + int(purchases)

    def update_settings(
        self,
        fields: dict[str, Any],
        confirm_currency_change: bool = False,
    ) -> Settings:
        settings = self.get_settings()

        new_code = fields.get("currency_code")
        if new_code is not None and new_code != settings.currency_code:
            if not is_supported(new_code):
                raise AppError(
                    status_code=422,
                    error_code="UNSUPPORTED_CURRENCY",
                    message="Moneda no soportada",
                )
            if self._count_transactions() > 0 and not confirm_currency_change:
                raise AppError(
                    status_code=409,
                    error_code="CURRENCY_CHANGE_REQUIRES_CONFIRMATION",
                    message=(
                        "Ya existen ventas o compras registradas. Cambiar la moneda "
                        "de operación cambia el significado económico de los datos "
                        "existentes. Confirma explícitamente para continuar."
                    ),
                )
            # Al cambiar de moneda, sincronizamos símbolo/locale/decimales con
            # el catálogo salvo que el usuario envíe valores explícitos.
            info = currency_info(new_code)
            fields.setdefault("currency_symbol", info["symbol"])
            fields.setdefault("currency_locale", info["locale"])
            fields.setdefault("decimal_places", info["decimals"])

        for field, value in fields.items():
            if field == "confirm_currency_change":
                continue
            if not hasattr(settings, field):
                continue
            if value is None and field not in _NULLABLE_TEXT_FIELDS:
                continue
            if isinstance(value, str):
                value = value.strip() or None
                if field == "currency_symbol" and value is None:
                    continue
            setattr(settings, field, value)

        self.db.commit()
        self.db.refresh(settings)
        return settings

    def reset_defaults(self, confirm_currency_change: bool = False) -> Settings:
        settings = self.get_settings()
        if (
            settings.currency_code != DEFAULT_CURRENCY_CODE
            and self._count_transactions() > 0
            and not confirm_currency_change
        ):
            raise AppError(
                status_code=409,
                error_code="CURRENCY_CHANGE_REQUIRES_CONFIRMATION",
                message=(
                    "Restaurar los valores predeterminados cambiaría la moneda de "
                    "operación con transacciones existentes. Confirma explícitamente."
                ),
            )
        info = currency_info(DEFAULT_CURRENCY_CODE)
        settings.currency_code = DEFAULT_CURRENCY_CODE
        settings.currency_symbol = info["symbol"]
        settings.currency_locale = info["locale"]
        settings.decimal_places = info["decimals"]
        settings.use_thousand_separator = True
        settings.business_name = "NEXORA"
        settings.business_tax_id = None
        settings.business_address = None
        settings.business_phone = None
        settings.business_email = None
        settings.business_logo_path = None
        settings.printer_name = None
        settings.paper_width = "80mm"
        settings.print_copies = 1
        settings.print_font_size = "12px"
        settings.print_show_logo = True
        settings.print_show_contact = True
        settings.print_show_tax_id = False
        settings.print_footer_text = DEFAULT_FOOTER_TEXT
        self.db.commit()
        self.db.refresh(settings)
        return settings
