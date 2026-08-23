from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def product_payload(category_id, **overrides) -> dict:
    payload = {
        "name": "Leche Entera 1L",
        "barcode": "7501234567890",
        "purchase_price": "12.50",
        "sale_price": "18.00",
        "category_id": str(category_id),
        "stock": 25,
        "minimum_stock": 5,
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_product(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category(name="Lácteos")
    response = client.post(
        "/api/products",
        json=product_payload(category.id),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Leche Entera 1L"
    assert data["sale_price"] == "18.00"
    assert data["category"]["id"] == str(category.id)
    assert data["stock"] == 25
    assert "password" not in data


def test_create_product_with_invalid_category_returns_400(
    client: TestClient, admin_user
) -> None:
    from uuid import uuid4

    payload = product_payload(uuid4())
    response = client.post(
        "/api/products", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_CATEGORY"


def test_create_product_with_duplicate_barcode_returns_409(
    client: TestClient, admin_user, make_category, make_product
) -> None:
    category = make_category()
    make_product(barcode="7500000000011", category=category)
    payload = product_payload(category.id, barcode="7500000000011")
    response = client.post(
        "/api/products", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "BARCODE_ALREADY_EXISTS"


def test_create_product_with_negative_prices_rejected(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    for field in ("sale_price", "purchase_price"):
        payload = product_payload(category.id, **{field: "-1.00"})
        response = client.post(
            "/api/products", json=payload, headers=auth_headers(admin_user)
        )
        assert response.status_code == 422, f"{field} negativo aceptado"


def test_create_product_with_negative_stock_rejected(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    for field in ("stock", "minimum_stock"):
        payload = product_payload(category.id, **{field: -3})
        response = client.post(
            "/api/products", json=payload, headers=auth_headers(admin_user)
        )
        assert response.status_code == 422, f"{field} negativo aceptado"


def test_products_support_pagination_and_total(
    client: TestClient, admin_user, make_category, make_product
) -> None:
    category = make_category()
    for i in range(7):
        make_product(name=f"Bulk {i}", category=category)

    page_one = client.get(
        "/api/products?limit=5&skip=0", headers=auth_headers(admin_user)
    )
    assert page_one.status_code == 200
    body = page_one.json()
    assert len(body["items"]) == 5
    assert body["total"] == 7

    page_two = client.get(
        "/api/products?limit=5&skip=5", headers=auth_headers(admin_user)
    )
    assert len(page_two.json()["items"]) == 2


def test_products_search_by_name_and_barcode(
    client: TestClient, admin_user, make_product
) -> None:
    make_product(name="Coca-Cola 600ml", barcode="7501111111111")
    make_product(name="Pepsi 600ml", barcode="7502222222222")

    by_name = client.get(
        "/api/products?q=coca-cola", headers=auth_headers(admin_user)
    )
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["name"] == "Coca-Cola 600ml"

    by_barcode = client.get(
        "/api/products?q=7502222222222", headers=auth_headers(admin_user)
    )
    assert by_barcode.json()["total"] == 1
    assert by_barcode.json()["items"][0]["name"] == "Pepsi 600ml"


def test_products_filters_by_category_status_low_stock(
    client: TestClient, admin_user, make_category, make_product
) -> None:
    cat_a = make_category(name="A")
    cat_b = make_category(name="B")
    make_product(name="Prod A1", category=cat_a, stock=1, minimum_stock=5)
    make_product(name="Prod B1", category=cat_b, stock=50, minimum_stock=5)

    by_category = client.get(
        f"/api/products?category_id={cat_a.id}", headers=auth_headers(admin_user)
    )
    assert by_category.json()["total"] == 1

    only_active = client.get(
        "/api/products?is_active=true", headers=auth_headers(admin_user)
    )
    total_active = only_active.json()["total"]

    low = client.get("/api/products?low_stock=true", headers=auth_headers(admin_user))
    items = low.json()["items"]
    assert low.json()["total"] >= 1
    assert all(p["stock"] <= p["minimum_stock"] for p in items)

    inactive_filter = client.get(
        "/api/products?is_active=false", headers=auth_headers(admin_user)
    )
    assert inactive_filter.json()["total"] + total_active >= 2


def test_get_product_by_barcode_returns_active_product(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(barcode="7503333333333", sale_price="99.99", stock=7)
    response = client.get(
        "/api/products/barcode/7503333333333", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(product.id)
    assert data["sale_price"] == "99.99"
    assert data["stock"] == 7
    assert data["category"]["name"] is not None


def test_barcode_lookup_ignores_inactive_products(
    client: TestClient, admin_user, make_product
) -> None:
    make_product(barcode="7504444444444", is_active=False)
    response = client.get(
        "/api/products/barcode/7504444444444", headers=auth_headers(admin_user)
    )
    assert response.status_code == 404


def test_update_product_fields(client: TestClient, admin_user, make_product) -> None:
    product = make_product()
    response = client.patch(
        f"/api/products/{product.id}",
        json={"sale_price": "22.75", "minimum_stock": 10},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sale_price"] == "22.75"
    assert data["minimum_stock"] == 10


def test_deactivate_product_via_delete(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product()
    delete_response = client.delete(
        f"/api/products/{product.id}", headers=auth_headers(admin_user)
    )
    assert delete_response.status_code == 204
    get_response = client.get(
        f"/api/products/{product.id}", headers=auth_headers(admin_user)
    )
    assert get_response.json()["is_active"] is False


def test_cashier_cannot_create_or_update_products(
    client: TestClient, cashier_user, make_category
) -> None:
    category = make_category()
    headers = auth_headers(cashier_user)

    create_response = client.post(
        "/api/products",
        json=product_payload(category.id),
        headers=headers,
    )
    assert create_response.status_code == 403

    read_response = client.get("/api/products", headers=headers)
    assert read_response.status_code == 200


def test_inventory_manager_has_full_product_crud(
    client: TestClient, inventory_manager_user, make_category
) -> None:
    category = make_category()
    headers = auth_headers(inventory_manager_user)

    created = client.post(
        "/api/products",
        json=product_payload(category.id),
        headers=headers,
    )
    assert created.status_code == 201

    updated = client.patch(
        f"/api/products/{created.json()['id']}",
        json={"minimum_stock": 8},
        headers=headers,
    )
    assert updated.status_code == 200

    deleted = client.delete(
        f"/api/products/{created.json()['id']}", headers=headers
    )
    assert deleted.status_code == 204


def test_products_require_authentication(client: TestClient) -> None:
    assert client.get("/api/products").status_code == 401
