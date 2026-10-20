"""Motor de intención y extracción de entidades en español (Fase 13).

Clasificador **determinista** (sin dependencias externas ni llamadas de red)
que entiende peticiones en lenguaje natural sobre productos, inventario,
compras, proveedores, clientes, cuentas por cobrar, ventas, caja y reportes.

Se usa para dos cosas:

1. *Pre-análisis* del mensaje: produce una pista estructurada que se inyecta
   en el prompt de Gemini para mejorar la precisión (sin ejecutar nada).
2. *Respaldo local*: cuando el proveedor de IA no está configurado o no
   devuelve respuesta, el asistente puede responder con datos reales del
   sistema usando únicamente herramientas de solo lectura.

El módulo NUNCA modifica datos ni ejecuta SQL arbitrario: solo clasifica texto
y extrae entidades (nombre de producto, código de barras, cantidad, período,
proveedor, etc.).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


# ----------------------------------------------------------------------
# Intenciones
# ----------------------------------------------------------------------
class Intents:
    PRODUCT_STOCK = "product_stock"
    SEARCH_PRODUCT = "search_product"
    LOW_STOCK = "low_stock"
    INVENTORY_SUMMARY = "inventory_summary"
    SALES_SUMMARY = "sales_summary"
    PURCHASES_SUMMARY = "purchases_summary"
    SUPPLIERS = "suppliers"
    CUSTOMERS = "customers"
    RECEIVABLES = "receivables"
    CASH = "cash"
    BUSINESS_SUMMARY = "business_summary"
    ADJUST_STOCK = "adjust_stock"
    CREATE_PURCHASE = "create_purchase"
    HELP = "help"
    UNKNOWN = "unknown"


# Palabras clave por intención. Cuanto más específica (multi-palabra) sea la
# coincidencia, mayor peso tiene al puntuar.
_KEYWORDS: dict[str, list[str]] = {
    Intents.ADJUST_STOCK: [
        "ajusta el stock", "ajustar el stock", "ajuste de stock", "ajustar stock",
        "actualiza el stock", "actualizar el stock", "actualizar stock",
        "pon el stock", "poner el stock", "deja el stock", "dejar el stock",
        "cambia el stock", "cambiar el stock", "corrige el stock", "corregir stock",
        "cuadrar inventario", "cuadre de inventario", "cuadre fisico",
        "conteo fisico", "fijar stock", "setear stock", "dejar en",
    ],
    Intents.CREATE_PURCHASE: [
        "comprale a", "comprar a", "compra a", "comprale al", "comprar al",
        "orden de compra", "ordenar al proveedor", "pedir al proveedor",
        "pedido al proveedor", "abastecer", "abastecete", "reponer con",
        "surtir", "adquirir de",
    ],
    Intents.LOW_STOCK: [
        "stock bajo", "bajo stock", "poco stock", "falta stock",
        "por agotarse", "por agotar", "se estan acabando", "se estan agotando",
        "por acabarse", "a punto de agotarse", "reabastecer", "reabastecimiento",
        "reponer inventario", "necesitan reposicion", "necesita reposicion",
        "bajo minimo", "bajo el minimo", "debajo del minimo", "stock critico",
        "agotado", "agotados", "sin stock", "faltantes", "reponer",
        "que reponer", "debo reponer", "necesito reponer", "urge reponer",
    ],
    Intents.PRODUCT_STOCK: [
        "cuanto stock", "cuanto unidades", "cuantas unidades", "cuantos quedan",
        "cuanto queda", "cuanto hay", "cuanta existencia", "existencias de",
        "existencia de", "stock de", "stock del", "inventario de", "inventario del",
        "disponibilidad de", "hay de", "hay del", "hay existencias", "hay stock",
        "existencias hay", "existencia hay", "unidades quedan", "unidades hay",
        "unidades de", "stock actual",
    ],
    Intents.SEARCH_PRODUCT: [
        "busca el producto", "buscar el producto", "busca producto",
        "busca un producto", "buscame", "encuentra el producto",
        "encuentra producto", "localiza el producto", "localizar producto",
        "por codigo de barras", "codigo de barras", "barcode", "escanea",
        "precio de", "precio del", "que precio tiene", "cuanto cuesta",
        "cuanto vale", "cuanto sale", "donde esta el producto",
    ],
    Intents.SALES_SUMMARY: [
        "cuanto vendi", "cuanto se vendio", "total vendido", "resumen de ventas",
        "reporte de ventas", "movimiento de ventas", "ventas del dia",
        "ventas de la semana", "ventas del mes", "ventas de hoy", "vendi",
        "vendido", "vendimos", "facturacion", "facture", "ingresos por ventas",
        "productos mas vendidos", "mas vendidos", "ventas", "venta",
    ],
    Intents.PURCHASES_SUMMARY: [
        "reporte de compras", "resumen de compras", "cuanto compre",
        "compras del mes", "compras de la semana", "historial de compras",
        "ultimas compras", "compras recientes", "total de compras",
        "compras", "compre", "comprado",
    ],
    Intents.SUPPLIERS: [
        "busca proveedor", "buscar proveedor", "busca el proveedor",
        "lista de proveedores", "dime los proveedores", "proveedores",
        "proveedor", "suplidor", "suplidores",
    ],
    Intents.RECEIVABLES: [
        "cuentas por cobrar", "por cobrar", "saldo pendiente", "saldos pendientes",
        "quien me debe", "quienes me deben", "me deben", "deuda de", "deudas",
        "clientes morosos", "mora", "credito otorgado", "cartera vencida",
        "por pagar", "cuanto me deben",
    ],
    Intents.CUSTOMERS: [
        "busca cliente", "buscar cliente", "lista de clientes", "clientes",
        "cliente", "cartera de clientes",
    ],
    Intents.CASH: [
        "estado de caja", "cierre de caja", "apertura de caja", "arqueo de caja",
        "movimientos de caja", "dinero en caja", "efectivo en caja",
        "cuanto hay en caja", "turno de caja", "caja", "arqueo", "efectivo",
    ],
    Intents.BUSINESS_SUMMARY: [
        "como va el negocio", "estado del negocio", "resumen general",
        "panorama general", "situacion general", "balance general",
        "resumen del negocio", "informe general", "resumen", "reporte",
        "reportes", "informe",
    ],
    Intents.INVENTORY_SUMMARY: [
        "valorizacion del inventario", "valor del inventario", "valorizar",
        "cuantos productos hay", "total de productos", "salud del inventario",
        "estado del inventario", "resumen de inventario", "rotacion",
        "inventario", "existencias",
    ],
    Intents.HELP: [
        "que puedes hacer", "que sabes hacer", "cuales son tus funciones",
        "tus capacidades", "que opciones tengo", "como funcionas",
        "quien eres", "ayuda", "help", "ejemplos", "hola", "buenas",
        "buenos dias", "buenas tardes", "buenas noches", "hey",
    ],
}

# Normalizaciones de sinónimos/errores frecuentes -> término canónico.
_CANONICAL: dict[str, str] = {
    "almuacen": "almacen",
    "almacen": "almacen",
    "produto": "producto",
    "prodcuto": "producto",
    "prodocto": "producto",
    "productos": "producto",
    "articulos": "producto",
    "articulo": "producto",
    "mercancia": "producto",
    "mercaderia": "producto",
    "inventaryo": "inventario",
    "inventarios": "inventario",
    "existensias": "existencias",
    "existencia": "existencias",
    "existensia": "existencias",
    "stokc": "stock",
    "stok": "stock",
    "estok": "stock",
    "proveedr": "proveedor",
    "provehedor": "proveedor",
    "provedor": "proveedor",
    "suplidor": "proveedor",
    "suplidores": "proveedor",
    "clente": "cliente",
    "clientes": "cliente",
    "ventaz": "ventas",
    "ventas": "ventas",
    "compras": "compras",
    "facturacon": "facturacion",
    "facturacion": "facturacion",
    "kaja": "caja",
    "efectibo": "efectivo",
    "reporte": "reportes",
    "report": "reportes",
    "repote": "reportes",
    "vendi": "vendi",
    "vendido": "vendido",
    "unidadez": "unidades",
    "unidad": "unidades",
    "cuantoz": "cuantos",
    "cuanto": "cuanto",
    "cuanta": "cuanto",
    "cuantos": "cuanto",
    "cuantas": "cuanto",
    "existen": "existencias",
    "queda": "quedan",
    "quedan": "quedan",
}

_WORD_RE = re.compile(r"[a-z0-9]+")

_DAYS_RE = re.compile(r"(?:ultimos?|ultimas?|pasados?|ultimo|ultima)\s+(\d{1,3})\s*dias?")
_SINCE_RE = re.compile(r"(\d{1,3})\s*dias?")
_BARCODE_RE = re.compile(r"\b(\d{6,14})\b")
_QTY_RE = re.compile(r"\b(\d{1,6})\b")

# Sintagmas de consulta de producto (sobre texto normalizado).
_PRODUCT_PATTERNS = [
    re.compile(r"(?:existencias|stock|inventario|disponibilidad)\s+(?:de|del|para)\s+(.+)"),
    re.compile(r"(?:hay|tienen?|tiene|queda)\s+(?:de\s+|del\s+)?(.+)"),
    re.compile(r"(?:precio|valor|costo)\s+(?:de|del|para)\s+(.+)"),
    re.compile(r"(?:busca|buscame|buscar|encuentra|localiza|localizar)\s+(?:el\s+|un\s+|una\s+|la\s+)?(?:producto|articulo)?\s*(.+)"),
    re.compile(r"(?:cuanto\s+)?(?:cuesta|vale|sale)\s+(?:el\s+|la\s+)?(.+)"),
    re.compile(r"(?:de|del)\s+([a-z0-9][a-z0-9 ]{1,40}?)(?:\s+a\s+\d+|\s+por favor|\s+ahora|\s+gracias)?$"),
]

# Palabras vacías que se eliminan al limpiar un nombre de producto.
_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "para", "por", "con", "sin", "y", "o", "que", "cual", "cuanto", "cuanta",
    "cuantos", "cuantas", "hay", "tiene", "tienen", "tengo", "queda", "quedan",
    "producto", "articulo", "productos", "articulos", "stock", "existencias",
    "inventario", "disponibilidad", "actual", "ahora", "por", "favor", "gracias",
    "unidad", "unidades", "cuantos", "cuanta", "cuantas", "quedan", "queda",
    "dias", "dia", "semana", "semanas", "mes", "meses", "hoy", "ayer", "ultimo",
    "ultima", "ultimos", "ultimas", "reporte", "reportes", "resumen", "estado",
    "busca", "buscar", "buscame", "encuentra", "localiza", "localizar", "dime",
    "muestra", "muestrame", "ver", "lista", "sobre", "que", "me", "mi", "su",
    "proveedor", "proveedores", "cliente", "clientes", "caja", "ventas", "venta",
    "compras", "compra", "precio", "cuesta", "vale", "sale",
}


def strip_accents(text: str) -> str:
    """Elimina tildes/acentos conservando el resto del texto."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Normaliza a minúsculas, sin acentos y con sinónimos canónicos."""
    lowered = strip_accents(text.lower())
    lowered = lowered.replace("ñ", "n")
    tokens = _WORD_RE.findall(lowered)
    canonical = [_CANONICAL.get(tok, tok) for tok in tokens]
    return " ".join(canonical)


