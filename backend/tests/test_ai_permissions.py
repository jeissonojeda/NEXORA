"""Tests de permisos RBAC de los endpoints de IA operativa."""

import pytest
from fastapi.testclient import TestClient

from app.core.rbac import Roles
from tests.conftest import auth_headers


def test_chat_requires_ai_read(client, db_session, admin_user):
    resp = client.post(
        "/api/ai/chat",
        json={"message": "hola"},
        headers=auth_headers(admin_user),
    )
    # admin tiene ai.read => llega al servicio (permite error 502/500 por
    # falta de API key, pero NO 403).
    assert resp.status_code != 403


def test_chat_denied_without_role(client, db_session, no_role_user):
    resp = client.post(
        "/api/ai/chat",
        json={"message": "hola"},
        headers=auth_headers(no_role_user),
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    "fixture_name,expected",
    [
        (Roles.ADMIN, 200),
        (Roles.INVENTORY_MANAGER, 200),
        (Roles.CASHIER, 403),
    ],
)
def test_invoice_scan_permission(
    client, db_session, admin_user, inventory_manager_user, cashier_user,
    fixture_name, expected, monkeypatch,
):
    user = {
        Roles.ADMIN: admin_user,
        Roles.INVENTORY_MANAGER: inventory_manager_user,
        Roles.CASHIER: cashier_user,
    }[fixture_name]

    from tests.fakes import FakeGeminiClient

    fake = FakeGeminiClient(vision_text='{"supplier_name": "X", "items": []}')
    monkeypatch.setattr(
        "app.services.ai_operational_service.gemini_client", fake
    )

    resp = client.post(
        "/api/ai/invoice/scan",
        files={"file": ("factura.png", b"imagen", "image/png")},
        headers=auth_headers(user),
    )
    assert resp.status_code == expected


def test_confirm_requires_ai_execute(client, db_session, cashier_user):
    resp = client.post(
        "/api/ai/action/confirm",
        json={
            "action_name": "create_supplier",
            "args": {"name": "ProveedorX"},
            "idempotency_key": "k1",
        },
        headers=auth_headers(cashier_user),
    )
    assert resp.status_code == 403


def test_confirm_inventory_manager_without_native_payment_denied(
    client, db_session, inventory_manager_user
):
    # INVENTORY_MANAGER tiene ai.execute pero no receivables.payment nativo.
    resp = client.post(
        "/api/ai/action/confirm",
        json={
            "action_name": "register_payment",
            "args": {"account_id": "a", "amount": "10", "payment_method": "CASH"},
            "idempotency_key": "k-pay",
        },
        headers=auth_headers(inventory_manager_user),
    )
    assert resp.status_code == 403
