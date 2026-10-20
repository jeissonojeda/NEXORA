from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _product_payload(category_id, **overrides) -> dict:
    payload = {
        "name": "Producto precios",
        "barcode": "7509999999999",
        "purchase_price": "10000",
        "profit_percent": "30",
        "category_id": str(category_id),
        "stock": 10,
        "minimum_stock": 1,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Precios / utilidad
# ---------------------------------------------------------------------------
def test_create_product_computes_sale_price_from_profit(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=_product_payload(category.id),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["purchase_price"] == "10000.00"
    assert data["profit_percent"] == "30.00"
    assert data["sale_price"] == "13000.00"


def test_create_product_zero_profit_uses_cost(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=_product_payload(category.id, profit_percent="0"),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    assert response.json()["sale_price"] == "10000.00"


def test_create_product_rounds_half_up(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=_product_payload(
            category.id, purchase_price="999.99", profit_percent="33.33"
        ),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    # 999.99 * 1.3333 = 1333.286667 -> 1333.29
    assert response.json()["sale_price"] == "1333.29"


def test_create_product_rejects_negative_profit(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=_product_payload(category.id, profit_percent="-5"),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422


def test_manual_sale_price_recomputes_profit(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=_product_payload(
            category.id, purchase_price="100", sale_price="150", profit_percent="0"
        ),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sale_price"] == "150.00"
    assert data["profit_percent"] == "50.00"


def test_update_purchase_price_recalculates_sale_price(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    created = client.post(
        "/api/products",
        json=_product_payload(category.id, purchase_price="100", profit_percent="30"),
        headers=auth_headers(admin_user),
    ).json()
    assert created["sale_price"] == "130.00"

    response = client.patch(
        f"/api/products/{created['id']}",
        json={"purchase_price": "200"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["sale_price"] == "260.00"


def test_update_profit_percent_recalculates_sale_price(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    created = client.post(
        "/api/products",
        json=_product_payload(category.id, purchase_price="100", profit_percent="30"),
        headers=auth_headers(admin_user),
    ).json()

    response = client.patch(
        f"/api/products/{created['id']}",
        json={"profit_percent": "50"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["sale_price"] == "150.00"


def test_historical_sale_price_not_recalculated(
    client: TestClient, cashier_user, admin_user, make_product
) -> None:
    product = make_product(sale_price="100.00", purchase_price="50.00", stock=10)
    sale = client.post(
        "/api/sales",
        json={
            "payment_method": "CASH",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
        headers=auth_headers(cashier_user),
    ).json()
    assert sale["items"][0]["unit_price"] == "100.00"

    # Cambiar el precio del producto no debe alterar la venta ya registrada.
    client.patch(
        f"/api/products/{product.id}",
        json={"sale_price": "500.00"},
        headers=auth_headers(admin_user),
    )
    detail = client.get(
        f"/api/sales/{sale['id']}", headers=auth_headers(cashier_user)
    ).json()
    assert detail["items"][0]["unit_price"] == "100.00"


# ---------------------------------------------------------------------------
# Impuestos
# ---------------------------------------------------------------------------
def test_create_and_list_tax(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/taxes",
        json={"name": "IVA", "rate": "19", "is_default": True},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rate"] == "19.00"
    assert data["is_default"] is True

    listing = client.get("/api/taxes", headers=auth_headers(admin_user))
    assert listing.status_code == 200
    assert any(t["name"] == "IVA" for t in listing.json())


def test_tax_duplicate_name_returns_409(client: TestClient, admin_user) -> None:
    payload = {"name": "IVA", "rate": "19"}
    client.post("/api/taxes", json=payload, headers=auth_headers(admin_user))
    response = client.post("/api/taxes", json=payload, headers=auth_headers(admin_user))
    assert response.status_code == 409
    assert response.json()["error_code"] == "TAX_NAME_ALREADY_EXISTS"


def test_tax_rate_out_of_range_rejected(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/taxes",
        json={"name": "Exagerado", "rate": "150"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422


def test_category_linked_to_tax(client: TestClient, admin_user) -> None:
    tax = client.post(
        "/api/taxes",
        json={"name": "IVA", "rate": "19"},
        headers=auth_headers(admin_user),
    ).json()
    response = client.post(
        "/api/categories",
        json={"name": "Bebidas", "tax_id": tax["id"]},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    assert response.json()["tax"]["id"] == tax["id"]
    assert response.json()["tax"]["rate"] == "19.00"


def test_product_inherits_category_tax(client: TestClient, admin_user) -> None:
    tax = client.post(
        "/api/taxes",
        json={"name": "IVA", "rate": "19"},
        headers=auth_headers(admin_user),
    ).json()
    category = client.post(
        "/api/categories",
        json={"name": "Bebidas", "tax_id": tax["id"]},
        headers=auth_headers(admin_user),
    ).json()
    product = client.post(
        "/api/products",
        json=_product_payload(category["id"], purchase_price="100", profit_percent="0"),
        headers=auth_headers(admin_user),
    ).json()
    assert product["tax"] is None
    assert product["effective_tax"]["id"] == tax["id"]
    assert product["effective_tax"]["rate"] == "19.00"


def test_product_tax_override(client: TestClient, admin_user) -> None:
    base = client.post(
        "/api/taxes",
        json={"name": "IVA", "rate": "19"},
        headers=auth_headers(admin_user),
    ).json()
    special = client.post(
        "/api/taxes",
        json={"name": "Exento", "rate": "0"},
        headers=auth_headers(admin_user),
    ).json()
    category = client.post(
        "/api/categories",
        json={"name": "Canasta", "tax_id": base["id"]},
        headers=auth_headers(admin_user),
    ).json()
    product = client.post(
        "/api/products",
        json=_product_payload(
            category["id"], purchase_price="100", profit_percent="0", tax_id=special["id"]
        ),
        headers=auth_headers(admin_user),
    ).json()
    assert product["effective_tax"]["id"] == special["id"]


def test_sale_item_stores_tax_rate_and_amount(
    client: TestClient, admin_user, cashier_user
) -> None:
    tax = client.post(
        "/api/taxes",
        json={"name": "IVA", "rate": "19"},
        headers=auth_headers(admin_user),
    ).json()
    category = client.post(
        "/api/categories",
        json={"name": "Bebidas", "tax_id": tax["id"]},
        headers=auth_headers(admin_user),
    ).json()
    product = client.post(
        "/api/products",
        json=_product_payload(
            category["id"], purchase_price="100", profit_percent="0", sale_price="100"
        ),
        headers=auth_headers(admin_user),
    ).json()

    sale = client.post(
        "/api/sales",
        json={
            "payment_method": "CASH",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers=auth_headers(cashier_user),
    )
    assert sale.status_code == 201
    body = sale.json()
    item = body["items"][0]
    assert item["tax_rate"] == "19.00"
    assert item["tax"] == "19.00"
    assert item["tax_name"] == "IVA"
    # El impuesto de cabecera se deriva de los ítems cuando no se envía.
    assert body["tax"] == "19.00"
    assert float(body["total"]) == 119.0


def test_tax_write_requires_permission(client: TestClient, cashier_user) -> None:
    response = client.post(
        "/api/taxes",
        json={"name": "No permitido", "rate": "5"},
        headers=auth_headers(cashier_user),
    )
    assert response.status_code == 403


def test_tax_read_allowed_for_cashier(client: TestClient, cashier_user) -> None:
    response = client.get("/api/taxes", headers=auth_headers(cashier_user))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Configuración / moneda
# ---------------------------------------------------------------------------
def test_settings_default_currency_is_cop(client: TestClient, admin_user) -> None:
    response = client.get("/api/settings", headers=auth_headers(admin_user))
    assert response.status_code == 200
    data = response.json()
    assert data["currency_code"] == "COP"
    assert data["currency_symbol"] == "$"
    assert "es-CO" in data["currency_locale"]


def test_update_currency(client: TestClient, admin_user) -> None:
    response = client.put(
        "/api/settings",
        json={"currency_code": "USD"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["currency_code"] == "USD"


def test_currency_change_requires_confirmation_with_transactions(
    client: TestClient, admin_user, cashier_user, make_product
) -> None:
    product = make_product()
    client.post(
        "/api/sales",
        json={
            "payment_method": "CASH",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
        headers=auth_headers(cashier_user),
    )
    blocked = client.put(
        "/api/settings",
        json={"currency_code": "USD"},
        headers=auth_headers(admin_user),
    )
    assert blocked.status_code == 409
    assert (
        blocked.json()["error_code"] == "CURRENCY_CHANGE_REQUIRES_CONFIRMATION"
    )

    confirmed = client.put(
        "/api/settings",
        json={"currency_code": "USD", "confirm_currency_change": True},
        headers=auth_headers(admin_user),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["currency_code"] == "USD"


def test_unsupported_currency_rejected(client: TestClient, admin_user) -> None:
    response = client.put(
        "/api/settings",
        json={"currency_code": "XYZ"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422
