"""Cálculo de precios: utilidad sobre el costo.

Política única y centralizada para NEXORA:

- La utilidad se calcula SIEMPRE sobre el costo de compra (no sobre el precio
  de venta). ``utilidad %`` no es lo mismo que ``margen %``.
- ``precio_venta = precio_compra * (1 + utilidad / 100)``.
- La utilidad bruta por unidad es ``precio_venta - precio_compra`` (no es
  ganancia neta: no descuenta otros gastos).
- Redondeo monetario: ``ROUND_HALF_UP`` a 2 decimales (consistente con el resto
  del backend). El porcentaje se guarda con 2 decimales.
- El backend es la autoridad: recalcula/valida aunque el frontend envíe valores.
"""

from decimal import ROUND_HALF_UP, Decimal

MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")
_ONE_HUNDRED = Decimal("100")


def money(value) -> Decimal:
    """Normaliza un valor monetario a 2 decimales (ROUND_HALF_UP)."""
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_quantum() -> Decimal:
    return MONEY_QUANT


def _percent(value) -> Decimal:
    return Decimal(str(value)).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def compute_sale_price(purchase_price, profit_percent) -> Decimal:
    """Precio de venta a partir del costo y la utilidad porcentual sobre el costo."""
    purchase = money(purchase_price)
    percent = _percent(profit_percent)
    if purchase < 0:
        raise ValueError("El precio de compra no puede ser negativo")
    if percent < 0:
        raise ValueError("La utilidad no puede ser negativa")
    return money(purchase * (Decimal("1") + percent / _ONE_HUNDRED))


def compute_profit_percent(purchase_price, sale_price) -> Decimal:
    """Utilidad porcentual implícita al fijar manualmente el precio de venta."""
    purchase = money(purchase_price)
    sale = money(sale_price)
    if purchase <= 0:
        return Decimal("0.00")
    return _percent(((sale / purchase) - Decimal("1")) * _ONE_HUNDRED)


def gross_profit(purchase_price, sale_price) -> Decimal:
    """Utilidad bruta por unidad (venta - costo). No es ganancia neta."""
    return money(money(sale_price) - money(purchase_price))


def resolve_prices(
    purchase_price,
    profit_percent,
    sale_price=None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Devuelve ``(purchase, profit_percent, sale_price)`` aplicando la política.

    - Si ``sale_price`` se entrega (override manual), manda el precio y se
      recalcula el porcentaje de utilidad implícito.
    - Si no, se calcula el precio de venta desde ``profit_percent``.
    """
    purchase = money(purchase_price if purchase_price is not None else 0)
    if sale_price is not None:
        sale = money(sale_price)
        percent = compute_profit_percent(purchase, sale)
        # No se admiten porcentajes negativos (la venta bajo costo se registra
        # con utilidad 0; el precio de venta manual se respeta igualmente).
        if percent < 0:
            percent = Decimal("0.00")
        return purchase, percent, sale
    percent = _percent(profit_percent if profit_percent is not None else 0)
    sale = compute_sale_price(purchase, percent)
    return purchase, percent, sale
