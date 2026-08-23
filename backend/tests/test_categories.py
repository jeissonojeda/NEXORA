from fastapi.testclient import TestClient

from tests.conftest import auth_headers

CATEGORY_PAYLOAD = {"name": "Lácteos", "description": "Leche y derivados"}


def test_admin_can_create_category(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/categories", json=CATEGORY_PAYLOAD, headers=auth_headers(admin_user)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Lácteos"
    assert data["is_active"] is True


def test_create_category_with_duplicate_name_returns_409(
    client: TestClient, admin_user, make_category
) -> None:
    make_category(name="Panadería")
    response = client.post(
        "/api/categories",
        json={"name": "Panadería"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CATEGORY_NAME_ALREADY_EXISTS"


def test_get_category_by_id(client: TestClient, admin_user, make_category) -> None:
    category = make_category(name="Bebidas")
    response = client.get(
        f"/api/categories/{category.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Bebidas"


def test_update_category(client: TestClient, admin_user, make_category) -> None:
    category = make_category(name="Viejo nombre")
    response = client.patch(
        f"/api/categories/{category.id}",
        json={"name": "Nuevo nombre", "description": "Actualizada"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nuevo nombre"
    assert data["description"] == "Actualizada"


def test_delete_category_without_products_deactivates_it(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category(name="Temporal")
    response = client.delete(
        f"/api/categories/{category.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 204
    get_response = client.get(
        f"/api/categories/{category.id}", headers=auth_headers(admin_user)
    )
    assert get_response.json()["is_active"] is False


def test_delete_category_in_use_returns_409(
    client: TestClient, admin_user, make_category, make_product
) -> None:
    category = make_category(name="En uso")
    make_product(category=category)
    response = client.delete(
        f"/api/categories/{category.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CATEGORY_IN_USE"


def test_cashier_can_read_categories_but_not_create(
    client: TestClient, cashier_user
) -> None:
    read_response = client.get("/api/categories", headers=auth_headers(cashier_user))
    assert read_response.status_code == 200

    create_response = client.post(
        "/api/categories", json=CATEGORY_PAYLOAD, headers=auth_headers(cashier_user)
    )
    assert create_response.status_code == 403
    assert create_response.json()["error_code"] == "PERMISSION_DENIED"


def test_inventory_manager_has_full_category_crud(
    client: TestClient, inventory_manager_user
) -> None:
    headers = auth_headers(inventory_manager_user)

    created = client.post("/api/categories", json={"name": "Limpieza"}, headers=headers)
    assert created.status_code == 201
    category_id = created.json()["id"]

    updated = client.patch(
        f"/api/categories/{category_id}",
        json={"description": "Productos de limpieza"},
        headers=headers,
    )
    assert updated.status_code == 200

    listed = client.get("/api/categories", headers=headers)
    assert listed.status_code == 200

    deleted = client.delete(f"/api/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204


def test_categories_require_authentication(client: TestClient) -> None:
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/categories", json=CATEGORY_PAYLOAD).status_code == 401


def test_create_category_with_blank_name_rejected(
    client: TestClient, admin_user
) -> None:
    response = client.post(
        "/api/categories", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 422
