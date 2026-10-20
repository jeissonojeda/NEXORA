from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Settings(Base):
    """Configuración global de la aplicación."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Moneda
    currency_code: Mapped[str] = mapped_column(String(3), default="COP")
    currency_symbol: Mapped[str] = mapped_column(String(5), default="$")
    currency_locale: Mapped[str] = mapped_column(String(10), default="es-CO")
    decimal_places: Mapped[int] = mapped_column(Integer, default=2)
    use_thousand_separator: Mapped[bool] = mapped_column(Boolean, default=True)

    # Datos de negocio
    business_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_address: Mapped[str | None] = mapped_column(String(250), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Razón social y textos libres del encabezado/pie (migración 0014).
    business_legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Impresión
    printer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    paper_width: Mapped[Literal["58mm", "80mm", "A4", "A5", "TICKET"]] = mapped_column(
        String(10), default="80mm"
    )
    print_copies: Mapped[int] = mapped_column(Integer, default=1)
    print_font_size: Mapped[str] = mapped_column(String(10), default="12px")
    print_show_logo: Mapped[bool] = mapped_column(Boolean, default=True)
    print_show_contact: Mapped[bool] = mapped_column(Boolean, default=True)
    print_show_tax_id: Mapped[bool] = mapped_column(Boolean, default=False)
    print_footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Personalización del comprobante (migración 0014).
    print_logo_size: Mapped[str | None] = mapped_column(String(10), nullable=True)
    print_logo_align: Mapped[str | None] = mapped_column(String(10), nullable=True)
    print_show_company_name: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_nit: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_address: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_phone: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_email: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_city: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_city: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_header_text: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_additional_info: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_legal_footer: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_customer_info: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_seller: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_payment_method: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_sale_date: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_due_date: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_barcode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    print_show_unit: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_discount: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_show_tax: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    print_alignment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    print_margin_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadatos del logo persistido en disco (migración 0014).
    logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