@dataclass
class IntentResult:
    intent: str
    confidence: float
    entities: dict[str, object] = field(default_factory=dict)
    matched_keywords: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification: str | None = None

    @property
    def hint(self) -> str:
        """Pista compacta para inyectar en el prompt del modelo."""
        parts = [f"intencion={self.intent}", f"confianza={self.confidence:.2f}"]
        if self.entities:
            ents = ", ".join(f"{k}={v}" for k, v in self.entities.items() if v)
            if ents:
                parts.append(f"entidades({ents})")
        return "; ".join(parts)


def _score_keywords(norm: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    scores: dict[str, int] = {intent: 0 for intent in _KEYWORDS}
    matched: dict[str, list[str]] = {intent: [] for intent in _KEYWORDS}
    for intent, keywords in _KEYWORDS.items():
        for kw in keywords:
            if not kw:
                continue
            if kw in norm:
                score = 2 + kw.count(" ")
                scores[intent] += score
                matched[intent].append(kw)
    return scores, matched


def extract_days(norm: str) -> int | None:
    """Extrae el período en días de expresiones como 'últimos 30 días'."""
    if "hoy" in norm or "del dia" in norm:
        return 1
    if "esta semana" in norm or "de la semana" in norm or "semana" in norm:
        return 7
    if "este mes" in norm or "del mes" in norm or "mes" in norm:
        return 30
    m = _DAYS_RE.search(norm) or _SINCE_RE.search(norm)
    if m:
        try:
            value = int(m.group(1))
            return max(1, min(value, 365))
        except ValueError:
            return None
    return None


def extract_barcode(norm: str) -> str | None:
    m = _BARCODE_RE.search(norm)
    return m.group(1) if m else None


def extract_product_query(original: str, norm: str) -> str | None:
    """Extrae un nombre/código candidato de producto."""
    barcode = extract_barcode(norm)
    if barcode:
        return barcode
    for pattern in _PRODUCT_PATTERNS:
        m = pattern.search(norm)
        if not m:
            continue
        candidate = _clean_candidate(m.group(1))
        if candidate:
            return candidate
    # Último recurso: tokens significativos que no son palabras vacías.
    return _clean_candidate(norm)


def _clean_candidate(candidate: str) -> str | None:
    """Quita "a N"/"en N" y tokens numéricos o vacíos de un nombre candidato."""
    candidate = re.split(r"\s+(?:a|en)\s+\d+\b", candidate)[0]
    tokens = [
        t
        for t in _WORD_RE.findall(candidate)
        if t not in _STOPWORDS and not t.isdigit() and len(t) >= 2
    ]
    if tokens:
        return " ".join(tokens)[:80]
    return None


def extract_quantity(original: str, norm: str) -> int | None:
    """Extrae una cantidad/stock numérico (ignorando códigos de barras)."""
    if extract_barcode(norm):
        norm = _BARCODE_RE.sub(" ", norm)
    m = _QTY_RE.search(norm)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def classify(text: str) -> IntentResult:
    """Clasifica una petición en español y extrae sus entidades."""
    norm = normalize(text)
    if not norm.strip():
        return IntentResult(
            intent=Intents.UNKNOWN,
            confidence=0.0,
            needs_clarification=True,
            clarification=HELP_MESSAGE,
        )

    scores, matched = _score_keywords(norm)
    entities: dict[str, object] = {}

    # --- Overrides / heurísticas ---
    barcode = extract_barcode(norm)
    days = extract_days(norm)
    quantity = extract_quantity(text, norm)

    # "ajustar stock de X a N" gana sobre una simple consulta.
    if re.search(r"(?:stock|inventario|existencias)", norm) and re.search(
        r"\b(?:a|en)\s+\d", norm
    ):
        scores[Intents.ADJUST_STOCK] += 4

    # Comprar a un proveedor concreto => acción, no resumen.
    if re.search(r"\b(?:comprar|compra|comprale|adquirir|ordenar|pedir)\b", norm) and re.search(
        r"\ba\s+(?:l\s+)?(?:proveedor|suplidor|[a-z]{3,})", norm
    ):
        scores[Intents.CREATE_PURCHASE] += 4

    # "clientes con deuda" => cuentas por cobrar.
    if "cliente" in norm and re.search(r"\b(deuda|deudas|debe|deben|mora|saldo)\b", norm):
        scores[Intents.RECEIVABLES] += 3

    # "compras a proveedores" (consulta) no debe convertirse en acción.
    if Intents.SUPPLIERS in matched and scores[Intents.SUPPLIERS] > 0:
        entities["supplier_query"] = extract_product_query(text, norm)

    # "hay <producto>" sin verbo explícito => consulta de existencias.
    if max(scores.values()) == 0 and re.search(r"\bhay\b", norm):
        scores[Intents.PRODUCT_STOCK] = 1

    best_intent = max(scores, key=lambda k: (scores[k], len(matched[k])))
    best_score = scores[best_intent]

    if best_score == 0:
        greeting = re.search(r"\b(hola|buenas|buenos|hey|saludos)\b", norm)
        intent = Intents.HELP if greeting else Intents.UNKNOWN
        return IntentResult(intent=intent, confidence=0.2)

    confidence = min(0.95, 0.35 + 0.12 * best_score)

    # Entidades aplicables según intención.
    if best_intent in {
        Intents.PRODUCT_STOCK,
        Intents.SEARCH_PRODUCT,
        Intents.ADJUST_STOCK,
        Intents.CREATE_PURCHASE,
    }:
        product_query = extract_product_query(text, norm)
        if product_query:
            entities["product_query"] = product_query
        if days:
            entities["days"] = days
        if best_intent in {Intents.ADJUST_STOCK, Intents.CREATE_PURCHASE} and quantity:
            entities["quantity"] = quantity

    if best_intent in {Intents.SALES_SUMMARY, Intents.PURCHASES_SUMMARY, Intents.BUSINESS_SUMMARY}:
        if days:
            entities["days"] = days

    if best_intent == Intents.CUSTOMERS:
        customer_query = extract_product_query(text, norm)
        if customer_query:
            entities["customer_query"] = customer_query

    if barcode:
        entities["barcode"] = barcode

    return IntentResult(
        intent=best_intent,
        confidence=confidence,
        entities=entities,
        matched_keywords=matched[best_intent][:5],
    )


HELP_MESSAGE = (
    "Puedo ayudarte con productos, inventario, compras, proveedores, clientes, "
    "cuentas por cobrar, ventas, caja y reportes. Prueba, por ejemplo:\n"
    "• ¿Cuánto stock queda de leche?\n"
    "• ¿Qué productos tienen stock bajo?\n"
    "• ¿Cuánto vendí en los últimos 7 días?\n"
    "• Muéstrame las cuentas por cobrar pendientes\n"
    "• Estado de caja de hoy\n"
    "• Ajusta el stock de arroz a 50 (te pediré confirmación)\n\n"
    "Si no sabes qué pedir, dime el área que te interesa y te propongo opciones."
)
