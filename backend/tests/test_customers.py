"""Tests del módulo de clientes (CRUD, crédito, RBAC, desactivación lógica)."""

from tests.conftest import TEST_PASSWORD, auth_headers

BASE = "/api/customers"
LOGIN = "/api/auth/login"


def _login(client, username: str) -> dict[str, str]:
    res = client.post(LOGIN, json={"username": username, "password": TEST_PASSWORD})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _payload(**overrides) -> dict:
    data = {
        "name": "Juan Pérez",
        "identification": "1090123456",
        "phone": "3001112233",
        "email": "juan@example.com",
    }
    data.update(overrides)
    return data


# ----------------------------------------------------------------------
# Creación
# ----------------------------------------------------------------------
def test_create_customer_success_returns_201(client, admin_user):
    res = client.post(BASE, json=_payload(), headers=auth_headers(admin_user))
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Juan Pérez"
    assert body["identification"] == "1090123456"
    assert body["is_active"] is True
    assert body["credit_enabled"] is False
    assert body["credit_limit"] == "0.00"
    assert body["current_balance"] == "0.00"
    assert body["credit_available"] == "0.00"


def test_create_customer_without_identification_ok(client, admin_user):
    res = client.post(
        BASE,
        json={"name": "Consumidor Final"},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 201
    assert res.json()["identification"] is None


def test_create_customer_duplicate_identification_conflict_409(client, admin_user):
    client.post(BASE, json=_payload(), headers=auth_headers(admin_user))
    res = client.post(
        BASE, json=_payload(name="Otro Nombre"), headers=auth_headers(admin_user)
    )
    assert res.status_code == 409
    assert res.json()["error_code"] == "CUSTOMER_IDENTIFICATION_ALREADY_EXISTS"


def test_create_customer_blank_identification_normalized_to_null(client, admin_user):
    res = client.post(
        BASE, json=_payload(identification="   "), headers=auth_headers(admin_user)
    )
    assert res.status_code == 201
    assert res.json()["identification"] is None


def test_create_customer_credit_without_limit_rejected_422(client, admin_user):
    res = client.post(
        BASE,
        json=_payload(credit_enabled=True),
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 422


def test_create_customer_with_credit_limit_ok(client, admin_user):
    res = client.post(
        BASE,
        json=_payload(credit_enabled=True, credit_limit="1000000.00"),
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 201
    body = res.json()
    assert body["credit_enabled"] is True
    assert body["credit_available"] == "1000000.00"


# ----------------------------------------------------------------------
# Permisos / RBAC
# ----------------------------------------------------------------------
def test_create_customer_requires_auth_401(client):
    assert client.post(BASE, json=_payload()).status_code == 401


def test_create_customer_forbidden_without_permission_403(client, no_role_user):
    res = client.post(BASE, json=_payload(), headers=auth_headers(no_role_user))
    assert res.status_code == 403


def test_cashier_can_create_and_read_customers(client, cashier_user):
    headers = auth_headers(cashier_user)
    created = client.post(BASE, json=_payload(), headers=headers)
    assert created.status_code == 201
    listed = client.get(BASE, headers=headers)
    assert listed.status_code == 200


def test_inventory_manager_can_manage_customers_but_not_delete(
    client, inventory_manager_user
):
    headers = auth_headers(inventory_manager_user)
    created = client.post(BASE, json=_payload(), headers=headers)
    assert created.status_code == 201
    customer_id = created.json()["id"]
    updated = client.patch(
        f"{BASE}/{customer_id}", json={"city": "Cali"}, headers=headers
    )
    assert updated.status_code == 200
    deleted = client.delete(f"{BASE}/{customer_id}", headers=headers)
    assert deleted.status_code == 403


def test_delete_customer_reserved_to_admin(client, cashier_user, admin_user, make_customer):
    customer = make_customer()
    res = client.delete(
        f"{BASE}/{customer.id}", headers=auth_headers(cashier_user)
    )
    assert res.status_code == 403
    ok = client.delete(f"{BASE}/{customer.id}", headers=auth_headers(admin_user))
    assert ok.status_code == 204


# ----------------------------------------------------------------------
# Listado / detalle
# ----------------------------------------------------------------------
def test_list_customers_pagination_and_total(client, admin_user, make_customer):
    for i in range(5):
        make_customer(name=f"Cliente {i}")
    res = client.get(
        BASE, params={"skip": 1, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_customers_search_by_name(client, admin_user, make_customer):
    make_customer(name="María Gómez")
    make_customer(name="Pedro Ruiz")
    res = client.get(
        BASE, params={"q": "maría"}, headers=auth_headers(admin_user)
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_list_customers_filter_credit_enabled(client, admin_user, make_customer):
    make_customer(credit_enabled=True, credit_limit="500000.00")
    make_customer()
    res = client.get(
        BASE, params={"credit_enabled": True}, headers=auth_headers(admin_user)
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_get_customer_not_found_404(client, admin_user):
    res = client.get(
        f"{BASE}/00000000-0000-0000-0000-000000000001",
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 404


def test_update_customer_fields(client, admin_user):
    created = client.post(BASE, json=_payload(), headers=auth_headers(admin_user))
    cid = created.json()["id"]
    res = client.patch(
        f"{BASE}/{cid}",
        json={"phone": "3114445566", "city": "Bogotá"},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 200
    assert res.json()["phone"] == "3114445566"
    assert res.json()["city"] == "Bogotá"


# ----------------------------------------------------------------------
# Reglas de crédito en actualización
# ----------------------------------------------------------------------
def test_update_credit_limit_below_balance_conflict_409(client, admin_user, make_customer):
    customer = make_customer(
        credit_enabled=True, credit_limit="1000000.00"
    )
    # Deuda de 300k vía cuenta por cobrar manual
    rec = client.post(
        "/api/receivables",
        json={"customer_id": str(customer.id), "original_amount": "300000.00"},
        headers=auth_headers(admin_user),
    )
    assert rec.status_code == 201
    res = client.patch(
        f"{BASE}/{customer.id}",
        json={"credit_limit": "200000.00"},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 409
    assert res.json()["error_code"] == "CREDIT_LIMIT_BELOW_BALANCE"


def test_enable_credit_with_balance_above_limit_conflict_409(
    client, db_session, admin_user, make_customer
):
    from decimal import Decimal

    customer = make_customer(credit_enabled=False, credit_limit="100000.00")
    # Estado de borde fabricado: saldo mayor al límite con crédito apagado
    customer.current_balance = Decimal("150000.00")
    db_session.commit()

    res = client.patch(
        f"{BASE}/{customer.id}",
        json={"credit_enabled": True},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 409
    assert res.json()["error_code"] == "CREDIT_LIMIT_BELOW_BALANCE"


# ----------------------------------------------------------------------
# Desactivación lógica
# ----------------------------------------------------------------------
def test_deactivate_customer_soft_delete_keeps_history(client, admin_user, make_customer):
    customer = make_customer(
        name="Cliente Histórico", credit_enabled=True, credit_limit="500000.00"
    )
    rec = client.post(
        "/api/receivables",
        json={"customer_id": str(customer.id), "original_amount": "50000.00"},
        headers=auth_headers(admin_user),
    )
    assert rec.status_code == 201

    deleted = client.delete(
        f"{BASE}/{customer.id}", headers=auth_headers(admin_user)
    )
    assert deleted.status_code == 204

    detail = client.get(f"{BASE}/{customer.id}", headers=auth_headers(admin_user))
    assert detail.status_code == 200
    body = detail.json()
    assert body["is_active"] is False
    # El historial financiero permanece intacto
    statement = client.get(
        f"{BASE}/{customer.id}/statement", headers=auth_headers(admin_user)
    )
    assert statement.status_code == 200
    assert statement.json()["summary"]["open_count"] == 1
