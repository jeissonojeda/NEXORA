from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def supplier_payload(**overrides) -> dict:
    payload = {
        "name": "Distribuidora Alimenticia S.A.",
        "identification": "310123456789",
        "contact_name": "María Rodríguez",
        "phone": "+506 8888-1234",
        "email": "ventas@distribuidora.example.com",
        "address": "Bodegas 4-8, Zona Industrial",
        "city": "San José",
        "notes": "Entrega los martes y viernes",
    }
    payload.update(overrides)
    return payload


def product_with_supplier_payload(category_id, supplier_id, **overrides) -> dict:
    payload = {
        "name": "Arroz 5kg",
        "purchase_price": "3000.00",
        "sale_price": "4500.00",
        "category_id": str(category_id),
        "supplier_id": str(supplier_id),
        "stock": 20,
        "minimum_stock": 4,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_admin_can_create_supplier(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/suppliers", json=supplier_payload(), headers=auth_headers(admin_user)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Distribuidora Alimenticia S.A."
    assert data["identification"] == "310123456789"
    assert data["city"] == "San José"
    assert data["is_active"] is True


def test_create_supplier_without_optional_fields(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/suppliers",
        json={"name": "Proveedor mínimo"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["identification"] is None
    assert data["email"] is None
    assert data["is_active"] is True


def test_get_supplier_returns_products_count(
    client: TestClient, admin_user, make_supplier, make_product
) -> None:
    supplier = make_supplier(name="Con productos")
    make_product(supplier=supplier)
    make_product(supplier=supplier)

    response = client.get(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["products_count"] == 2


def test_update_supplier_fields(client: TestClient, admin_user, make_supplier) -> None:
    supplier = make_supplier(name="Nombre viejo", city="Heredia")
    response = client.patch(
        f"/api/suppliers/{supplier.id}",
        json={"contact_name": "Nuevo contacto", "phone": "+506 2222-0000"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contact_name"] == "Nuevo contacto"
    assert data["phone"] == "+506 2222-0000"
    assert data["city"] == "Heredia"


def test_update_supplier_can_clear_identification(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier(identification="400999999998")
    response = client.patch(
        f"/api/suppliers/{supplier.id}",
        json={"identification": None},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["identification"] is None


def test_delete_supplier_deactivates_logically(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier(name="Para desactivar")
    response = client.delete(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 204

    get_response = client.get(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


def test_get_nonexistent_supplier_returns_404(client: TestClient, admin_user) -> None:
    response = client.get(
        f"/api/suppliers/{uuid4()}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "SUPPLIER_NOT_FOUND"


def test_update_and_delete_nonexistent_supplier_fail(
    client: TestClient, admin_user
) -> None:
    missing = uuid4()
    patch_response = client.patch(
        f"/api/suppliers/{missing}",
        json={"name": "X"},
        headers=auth_headers(admin_user),
    )
    assert patch_response.status_code == 404

    delete_response = client.delete(
        f"/api/suppliers/{missing}", headers=auth_headers(admin_user)
    )
    assert delete_response.status_code == 404


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------


def test_create_supplier_without_name_rejected(client: TestClient, admin_user) -> None:
    for payload in ({}, {"name": ""}):
        response = client.post(
            "/api/suppliers", json=payload, headers=auth_headers(admin_user)
        )
        assert response.status_code == 422


def test_create_supplier_duplicate_identification_returns_409(
    client: TestClient, admin_user, make_supplier
) -> None:
    make_supplier(identification="310111222333")
    payload = supplier_payload(
        name="Otro nombre distinto", identification="310111222333"
    )
    response = client.post(
        "/api/suppliers", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert (
        response.json()["error_code"] == "SUPPLIER_IDENTIFICATION_ALREADY_EXISTS"
    )


def test_update_supplier_to_existing_identification_returns_409(
    client: TestClient, admin_user, make_supplier
) -> None:
    make_supplier(identification="310444555666")
    other = make_supplier(identification="310777888999")
    response = client.patch(
        f"/api/suppliers/{other.id}",
        json={"identification": "310444555666"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409


def test_create_supplier_invalid_email_rejected(
    client: TestClient, admin_user
) -> None:
    payload = supplier_payload(email="no-es-un-email")
    response = client.post(
        "/api/suppliers", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 422


def test_update_supplier_invalid_email_rejected(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    response = client.patch(
        f"/api/suppliers/{supplier.id}",
        json={"email": "invalido@"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422


def test_phone_stored_as_text_with_prefixes(
    client: TestClient, admin_user
) -> None:
    phone = "+506 (506) 8888-0000 ext. 12"
    payload = supplier_payload(name="Teléfono raro", phone=phone)
    response = client.post(
        "/api/suppliers", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 201
    assert response.json()["phone"] == phone


def test_blank_optional_fields_become_null(client: TestClient, admin_user) -> None:
    payload = supplier_payload(
        identification="   ",
        email=None,
        phone="  ",
        city=" ",
        notes="",
    )
    response = client.post(
        "/api/suppliers", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["identification"] is None
    assert data["phone"] is None
    assert data["city"] is None
    assert data["notes"] is None


# ---------------------------------------------------------------------------
# Relación Supplier ↔ Product
# ---------------------------------------------------------------------------


def test_product_can_be_created_with_supplier(
    client: TestClient, admin_user, make_category, make_supplier
) -> None:
    category = make_category()
    supplier = make_supplier(name="Con producto activo")
    response = client.post(
        "/api/products",
        json=product_with_supplier_payload(category.id, supplier.id),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["supplier"]["id"] == str(supplier.id)


def test_inactive_supplier_cannot_be_assigned_to_new_active_product(
    client: TestClient, admin_user, make_category, make_supplier
) -> None:
    category = make_category()
    supplier = make_supplier(is_active=False)
    response = client.post(
        "/api/products",
        json=product_with_supplier_payload(category.id, supplier.id),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "SUPPLIER_INACTIVE"


def test_nonexistent_supplier_cannot_be_assigned(
    client: TestClient, admin_user, make_category
) -> None:
    category = make_category()
    response = client.post(
        "/api/products",
        json=product_with_supplier_payload(category.id, uuid4()),
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_SUPPLIER"


def test_inactive_product_can_keep_inactive_supplier(
    client: TestClient, admin_user, make_category, make_product, make_supplier
) -> None:
    category = make_category()
    supplier = make_supplier(is_active=False)
    product = make_product(category=category, is_active=False, supplier=supplier)

    # Cambios que no alteran el estado activo no deben fallar.
    response = client.patch(
        f"/api/products/{product.id}",
        json={"minimum_stock": 1},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["supplier"]["id"] == str(supplier.id)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_cashier_can_read_but_not_modify_suppliers(
    client: TestClient, cashier_user, make_supplier
) -> None:
    supplier = make_supplier(name="Solo lectura cajero")
    headers = auth_headers(cashier_user)

    assert client.get("/api/suppliers", headers=headers).status_code == 200
    detail = client.get(f"/api/suppliers/{supplier.id}", headers=headers)
    assert detail.status_code == 200
    products_list = client.get(
        f"/api/suppliers/{supplier.id}/products", headers=headers
    )
    assert products_list.status_code == 200

    create_response = client.post(
        "/api/suppliers", json={"name": "No permitido"}, headers=headers
    )
    assert create_response.status_code == 403
    assert create_response.json()["error_code"] == "PERMISSION_DENIED"

    update_response = client.patch(
        f"/api/suppliers/{supplier.id}", json={"city": "X"}, headers=headers
    )
    assert update_response.status_code == 403

    delete_response = client.delete(
        f"/api/suppliers/{supplier.id}", headers=headers
    )
    assert delete_response.status_code == 403


def test_inventory_manager_has_full_supplier_crud(
    client: TestClient, inventory_manager_user
) -> None:
    headers = auth_headers(inventory_manager_user)

    created = client.post(
        "/api/suppliers", json={"name": "De encargado"}, headers=headers
    )
    assert created.status_code == 201
    supplier_id = created.json()["id"]

    updated = client.patch(
        f"/api/suppliers/{supplier_id}", json={"city": "Cartago"}, headers=headers
    )
    assert updated.status_code == 200

    listed = client.get("/api/suppliers", headers=headers)
    assert listed.status_code == 200

    deleted = client.delete(f"/api/suppliers/{supplier_id}", headers=headers)
    assert deleted.status_code == 204


def test_suppliers_require_authentication(client: TestClient) -> None:
    assert client.get("/api/suppliers").status_code == 401
    assert client.post("/api/suppliers", json={"name": "Anónimo"}).status_code == 401


# ---------------------------------------------------------------------------
# Listado: paginación, búsqueda, filtros, ordenamiento
# ---------------------------------------------------------------------------


def test_suppliers_pagination(client: TestClient, admin_user, make_supplier) -> None:
    for i in range(7):
        make_supplier(name=f"Paginado {i:02d}")

    page_one = client.get(
        "/api/suppliers?limit=5&skip=0&order_by=name",
        headers=auth_headers(admin_user),
    )
    body_one = page_one.json()
    assert page_one.status_code == 200
    assert len(body_one["items"]) == 5
    assert body_one["total"] >= 7

    page_two = client.get(
        "/api/suppliers?limit=5&skip=5&order_by=name",
        headers=auth_headers(admin_user),
    )
    names_one = {item["id"] for item in body_one["items"]}
    names_two = {item["id"] for item in page_two.json()["items"]}
    assert not (names_one & names_two)


def test_suppliers_search_by_name_identification_email_phone(
    client: TestClient, admin_user, make_supplier
) -> None:
    make_supplier(
        name="Comercial Buena Vista",
        identification="310000111222",
        email="contacto@buenavista.example.com",
        phone="+506 8877-6655",
    )

    by_name = client.get(
        "/api/suppliers?q=buena vista", headers=auth_headers(admin_user)
    )
    assert by_name.json()["total"] == 1

    by_identification = client.get(
        "/api/suppliers?q=310000111222", headers=auth_headers(admin_user)
    )
    assert by_identification.json()["total"] == 1
    assert by_identification.json()["items"][0]["email"] == (
        "contacto@buenavista.example.com"
    )

    by_email = client.get(
        "/api/suppliers?q=contacto@", headers=auth_headers(admin_user)
    )
    assert by_email.json()["total"] == 1

    by_phone = client.get("/api/suppliers?q=8877-6655", headers=auth_headers(admin_user))
    assert by_phone.json()["total"] == 1


def test_suppliers_filter_by_status(client: TestClient, admin_user, make_supplier) -> None:
    active = make_supplier(name="Filtro activo", is_active=True)
    inactive = make_supplier(name="Filtro inactivo", is_active=False)

    only_active = client.get(
        "/api/suppliers?is_active=true", headers=auth_headers(admin_user)
    )
    ids_active = [s["id"] for s in only_active.json()["items"]]
    assert str(active.id) in ids_active
    assert str(inactive.id) not in ids_active

    only_inactive = client.get(
        "/api/suppliers?is_active=false", headers=auth_headers(admin_user)
    )
    ids_inactive = [s["id"] for s in only_inactive.json()["items"]]
    assert str(inactive.id) in ids_inactive
    assert str(active.id) not in ids_inactive


def test_suppliers_safe_ordering(client: TestClient, admin_user, make_supplier) -> None:
    make_supplier(name="Zeta Ltda")
    make_supplier(name="Alpha Distribución")

    asc_response = client.get(
        "/api/suppliers?order_by=name&order=asc", headers=auth_headers(admin_user)
    )
    names_asc = [s["name"] for s in asc_response.json()["items"]]
    assert names_asc == sorted(names_asc)

    desc_response = client.get(
        "/api/suppliers?order_by=name&order=desc", headers=auth_headers(admin_user)
    )
    names_desc = [s["name"] for s in desc_response.json()["items"]]
    assert names_desc == sorted(names_desc, reverse=True)

    invalid_order = client.get(
        "/api/suppliers?order_by=notes", headers=auth_headers(admin_user)
    )
    assert invalid_order.status_code == 422


# ---------------------------------------------------------------------------
# Endpoint /suppliers/{id}/products
# ---------------------------------------------------------------------------


def test_supplier_products_listing_is_scoped_and_paginated(
    client: TestClient, admin_user, make_supplier, make_category, make_product
) -> None:
    supplier_a = make_supplier(name="Proveedor A")
    supplier_b = make_supplier(name="Proveedor B")
    category = make_category()

    for i in range(4):
        make_product(name=f"Item A{i}", category=category, supplier=supplier_a)
    make_product(name="Item B0", category=category, supplier=supplier_b)
    make_product(name="Sin proveedor", category=category)

    first_page = client.get(
        f"/api/suppliers/{supplier_a.id}/products?limit=2&skip=0",
        headers=auth_headers(admin_user),
    )
    body = first_page.json()
    assert first_page.status_code == 200
    assert body["total"] == 4
    assert len(body["items"]) == 2
    assert all(item["supplier"]["id"] == str(supplier_a.id) for item in body["items"])

    second_page = client.get(
        f"/api/suppliers/{supplier_a.id}/products?limit=2&skip=2",
        headers=auth_headers(admin_user),
    )
    assert second_page.json()["total"] == 4
    assert len(second_page.json()["items"]) == 2

    other = client.get(
        f"/api/suppliers/{supplier_b.id}/products", headers=auth_headers(admin_user)
    )
    assert other.json()["total"] == 1


def test_supplier_products_search_and_status_filter(
    client: TestClient, admin_user, make_supplier, make_category, make_product
) -> None:
    supplier = make_supplier(name="Con mix de productos")
    category = make_category()
    make_product(name="Galletas Oreo", category=category, supplier=supplier)
    inactive = make_product(
        name="Jugo Naranja", category=category, supplier=supplier, is_active=False
    )

    search = client.get(
        f"/api/suppliers/{supplier.id}/products?q=oreo",
        headers=auth_headers(admin_user),
    )
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["name"] == "Galletas Oreo"

    only_active = client.get(
        f"/api/suppliers/{supplier.id}/products?is_active=true",
        headers=auth_headers(admin_user),
    )
    ids = [p["id"] for p in only_active.json()["items"]]
    assert str(inactive.id) not in ids

    all_products = client.get(
        f"/api/suppliers/{supplier.id}/products", headers=auth_headers(admin_user)
    )
    assert all_products.json()["total"] == 2


def test_products_of_nonexistent_supplier_returns_404(
    client: TestClient, admin_user
) -> None:
    response = client.get(
        f"/api/suppliers/{uuid4()}/products", headers=auth_headers(admin_user)
    )
    assert response.status_code == 404


def test_products_endpoint_filters_by_supplier(
    client: TestClient, admin_user, make_supplier, make_category, make_product
) -> None:
    supplier_a = make_supplier(name="Filtro producto A")
    supplier_b = make_supplier(name="Filtro producto B")
    category = make_category()
    target = make_product(name="Del A", category=category, supplier=supplier_a)
    make_product(name="Del B", category=category, supplier=supplier_b)
    make_product(name="Sin proveedor", category=category)

    response = client.get(
        f"/api/products?supplier_id={supplier_a.id}", headers=auth_headers(admin_user)
    )
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(target.id)
    assert body["items"][0]["supplier"]["id"] == str(supplier_a.id)

    empty_for_b = client.get(
        f"/api/products?supplier_id={uuid4()}", headers=auth_headers(admin_user)
    )
    assert empty_for_b.json()["total"] == 0


# ---------------------------------------------------------------------------
# Integración E2E (sección 19 del plan)
# ---------------------------------------------------------------------------


def test_full_supplier_product_lifecycle(
    client: TestClient, admin_user, make_category
) -> None:
    """Crear proveedor → producto asociado → consulta → desactivar → rechazo."""
    headers = auth_headers(admin_user)
    category = make_category(name="Abarrotes")

    created = client.post(
        "/api/suppliers",
        json=supplier_payload(name="Ciclo completo S.A."),
        headers=headers,
    )
    assert created.status_code == 201
    supplier_id = created.json()["id"]

    product_created = client.post(
        "/api/products",
        json=product_with_supplier_payload(category.id, supplier_id),
        headers=headers,
    )
    assert product_created.status_code == 201
    product_id = product_created.json()["id"]

    detail = client.get(f"/api/suppliers/{supplier_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["products_count"] == 1

    supplier_products = client.get(
        f"/api/suppliers/{supplier_id}/products", headers=headers
    )
    assert supplier_products.json()["total"] == 1
    assert supplier_products.json()["items"][0]["id"] == product_id

    deactivated = client.delete(f"/api/suppliers/{supplier_id}", headers=headers)
    assert deactivated.status_code == 204

    rejected = client.post(
        "/api/products",
        json=product_with_supplier_payload(category.id, supplier_id, name="Otro más"),
        headers=headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["error_code"] == "SUPPLIER_INACTIVE"

    still_there = client.get(f"/api/products/{product_id}", headers=headers)
    assert still_there.status_code == 200
    assert still_there.json()["is_active"] is True
    assert still_there.json()["supplier"]["id"] == supplier_id

    reactivate_blocked = client.patch(
        f"/api/products/{product_created.json()['id']}",
        json={"sale_price": "5000.00"},
        headers=headers,
    )
    assert reactivate_blocked.status_code == 200


def test_reactivating_product_with_inactive_supplier_rejected(
    client: TestClient, admin_user, make_category, make_product, make_supplier
) -> None:
    category = make_category()
    supplier = make_supplier(name="Se desactiva después")
    product = make_product(category=category, supplier=supplier)

    deactivate_supplier_response = client.delete(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert deactivate_supplier_response.status_code == 204

    # Desactivar el producto directamente vía API.
    deactivate = client.delete(
        f"/api/products/{product.id}", headers=auth_headers(admin_user)
    )
    assert deactivate.status_code == 204

    reactivate = client.patch(
        f"/api/products/{product.id}",
        json={"is_active": True},
        headers=auth_headers(admin_user),
    )
    assert reactivate.status_code == 409
    assert reactivate.json()["error_code"] == "SUPPLIER_INACTIVE"


def test_deactivated_supplier_keeps_products_intact(
    client: TestClient, admin_user, make_supplier, make_category, make_product
) -> None:
    supplier = make_supplier(name="Historial preservado")
    category = make_category()
    p1 = make_product(name="Producto 1", category=category, supplier=supplier)
    p2 = make_product(name="Producto 2", category=category, supplier=supplier)

    delete_response = client.delete(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert delete_response.status_code == 204

    for product in (p1, p2):
        check = client.get(
            f"/api/products/{product.id}", headers=auth_headers(admin_user)
        )
        assert check.status_code == 200
        assert check.json()["is_active"] is True
        assert check.json()["supplier"]["id"] == str(supplier.id)

    detail = client.get(
        f"/api/suppliers/{supplier.id}", headers=auth_headers(admin_user)
    )
    assert detail.json()["is_active"] is False
    assert detail.json()["products_count"] == 2
