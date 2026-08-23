from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD, auth_headers


def login_and_get_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", data={"username": username, "password": TEST_PASSWORD}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_entry_increases_stock_and_creates_movement(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=100)
    response = client.post(
        "/api/inventory/entries",
        json={"product_id": str(product.id), "quantity": 15,
              "reason": "Compra a proveedor"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    movement = response.json()
    assert movement["movement_type"] == "ENTRY"
    assert movement["quantity"] == 15
    assert movement["previous_stock"] == 100
    assert movement["new_stock"] == 115
    assert movement["created_by"] == str(admin_user.id)
    assert movement["created_by_username"] == admin_user.username


def test_exit_decreases_stock(client: TestClient, admin_user, make_product) -> None:
    product = make_product(stock=100)
    response = client.post(
        "/api/inventory/exits",
        json={"product_id": str(product.id), "quantity": 15},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    movement = response.json()
    assert movement["movement_type"] == "EXIT"
    assert movement["previous_stock"] == 100
    assert movement["new_stock"] == 85


def test_exit_with_insufficient_stock_returns_409(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=10)
    response = client.post(
        "/api/inventory/exits",
        json={"product_id": str(product.id), "quantity": 50},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "INSUFFICIENT_STOCK"

    get_response = client.get(
        f"/api/products/{product.id}", headers=auth_headers(admin_user)
    )
    assert get_response.json()["stock"] == 10


def test_adjustment_sets_absolute_stock(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=30)
    response = client.post(
        "/api/inventory/adjustments",
        json={"product_id": str(product.id), "new_stock": 22,
              "reason": "Conteo físico"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    movement = response.json()
    assert movement["quantity"] == 8
    assert movement["previous_stock"] == 30
    assert movement["new_stock"] == 22


def test_adjustment_without_change_rejected(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=30)
    response = client.post(
        "/api/inventory/adjustments",
        json={"product_id": str(product.id), "new_stock": 30,
              "reason": "Sin cambios"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422


def test_return_adds_stock(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=5)
    response = client.post(
        "/api/inventory/returns",
        json={"product_id": str(product.id), "quantity": 2,
              "reason": "Devolución de cliente"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    movement = response.json()
    assert movement["movement_type"] == "RETURN"
    assert movement["previous_stock"] == 5
    assert movement["new_stock"] == 7


def test_negative_or_zero_quantity_rejected(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=10)
    for quantity in (0, -5):
        for endpoint in ("entries", "exits", "returns"):
            response = client.post(
                f"/api/inventory/{endpoint}",
                json={"product_id": str(product.id), "quantity": quantity},
                headers=auth_headers(admin_user),
            )
            assert response.status_code == 422


def test_operation_on_inactive_product_rejected(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(is_active=False)
    response = client.post(
        "/api/inventory/entries",
        json={"product_id": str(product.id), "quantity": 1},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "PRODUCT_INACTIVE"


def test_movements_are_immutable_no_update_or_delete_endpoints(
    client: TestClient, admin_user, make_product
) -> None:
    product = make_product(stock=10)
    created = client.post(
        "/api/inventory/entries",
        json={"product_id": str(product.id), "quantity": 1},
        headers=auth_headers(admin_user),
    )
    movement_id = created.json()["id"]

    patch_response = client.patch(
        f"/api/inventory/movements/{movement_id}",
        json={"quantity": 99},
        headers=auth_headers(admin_user),
    )
    assert patch_response.status_code in (404, 405)

    delete_response = client.delete(
        f"/api/inventory/movements/{movement_id}",
        headers=auth_headers(admin_user),
    )
    assert delete_response.status_code in (404, 405)

    get_response = client.get(
        f"/api/inventory/movements/{movement_id}", headers=auth_headers(admin_user)
    )
    assert get_response.status_code == 200
    assert get_response.json()["quantity"] == 1


def test_movements_listing_filters(
    client: TestClient, admin_user, cashier_user, make_product
) -> None:
    product_a = make_product(stock=10)
    product_b = make_product(stock=20)

    headers_admin = auth_headers(admin_user)
    client.post("/api/inventory/entries",
                json={"product_id": str(product_a.id), "quantity": 3},
                headers=headers_admin)
    client.post("/api/inventory/exits",
                json={"product_id": str(product_b.id), "quantity": 2},
                headers=headers_admin)
    client.post("/api/inventory/returns",
                json={"product_id": str(product_a.id), "quantity": 1},
                headers=headers_admin)

    by_product = client.get(
        f"/api/inventory/movements?product_id={product_a.id}",
        headers=headers_admin,
    )
    assert by_product.json()["total"] == 2

    by_type = client.get(
        "/api/inventory/movements?movement_type=EXIT", headers=headers_admin
    )
    assert by_type.json()["total"] == 1

    by_user = client.get(
        f"/api/inventory/movements?created_by={admin_user.id}",
        headers=headers_admin,
    )
    assert by_user.json()["total"] == 3

    invalid_date = client.get(
        "/api/inventory/movements?date_from=2099-01-01T00:00:00",
        headers=headers_admin,
    )
    assert invalid_date.json()["total"] == 0

    all_movements = client.get("/api/inventory/movements", headers=headers_admin)
    assert all_movements.json()["total"] == 3


def test_low_stock_endpoint_lists_products_needing_attention(
    client: TestClient, admin_user, make_category, make_product
) -> None:
    category = make_category()
    low_product = make_product(
        name="Bajo stock", category=category, stock=2, minimum_stock=5
    )
    make_product(name="Stock ok", category=category, stock=50, minimum_stock=5)
    make_product(
        name="Inactivo bajo", category=category, stock=0, minimum_stock=5,
        is_active=False,
    )

    response = client.get("/api/inventory/low-stock", headers=auth_headers(admin_user))
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert str(low_product.id) in ids
    assert len(ids) == 1


def test_cashier_can_read_inventory_but_not_modify(
    client: TestClient, cashier_user, admin_user, make_product
) -> None:
    product = make_product(stock=10)
    cashier_headers = auth_headers(cashier_user)

    movements_response = client.get(
        "/api/inventory/movements", headers=cashier_headers
    )
    assert movements_response.status_code == 200

    low_stock_response = client.get("/api/inventory/low-stock", headers=cashier_headers)
    assert low_stock_response.status_code == 200

    entry_response = client.post(
        "/api/inventory/entries",
        json={"product_id": str(product.id), "quantity": 5},
        headers=cashier_headers,
    )
    assert entry_response.status_code == 403

    adjustment_response = client.post(
        "/api/inventory/adjustments",
        json={"product_id": str(product.id), "new_stock": 99, "reason": "hack"},
        headers=cashier_headers,
    )
    assert adjustment_response.status_code == 403


def test_inventory_manager_can_perform_all_operations(
    client: TestClient, inventory_manager_user, make_product
) -> None:
    product = make_product(stock=10)
    headers = auth_headers(inventory_manager_user)

    entry = client.post(
        "/api/inventory/entries",
        json={"product_id": str(product.id), "quantity": 5},
        headers=headers,
    )
    assert entry.status_code == 201

    exit_op = client.post(
        "/api/inventory/exits",
        json={"product_id": str(product.id), "quantity": 3},
        headers=headers,
    )
    assert exit_op.status_code == 201

    adjustment = client.post(
        "/api/inventory/adjustments",
        json={"product_id": str(product.id), "new_stock": 20, "reason": "conteo"},
        headers=headers,
    )
    assert adjustment.status_code == 201

    returned = client.post(
        "/api/inventory/returns",
        json={"product_id": str(product.id), "quantity": 2},
        headers=headers,
    )
    assert returned.status_code == 201


def test_integration_full_flow_create_entry_exit_low_stock(
    client: TestClient, admin_user, make_category
) -> None:
    headers = auth_headers(admin_user)

    category_response = client.post(
        "/api/categories", json={"name": "Abarrotes"}, headers=headers
    )
    category_id = category_response.json()["id"]

    product_response = client.post(
        "/api/products",
        json={
            "name": "Fideos 500g",
            "barcode": "7509999999999",
            "sale_price": "8.50",
            "category_id": category_id,
            "stock": 0,
            "minimum_stock": 10,
        },
        headers=headers,
    )
    product_id = product_response.json()["id"]

    client.post(
        "/api/inventory/entries",
        json={"product_id": product_id, "quantity": 50, "reason": "compra inicial"},
        headers=headers,
    )

    client.post(
        "/api/inventory/exits",
        json={"product_id": product_id, "quantity": 45},
        headers=headers,
    )

    final_product = client.get(f"/api/products/{product_id}", headers=headers).json()
    assert final_product["stock"] == 5
    assert final_product["stock"] <= final_product["minimum_stock"]

    low_response = client.get("/api/inventory/low-stock", headers=headers)
    assert product_id in [p["id"] for p in low_response.json()]

    movements_response = client.get(
        f"/api/inventory/movements?product_id={product_id}", headers=headers
    ).json()
    assert movements_response["total"] == 2
    types = {m["movement_type"] for m in movements_response["items"]}
    assert types == {"ENTRY", "EXIT"}

    by_type = {m["movement_type"]: m for m in movements_response["items"]}
    entry = by_type["ENTRY"]
    exit_movement = by_type["EXIT"]
    assert (entry["previous_stock"], entry["new_stock"]) == (0, 50)
    assert (exit_movement["previous_stock"], exit_movement["new_stock"]) == (50, 5)


def test_sequential_exits_beyond_stock_fail_consistently(
    client: TestClient, admin_user, make_product
) -> None:
    """Simulación de carrera: dos salidas concurrentes sobre stock limitado.

    En SQLite el lock FOR UPDATE no aplica; la prueba verifica el invariant
    lógico del servicio. La protección real (SELECT ... FOR UPDATE + CHECK
    stock>=0) se ejerce en PostgreSQL.
    """
    product = make_product(stock=10)
    headers = auth_headers(admin_user)

    first_exit = client.post(
        "/api/inventory/exits",
        json={"product_id": str(product.id), "quantity": 7},
        headers=headers,
    )
    second_exit = client.post(
        "/api/inventory/exits",
        json={"product_id": str(product.id), "quantity": 5},
        headers=headers,
    )

    assert first_exit.status_code == 201
    assert second_exit.status_code == 409

    current = client.get(f"/api/products/{product.id}", headers=headers).json()
    assert current["stock"] == 3
