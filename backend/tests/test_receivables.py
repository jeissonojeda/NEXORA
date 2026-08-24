"""Tests de cuentas por cobrar: crédito, pagos atómicos, idempotencia, RBAC."""

from tests.conftest import auth_headers

BASE = "/api/receivables"


def _credit_customer(make_customer, limit="1000000.00"):
    return make_customer(credit_enabled=True, credit_limit=limit)


def _create_receivable(client, admin_user, customer_id, amount, **kwargs):
    payload = {
        "customer_id": str(customer_id),
        "original_amount": amount,
        "description": kwargs.get("description", "Venta a crédito de prueba"),
    }
    if kwargs.get("due_date"):
        payload["due_date"] = kwargs["due_date"]
    return client.post(BASE, json=payload, headers=auth_headers(admin_user))


def _pay(client, user, account_id, amount, method="CASH", idempotency_key=None):
    payload = {"amount": amount, "payment_method": method}
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    return client.post(
        f"{BASE}/{account_id}/payments",
        json=payload,
        headers=auth_headers(user),
    )


# ----------------------------------------------------------------------
# Crear cuentas por cobrar
# ----------------------------------------------------------------------
def test_create_receivable_increases_balance_and_available(
    client, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    res = _create_receivable(client, admin_user, customer.id, "300000.00")
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "OPEN"
    assert body["original_amount"] == "300000.00"
    assert body["paid_amount"] == "0.00"
    assert body["balance"] == "300000.00"
    assert body["customer"]["id"] == str(customer.id)

    detail = client.get(
        f"/api/customers/{customer.id}", headers=auth_headers(admin_user)
    )
    assert detail.json()["current_balance"] == "300000.00"
    assert detail.json()["credit_available"] == "700000.00"


def test_create_receivable_requires_credit_enabled_409(
    client, admin_user, make_customer
):
    customer = make_customer(credit_enabled=False)
    res = _create_receivable(client, admin_user, customer.id, "50000.00")
    assert res.status_code == 409
    assert res.json()["error_code"] == "CREDIT_NOT_ENABLED"
    # El saldo del cliente no cambió
    detail = client.get(
        f"/api/customers/{customer.id}", headers=auth_headers(admin_user)
    )
    assert detail.json()["current_balance"] == "0.00"


def test_create_receivable_exceeding_limit_409(client, admin_user, make_customer):
    customer = _credit_customer(make_customer, limit="500000.00")
    res = _create_receivable(client, admin_user, customer.id, "600000.00")
    assert res.status_code == 409
    assert res.json()["error_code"] == "CREDIT_LIMIT_EXCEEDED"


def test_create_receivable_accumulates_until_limit(client, admin_user, make_customer):
    customer = _credit_customer(make_customer, limit="500000.00")
    first = _create_receivable(client, admin_user, customer.id, "300000.00")
    second = _create_receivable(client, admin_user, customer.id, "200000.00")
    assert first.status_code == 201
    assert second.status_code == 201

    third = _create_receivable(client, admin_user, customer.id, "0.01")
    assert third.status_code == 409


def test_create_receivable_inactive_customer_409(
    client, db_session, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    customer.is_active = False
    db_session.commit()
    res = _create_receivable(client, admin_user, customer.id, "50000.00")
    assert res.status_code == 409
    assert res.json()["error_code"] == "CUSTOMER_INACTIVE"


def test_create_receivable_unknown_customer_404(client, admin_user):
    res = _create_receivable(
        client, admin_user, "00000000-0000-0000-0000-000000000009", "50000.00"
    )
    assert res.status_code == 404


# ----------------------------------------------------------------------
# Flujo de pagos
# ----------------------------------------------------------------------
def test_partial_then_full_payment_updates_status_and_balances(
    client, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "300000.00").json()

    partial = _pay(client, admin_user, account["id"], "100000.00", "TRANSFER")
    assert partial.status_code == 201
    body = partial.json()
    assert body["amount"] == "100000.00"
    assert body["payment_method"] == "TRANSFER"

    after_partial = client.get(
        f"{BASE}/{account['id']}", headers=auth_headers(admin_user)
    ).json()
    assert after_partial["status"] == "PARTIALLY_PAID"
    assert after_partial["paid_amount"] == "100000.00"
    assert after_partial["balance"] == "200000.00"

    final = _pay(client, admin_user, account["id"], "200000.00")
    assert final.status_code == 201
    after_final = client.get(
        f"{BASE}/{account['id']}", headers=auth_headers(admin_user)
    ).json()
    assert after_final["status"] == "PAID"
    assert after_final["balance"] == "0.00"

    detail = client.get(
        f"/api/customers/{customer.id}", headers=auth_headers(admin_user)
    ).json()
    assert detail["current_balance"] == "0.00"
    assert detail["credit_available"] == "1000000.00"


def test_payment_exceeding_balance_conflict_409(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    res = _pay(client, admin_user, account["id"], "100000.01")
    assert res.status_code == 409
    assert res.json()["error_code"] == "PAYMENT_EXCEEDS_BALANCE"


def test_payment_on_paid_account_conflict_409(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "50000.00").json()
    assert _pay(client, admin_user, account["id"], "50000.00").status_code == 201
    res = _pay(client, admin_user, account["id"], "0.01")
    assert res.status_code == 409
    assert res.json()["error_code"] == "RECEIVABLE_ALREADY_PAID"


def test_multiple_payments_without_key_all_allowed(client, admin_user, make_customer):
    """Sin idempotency_key cada pago es una operación nueva y válida."""
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "300000.00").json()
    first = _pay(client, admin_user, account["id"], "100000.00")
    second = _pay(client, admin_user, account["id"], "100000.00")
    assert first.status_code == 201
    assert second.status_code == 201
    after = client.get(
        f"{BASE}/{account['id']}", headers=auth_headers(admin_user)
    ).json()
    assert after["paid_amount"] == "200000.00"
    assert after["status"] == "PARTIALLY_PAID"


def test_idempotent_payment_same_key_applies_once(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "300000.00").json()
    key = "pos-session-42-payment-1"

    first = _pay(client, admin_user, account["id"], "150000.00", "CARD", key)
    replay = _pay(client, admin_user, account["id"], "150000.00", "CARD", key)

    assert first.status_code == 201
    assert replay.status_code == 200  # replay idempotente, no creación
    assert replay.json()["id"] == first.json()["id"]

    after = client.get(
        f"{BASE}/{account['id']}", headers=auth_headers(admin_user)
    ).json()
    assert after["paid_amount"] == "150000.00"  # aplicado UNA sola vez
    assert after["status"] == "PARTIALLY_PAID"

    payments = client.get(
        f"{BASE}/{account['id']}/payments", headers=auth_headers(admin_user)
    ).json()
    assert payments["total"] == 1


def test_payments_listing_includes_username(client, cashier_user, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    _pay(client, cashier_user, account["id"], "40000.00")
    res = client.get(
        f"{BASE}/{account['id']}/payments", headers=auth_headers(cashier_user)
    )
    assert res.status_code == 200
    payment = res.json()["items"][0]
    assert payment["created_by"] == str(cashier_user.id)
    assert payment["created_by_username"] == cashier_user.username
    assert "password_hash" not in payment


def test_invalid_payment_method_rejected_422(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    res = _pay(client, admin_user, account["id"], "10000.00", method="BITCOIN")
    assert res.status_code == 422


def test_negative_payment_rejected_422(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    res = _pay(client, admin_user, account["id"], "-5.00")
    assert res.status_code == 422


# ----------------------------------------------------------------------
# Anulación
# ----------------------------------------------------------------------
def test_cancel_receivable_writes_off_remaining_balance(
    client, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "300000.00").json()
    _pay(client, admin_user, account["id"], "100000.00")

    cancelled = client.post(
        f"{BASE}/{account['id']}/cancel", headers=auth_headers(admin_user)
    )
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "CANCELLED"
    assert body["balance"] == "200000.00"  # histórico conservado

    detail = client.get(
        f"/api/customers/{customer.id}", headers=auth_headers(admin_user)
    ).json()
    assert detail["current_balance"] == "0.00"
    assert detail["credit_available"] == "1000000.00"

    # Ya no admite pagos
    late = _pay(client, admin_user, account["id"], "1.00")
    assert late.status_code == 409
    assert late.json()["error_code"] == "RECEIVABLE_CANCELLED"


def test_cancel_twice_conflict_409(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "10000.00").json()
    assert (
        client.post(f"{BASE}/{account['id']}/cancel", headers=auth_headers(admin_user)).status_code
        == 200
    )
    again = client.post(f"{BASE}/{account['id']}/cancel", headers=auth_headers(admin_user))
    assert again.status_code == 409
    assert again.json()["error_code"] == "RECEIVABLE_ALREADY_CANCELLED"


def test_cancel_paid_account_conflict_409(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    account = _create_receivable(client, admin_user, customer.id, "10000.00").json()
    _pay(client, admin_user, account["id"], "10000.00")
    res = client.post(f"{BASE}/{account['id']}/cancel", headers=auth_headers(admin_user))
    assert res.status_code == 409
    assert res.json()["error_code"] == "RECEIVABLE_ALREADY_PAID"


# ----------------------------------------------------------------------
# Estado de cuenta
# ----------------------------------------------------------------------
def test_statement_summary_counts_and_total_balance(
    client, admin_user, make_customer
):
    customer = _credit_customer(make_customer, limit="2000000.00")
    acc_open = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    acc_partial = _create_receivable(
        client, admin_user, customer.id, "200000.00"
    ).json()
    acc_paid = _create_receivable(client, admin_user, customer.id, "50000.00").json()
    acc_cancelled = _create_receivable(
        client, admin_user, customer.id, "70000.00"
    ).json()

    _pay(client, admin_user, acc_partial["id"], "50000.00")
    _pay(client, admin_user, acc_paid["id"], "50000.00")
    client.post(f"{BASE}/{acc_cancelled['id']}/cancel", headers=auth_headers(admin_user))

    res = client.get(
        f"/api/customers/{customer.id}/statement", headers=auth_headers(admin_user)
    )
    assert res.status_code == 200
    statement = res.json()
    summary = statement["summary"]
    assert summary["open_count"] == 1
    assert summary["partially_paid_count"] == 1
    assert summary["paid_count"] == 1
    assert summary["cancelled_count"] == 1
    assert summary["total_balance"] == "250000.00"  # open 100k + partial 150k

    credit = statement["credit"]
    assert credit["current_balance"] == "250000.00"
    assert credit["credit_available"] == "1750000.00"

    assert statement["accounts"]["total"] == 4
    assert statement["payments"]["total"] == 2
    assert statement["customer"]["id"] == str(customer.id)


def test_statement_unknown_customer_404(client, admin_user):
    res = client.get(
        "/api/customers/00000000-0000-0000-0000-000000000008/statement",
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 404


# ----------------------------------------------------------------------
# Listado con filtros
# ----------------------------------------------------------------------
def test_list_receivables_filter_by_status(client, admin_user, make_customer):
    customer = _credit_customer(make_customer)
    acc = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    _create_receivable(client, admin_user, customer.id, "200000.00")
    _pay(client, admin_user, acc["id"], "40000.00")

    res = client.get(
        BASE, params={"status": "PARTIALLY_PAID"}, headers=auth_headers(admin_user)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "PARTIALLY_PAID"

    by_customer = client.get(
        BASE, params={"customer_id": str(customer.id)}, headers=auth_headers(admin_user)
    )
    assert by_customer.json()["total"] == 2


# ----------------------------------------------------------------------
# RBAC
# ----------------------------------------------------------------------
def test_cashier_can_read_and_pay_but_not_create_or_cancel(
    client, cashier_user, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    create_res = _create_receivable(client, cashier_user, customer.id, "100000.00")
    assert create_res.status_code == 403

    account = _create_receivable(client, admin_user, customer.id, "100000.00").json()
    pay_res = _pay(client, cashier_user, account["id"], "40000.00")
    assert pay_res.status_code == 201

    list_res = client.get(BASE, headers=auth_headers(cashier_user))
    assert list_res.status_code == 200

    cancel_res = client.post(
        f"{BASE}/{account['id']}/cancel", headers=auth_headers(cashier_user)
    )
    assert cancel_res.status_code == 403


def test_inventory_manager_cannot_access_receivables(
    client, inventory_manager_user, admin_user, make_customer
):
    customer = _credit_customer(make_customer)
    res = _create_receivable(
        client, inventory_manager_user, customer.id, "100000.00"
    )
    assert res.status_code == 403
    listing = client.get(BASE, headers=auth_headers(inventory_manager_user))
    assert listing.status_code == 403


def test_receivables_require_auth_401(client):
    assert client.get(BASE).status_code == 401
