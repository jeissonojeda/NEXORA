from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.currencies import SUPPORTED_CURRENCIES, is_supported

PAPER_WIDTHS = ("58mm", "80mm", "A4", "A5", "TICKET")


class SettingsCurrencyOut(BaseModel):
    code: str
    name: str
    symbol: str
    locale: str
    decimals: int


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency_code: str
    currency_symbol: str
    currency_locale: str
    decimal_places: int
    use_thousand_separator: bool

    business_name: str | None
    business_tax_id: str | None
    business_address: str | None
    business_phone: str | None
    business_email: str | None
    business_logo_path: str | None
    business_legal_name: str | None
    business_header_text: str | None
    business_additional_info: str | None

    printer_name: str | None
    paper_width: str
    print_copies: int
    print_font_size: str
    print_show_logo: bool
    print_show_contact: bool
    print_show_tax_id: bool
    print_footer_text: str | None

    print_logo_size: str | None
    print_logo_align: str | None
    print_show_company_name: bool
    print_show_nit: bool
    print_show_address: bool
    print_show_phone: bool
    print_show_email: bool
    print_show_city: bool
    print_show_header_text: bool
    print_show_additional_info: bool
    print_show_legal_footer: bool
    print_show_customer_info: bool
    print_show_seller: bool
    print_show_payment_method: bool
    print_show_sale_date: bool
    print_show_due_date: bool
    print_show_barcode: bool
    print_show_unit: bool
    print_show_discount: bool
    print_show_tax: bool
    print_alignment: str | None
    print_margin_mm: int | None

    logo_filename: str | None
    logo_mime_type: str | None
    logo_size_bytes: int | None

    updated_at: datetime


class SettingsUpdate(BaseModel):
    currency_code: str | None = None
    currency_symbol: str | None = Field(default=None, max_length=5)
    currency_locale: str | None = Field(default=None, max_length=10)
    decimal_places: int | None = Field(default=None, ge=0, le=4)
    use_thousand_separator: bool | None = None

    business_name: str | None = Field(default=None, max_length=150)
    business_tax_id: str | None = Field(default=None, max_length=50)
    business_address: str | None = Field(default=None, max_length=250)
    business_phone: str | None = Field(default=None, max_length=50)
    business_email: str | None = Field(default=None, max_length=100)
    business_logo_path: str | None = Field(default=None, max_length=255)
    business_legal_name: str | None = Field(default=None, max_length=255)
    business_header_text: str | None = None
    business_additional_info: str | None = None

    printer_name: str | None = Field(default=None, max_length=150)
    paper_width: Literal["58mm", "80mm", "A4", "A5", "TICKET"] | None = None
    print_copies: int | None = Field(default=None, ge=1, le=10)
    print_font_size: str | None = Field(default=None, max_length=10)
    print_show_logo: bool | None = None
    print_show_contact: bool | None = None
    print_show_tax_id: bool | None = None
    print_footer_text: str | None = None

    print_logo_size: Literal["small", "medium", "large"] | None = None
    print_logo_align: Literal["left", "center", "right"] | None = None
    print_show_company_name: bool | None = None
    print_show_nit: bool | None = None
    print_show_address: bool | None = None
    print_show_phone: bool | None = None
    print_show_email: bool | None = None
    print_show_city: bool | None = None
    print_show_header_text: bool | None = None
    print_show_additional_info: bool | None = None
    print_show_legal_footer: bool | None = None
    print_show_customer_info: bool | None = None
    print_show_seller: bool | None = None
    print_show_payment_method: bool | None = None
    print_show_sale_date: bool | None = None
    print_show_due_date: bool | None = None
    print_show_barcode: bool | None = None
    print_show_unit: bool | None = None
    print_show_discount: bool | None = None
    print_show_tax: bool | None = None
    print_alignment: Literal["left", "center", "right"] | None = None
    print_margin_mm: int | None = Field(default=None, ge=0, le=30)

    # Requerido para cambiar la moneda de operación cuando ya existen
    # transacciones (ventas/compras). El backend lo exige y advierte.
    confirm_currency_change: bool = False

    @field_validator("currency_code")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.upper()
        if not is_supported(code):
            raise ValueError(
                "Moneda no soportada. Opciones: "
                + ", ".join(sorted(SUPPORTED_CURRENCIES.keys()))
            )
        return code
