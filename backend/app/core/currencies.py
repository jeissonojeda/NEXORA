"""Catálogo de monedas admitidas.

El sistema NO permite códigos de moneda arbitrarios: la moneda de operación y el
formato visual se validan contra este catálogo. La moneda por defecto de NEXORA
es el peso colombiano (COP).
"""

from typing import TypedDict


class CurrencyInfo(TypedDict):
    name: str
    symbol: str
    locale: str
    decimals: int


SUPPORTED_CURRENCIES: dict[str, CurrencyInfo] = {
    "COP": {"name": "Peso colombiano", "symbol": "$", "locale": "es-CO", "decimals": 2},
    "USD": {"name": "Dólar estadounidense", "symbol": "$", "locale": "en-US", "decimals": 2},
    "EUR": {"name": "Euro", "symbol": "€", "locale": "es-ES", "decimals": 2},
    "MXN": {"name": "Peso mexicano", "symbol": "$", "locale": "es-MX", "decimals": 2},
    "PEN": {"name": "Sol peruano", "symbol": "S/", "locale": "es-PE", "decimals": 2},
    "CLP": {"name": "Peso chileno", "symbol": "$", "locale": "es-CL", "decimals": 0},
    "ARS": {"name": "Peso argentino", "symbol": "$", "locale": "es-AR", "decimals": 2},
    "BRL": {"name": "Real brasileño", "symbol": "R$", "locale": "pt-BR", "decimals": 2},
    "CRC": {"name": "Colón costarricense", "symbol": "₡", "locale": "es-CR", "decimals": 2},
}

DEFAULT_CURRENCY_CODE = "COP"


def is_supported(code: str) -> bool:
    return code.upper() in SUPPORTED_CURRENCIES


def currency_info(code: str) -> CurrencyInfo:
    return SUPPORTED_CURRENCIES[code.upper()]
