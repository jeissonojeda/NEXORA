"""Tests del motor de intención en español y del asistente local (Fase 13)."""

import pytest
from sqlalchemy.orm import Session

from app.ai import intent as intent_engine
from app.ai.intent import Intents, classify, normalize
from app.ai.local_assistant import LocalAssistant
from app.services.ai_operational_service import AIOperationalService
from tests.fakes import FakeGeminiClient


# ----------------------------------------------------------------------
# Normalización
# ----------------------------------------------------------------------
def test_normalize_strips_accents_and_canonicalizes_typos():
    assert "producto" in normalize("Prodúcto")
    assert normalize("Almacén") == "almacen"
    norm = normalize("cuántos Artículos hay")
    assert "á" not in norm and "producto" in norm


# ----------------------------------------------------------------------
# Clasificación de intenciones (distintas formulaciones en español)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("¿cuánto stock queda de leche?", Intents.PRODUCT_STOCK),
        ("cuantas unidades de arroz hay", Intents.PRODUCT_STOCK),
        ("existencias de pan", Intents.PRODUCT_STOCK),
        ("hay harina", Intents.PRODUCT_STOCK),
        ("¿qué productos tienen stock bajo?", Intents.LOW_STOCK),
        ("se estan agotando las bebidas", Intents.LOW_STOCK),
        ("que productos debo reponer", Intents.LOW_STOCK),
        ("busca el producto por codigo de barras 7501234567890", Intents.SEARCH_PRODUCT),
        ("que precio tiene la leche", Intents.SEARCH_PRODUCT),
        ("cuánto vendí esta semana", Intents.SALES_SUMMARY),
        ("dime el total vendido", Intents.SALES_SUMMARY),
        ("ventas del mes", Intents.SALES_SUMMARY),
        ("muéstrame las últimas compras", Intents.PURCHASES_SUMMARY),
        ("busca el proveedor Distribuidora ABC", Intents.SUPPLIERS),
        ("quién me debe dinero", Intents.RECEIVABLES),
        ("cuentas por cobrar pendientes", Intents.RECEIVABLES),
        ("clientes con deuda", Intents.RECEIVABLES),
        ("estado de caja de hoy", Intents.CASH),
        ("cuánto hay en caja", Intents.CASH),
        ("cómo va el negocio", Intents.BUSINESS_SUMMARY),
        ("dame un resumen general", Intents.BUSINESS_SUMMARY),
        ("hola", Intents.HELP),
        ("que puedes hacer", Intents.HELP),
        ("asdf qwerty", Intents.UNKNOWN),
    ],
)
def test_classify_intents(text, expected):
    assert classify(text).intent == expected


def test_extract_days_and_barcode_and_quantity():
    result = classify("cuánto vendí en los últimos 45 días")
    assert result.entities.get("days") == 45

    result = classify("busca el producto 7501234567890")
    assert result.entities.get("barcode") == "7501234567890"

    result = classify("ajusta el stock de arroz a 50")
    assert result.intent == Intents.ADJUST_STOCK
    assert result.entities.get("quantity") == 50
    assert result.entities.get("product_query") == "arroz"


def test_classify_help_message_has_examples():
    result = classify("no entiendo nada zzz")
    assert result.intent == Intents.UNKNOWN
    assert "ejemplo" in intent_engine.HELP_MESSAGE.lower() or "•" in intent_engine.HELP_MESSAGE


# ----------------------------------------------------------------------
# Asistente local con datos reales
# ----------------------------------------------------------------------
def test_local_product_stock_returns_real_value(db_session, admin_user, make_product):
    make_product(name="Leche Entera 1L", stock=7, minimum_stock=3)
    answer = LocalAssistant(db_session).respond(admin_user, "cuánto stock queda de leche")
    assert "7" in answer.message
    assert answer.action_proposals == []
    assert any(t["name"] == "get_product_stock" for t in answer.tool_results)


def test_local_product_not_found_is_clear(db_session, admin_user):
    answer = LocalAssistant(db_session).respond(admin_user, "cuánto stock queda de unicornio")
    assert "no encontr" in answer.message.lower()


def test_local_ambiguous_product_asks_clarification(db_session, admin_user, make_product):
    make_product(name="Arroz Blanco")
    make_product(name="Arroz Integral")
    answer = LocalAssistant(db_session).respond(admin_user, "cuánto stock hay de arroz")
    assert "varios" in answer.message.lower()


def test_local_low_stock_lists_products(db_session, admin_user, make_product):
    make_product(name="Café", stock=1, minimum_stock=5)
    answer = LocalAssistant(db_session).respond(admin_user, "que productos tienen stock bajo")
    assert "Café" in answer.message


def test_local_unknown_suggests_examples(db_session, admin_user):
    answer = LocalAssistant(db_session).respond(admin_user, "xyzabc")
    assert "puedo" in answer.message.lower() or "productos" in answer.message.lower()


def test_local_cashier_cannot_propose_adjust(db_session, cashier_user, make_product):
    make_product(name="Arroz", stock=3)
    answer = LocalAssistant(db_session).respond(cashier_user, "ajusta el stock de arroz a 50")
    assert answer.action_proposals == []
    assert "permiso" in answer.message.lower()


def test_local_inventory_manager_proposes_adjust(
    db_session, inventory_manager_user, make_product
):
    product = make_product(name="Arroz Blanco", stock=3)
    answer = LocalAssistant(db_session).respond(
        inventory_manager_user, "ajusta el stock de arroz blanco a 50"
    )
    assert len(answer.action_proposals) == 1
    proposal = answer.action_proposals[0]
    assert proposal["action_name"] == "adjust_inventory"
    assert proposal["args"]["product_id"] == str(product.id)
    assert proposal["args"]["new_stock"] == 50


# ----------------------------------------------------------------------
# Respaldo local del servicio cuando Gemini no está configurado
# ----------------------------------------------------------------------
def test_chat_falls_back_to_local_when_ai_not_configured(
    db_session, admin_user, make_product
):
    make_product(name="Café", stock=1, minimum_stock=5)
    fake = FakeGeminiClient(available=False)
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.chat(admin_user, "que productos tienen stock bajo")
    assert resp.model_used == "nexora-local"
    assert "Café" in resp.message
    assert len(resp.tool_results) >= 1


def test_chat_uses_history_for_follow_up(db_session, admin_user, make_product):
    make_product(name="Leche Entera 1L", stock=9)
    # Sin producto en el mensaje actual: debe resolverlo desde el historial.
    fake = FakeGeminiClient(available=False)
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.chat(
        admin_user,
        "y cuantas existencias hay",
        history=[{"role": "user", "text": "cuanto stock de leche"}],
    )
    assert "Leche Entera" in resp.message
    assert "9" in resp.message
