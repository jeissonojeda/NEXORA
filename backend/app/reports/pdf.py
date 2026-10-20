"""Generación de documentos PDF para reportes.

Usa reportlab (tecnología definida en docs/ARCHITECTURE.md §2). El
documento incluye: título del reporte, fecha/hora de generación, filtros
aplicados, tabla legible y fila(s) de totales. Es un renderizador
genérico: no conoce dominio de negocio, solo recibe columnas/filas/
totales desde ReportService.
"""

import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_HEADER_BG = colors.HexColor("#1e3a8a")
_ZEBRA_BG = colors.HexColor("#f1f5f9")


def build_pdf(
    title: str,
    generated_at: datetime,
    filters_applied: list[tuple[str, str]],
    column_labels: list[str],
    rows: list[list[object]],
    totals_rows: list[tuple[str, list[object]]],
) -> bytes:
    """Construye el PDF completo y retorna los bytes.

    - ``column_labels``: encabezados en orden.
    - ``rows``: filas de datos ya formateadas como texto.
    - ``totals_rows``: pares (etiqueta, valores alineados a columnas).
      La primera celda lleva la etiqueta (ej. "TOTALES"); las celdas
      restantes corresponden una a una a las columnas desde la segunda
      en adelante (cadenas vacías cuando no aplica).
    """
    wide = len(column_labels) > 6
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter) if wide else letter,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=2,
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#475569"),
    )

    story: list[object] = [
        Paragraph(title, title_style),
        Paragraph(
            f"Generado: {generated_at.strftime('%d/%m/%Y %H:%M')}",
            subtitle_style,
        ),
    ]
    if filters_applied:
        applied = " · ".join(
            f"{label}: {value}" if value else label
            for label, value in filters_applied
        )
        story.append(Paragraph(f"Filtros: {applied}", subtitle_style))
    story.append(Spacer(1, 6 * mm))

    table_data: list[list[object]] = [list(column_labels)]
    table_data.extend(rows)
    table_data.extend([[""] * len(column_labels)] if totals_rows else [])

    table = Table(table_data, repeatRows=1)
    style_commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, _ZEBRA_BG]),
    ]
    first_total_row = len(table_data) - len(totals_rows)
    for offset in range(len(totals_rows)):
        row_index = first_total_row + offset
        style_commands.extend(
            [
                ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, row_index), (-1, row_index), "Helvetica-Bold"),
                ("LINEABOVE", (0, row_index), (-1, row_index), 0.8, _HEADER_BG),
            ]
        )
    table.setStyle(TableStyle(style_commands))
    story.append(table)

    doc.build(story)
    return buffer.getvalue()


def format_money(
    value: Decimal | float | int | None,
    symbol: str | None = None,
    decimals: int = 2,
) -> str:
    """Formato monetario legible para tablas del documento.

    Si se indica ``symbol`` (p. ej. ``$``) se antepone al monto; de lo
    contrario se conserva el formato numérico con separador de miles.
    """
    if value is None:
        return "-"
    amount = Decimal(str(value))
    rendered = f"{amount:,.{max(decimals, 0)}f}"
    return f"{symbol} {rendered}" if symbol else rendered


def format_text(value: object) -> str:
    if value is None:
        return "-"
    return str(value)


def format_datetime_value(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")


def format_date_only(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y")
