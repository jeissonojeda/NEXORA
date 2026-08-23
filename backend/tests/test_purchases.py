from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.purchase import PurchaseStatuses
from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_purchase(
    client: TestClient,
    user,
    supplier_id,
    items: list[dict] | None = None,
    **overrides,
):
    payload = {"supplier_id": str(supplier_id)}
    if items is not None:
        payload["items"] = items
    payload.update(overrides)
    return client.post("/api/purchases", json=payload, headers=auth_headers(user))


@pytest.fixture()
def item_factory(make_product):
    counter = {"n": 0}

    def _item(
        quantity: int = 10,
        unit_cost: str = "5000.00",
        discount: str = "0",
        tax: str = "0",
        **product_kwargs,
    ) -> dict:
        counter["n"] += 1
        product = make_product(
            name=f"Producto compra {counter['n']}", **product_kwargs
        )
        return {
            "product_id": str(product.id),
            "quantity": quantity,
            "unit_cost": unit_cost,
            "discount": discount,
            "tax": tax,
        }

    return _item


def _add_item(client: TestClient, user, purchase_id: str, item: dict):
    return client.post(
        f"/api/purchases/{purchase_id}/items", json=item, headers=auth_headers(user)
    )


# ---------------------------------------------------------------------------
# Creación de compras (DRAFT)
# ---------------------------------------------------------------------------


def test_create_purchase_draft_defaults(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()

    response = _create_purchase(client, admin_user, supplier.id)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == PurchaseStatuses.DRAFT
    assert data["supplier"]["id"] == str(supplier.id)
    assert data["subtotal"] == "0.00"
    assert data["discount"] == "0.00"
    assert data["tax"] == "0.00"
    assert data["total"] == "0.00"
    assert data["confirmed_at"] is None
    assert data["items"] == []
    assert data["created_by"] == str(admin_user.id)
    assert data["created_by_username"] == admin_user.username
    assert data["purchase_number"].startswith("COMP-")


def test_create_purchase_numbers_unique_and_sequential(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    first = _create_purchase(client, admin_user, supplier.id).json()
    second = _create_purchase(client, admin_user, supplier.id).json()

    assert first["purchase_number"] != second["purchase_number"]
    seq_first = int(first["purchase_number"].rsplit("-", 1)[1])
    seq_second = int(second["purchase_number"].rsplit("-", 1)[1])
    assert seq_second == seq_first + 1


# ---------------------------------------------------------------------------
# Cálculos con Decimal
# ---------------------------------------------------------------------------


def test_item_calculations_quantity_times_unit_cost(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    items = [item_factory(quantity=10, unit_cost="5000.00")]

    data = _create_purchase(client, admin_user, supplier.id, items=items).json()

    assert Decimal(data["items"][0]["subtotal"]) == Decimal("50000.00")
    assert Decimal(data["items"][0]["total"]) == Decimal("50000.00")
    assert Decimal(data["subtotal"]) == Decimal("50000.00")
    assert Decimal(data["total"]) == Decimal("50000.00")


def test_item_total_is_subtotal_minus_discount_plus_tax(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    items = [
        item_factory(quantity=3, unit_cost="1500.50", discount="100", tax="47.52")
    ]

    data = _create_purchase(client, admin_user, supplier.id, items=items).json()

    # subtotal = 3 × 1500.50 = 4501.50; total = 4501.50 - 100 + 47.52
    assert Decimal(data["items"][0]["subtotal"]) == Decimal("4501.50")
    assert Decimal(data["items"][0]["total"]) == Decimal("4449.02")


def test_header_totals_sum_items_minus_discount_plus_tax(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    items = [
        item_factory(quantity=10, unit_cost="5000.00"),
        item_factory(quantity=3, unit_cost="1500.50"),
    ]

    data = _create_purchase(
        client, admin_user, supplier.id, items=items, discount="250", tax="300"
    ).json()

    assert Decimal(data["subtotal"]) == Decimal("54501.50")
    assert Decimal(data["total"]) == Decimal("54551.50")


def test_item_discount_above_subtotal_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    items = [item_factory(quantity=1, unit_cost="10.00", discount="50")]

    response = _create_purchase(client, admin_user, supplier.id, items=items)

    assert response.status_code == 422
    assert response.json()["error_code"] == "ITEM_DISCOUNT_EXCEEDS_SUBTOTAL"


def test_header_discount_above_subtotal_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    items = [item_factory(quantity=1, unit_cost="10.00")]

    response = _create_purchase(
        client, admin_user, supplier.id, items=items, discount="99"
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "DISCOUNT_EXCEEDS_SUBTOTAL"


def test_snapshot_survives_later_product_price_changes(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    item_factory,
) -> None:
    from app.models.product import Product

    supplier = make_supplier()
    item = item_factory(quantity=2, unit_cost="1000.00")
    created = _create_purchase(
        client, admin_user, supplier.id, items=[item]
    ).json()

    product_id = UUID(created["items"][0]["product_id"])
    product = db_session.get(Product, product_id)
    product.purchase_price = Decimal("9999.00")
    db_session.commit()

    detail = client.get(
        f"/api/purchases/{created['id']}", headers=auth_headers(admin_user)
    ).json()

    assert Decimal(detail["items"][0]["unit_cost"]) == Decimal("1000.00")
    assert Decimal(detail["items"][0]["subtotal"]) == Decimal("2000.00")


# ---------------------------------------------------------------------------
# Validaciones de ítems y proveedor
# ---------------------------------------------------------------------------


def test_create_purchase_supplier_not_found(
    client: TestClient, admin_user
) -> None:
    response = _create_purchase(client, admin_user, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error_code"] == "SUPPLIER_NOT_FOUND"


def test_create_purchase_supplier_inactive(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier(is_active=False)
    response = _create_purchase(client, admin_user, supplier.id)
    assert response.status_code == 409
    assert response.json()["error_code"] == "SUPPLIER_INACTIVE"


def test_add_item_to_draft_recalculates_totals(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = _add_item(
        client, admin_user, purchase["id"], item_factory(quantity=4, unit_cost="250.00")
    )

    assert response.status_code == 201
    detail = client.get(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    ).json()
    assert len(detail["items"]) == 1
    assert Decimal(detail["subtotal"]) == Decimal("1000.00")
    assert Decimal(detail["total"]) == Decimal("1000.00")


def test_add_item_invalid_quantity_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()
    item = item_factory(quantity=0)

    response = _add_item(client, admin_user, purchase["id"], item)

    assert response.status_code == 422


def test_add_item_negative_cost_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()
    item = item_factory(unit_cost="-5")

    response = _add_item(client, admin_user, purchase["id"], item)

    assert response.status_code == 422


def test_add_item_product_not_found(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = _add_item(
        client,
        admin_user,
        purchase["id"],
        {
            "product_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
            "unit_cost": "10.00",
        },
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "PRODUCT_NOT_FOUND"


def test_add_item_product_inactive_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()
    item = item_factory(is_active=False)

    response = _add_item(client, admin_user, purchase["id"], item)

    assert response.status_code == 409
    assert response.json()["error_code"] == "PRODUCT_INACTIVE"


def test_add_item_duplicate_product_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    item = item_factory(quantity=1, unit_cost="10.00")
    purchase = _create_purchase(
        client, admin_user, supplier.id, items=[item]
    ).json()

    duplicate = dict(item)
    duplicate["quantity"] = 2
    response = _add_item(client, admin_user, purchase["id"], duplicate)

    assert response.status_code == 409
    assert response.json()["error_code"] == "PURCHASE_ITEM_DUPLICATE_PRODUCT"


def test_create_purchase_with_duplicate_products_rejected(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    item = item_factory(quantity=1, unit_cost="10.00")
    duplicate = dict(item)

    response = _create_purchase(
        client, admin_user, supplier.id, items=[item, duplicate]
    )

    assert response.status_code == 409


def test_update_item_recalculates_totals(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(
        client, admin_user, supplier.id, items=[item_factory(quantity=1,
                                                           unit_cost="100.00")]
    ).json()
    item_id = purchase["items"][0]["id"]

    response = client.patch(
        f"/api/purchases/{purchase['id']}/items/{item_id}",
        json={"quantity": 5, "unit_cost": "200.00"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert Decimal(response.json()["subtotal"]) == Decimal("1000.00")

    detail = client.get(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    ).json()
    assert Decimal(detail["subtotal"]) == Decimal("1000.00")
    assert Decimal(detail["total"]) == Decimal("1000.00")


def test_remove_item_recalculates_totals(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[
            item_factory(quantity=1, unit_cost="100.00"),
            item_factory(quantity=2, unit_cost="300.00"),
        ],
    ).json()
    first_item_id = purchase["items"][0]["id"]

    response = client.delete(
        f"/api/purchases/{purchase['id']}/items/{first_item_id}",
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 204

    detail = client.get(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    ).json()
    assert len(detail["items"]) == 1
    assert Decimal(detail["subtotal"]) == Decimal("600.00")


# ---------------------------------------------------------------------------
# Edición de encabezado
# ---------------------------------------------------------------------------


def test_update_draft_header_recalculates(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    other_supplier = make_supplier(name="Proveedor alternativo")
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[item_factory(quantity=2, unit_cost="500.00")],
    ).json()

    response = client.patch(
        f"/api/purchases/{purchase['id']}",
        json={"supplier_id": str(other_supplier.id), "notes": "urgente",
              "discount": "100", "tax": "50"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["supplier"]["id"] == str(other_supplier.id)
    assert data["notes"] == "urgente"
    assert Decimal(data["total"]) == Decimal("950.00")


# ---------------------------------------------------------------------------
# Listado, filtros y paginación
# ---------------------------------------------------------------------------


def test_list_purchases_paginated_and_filtered(
    client: TestClient, admin_user, inventory_manager_user, make_supplier,
    item_factory,
) -> None:
    supplier_a = make_supplier(name="Proveedor A")
    supplier_b = make_supplier(name="Proveedor B")
    for _ in range(3):
        _create_purchase(
            client, admin_user, supplier_a.id, items=[item_factory()]
        )
    draft_b = _create_purchase(
        client, admin_user, supplier_b.id, items=[item_factory()]
    ).json()
    client.post(
        f"/api/purchases/{draft_b['id']}/confirm",
        headers=auth_headers(inventory_manager_user),
    )

    all_rows = client.get(
        "/api/purchases?limit=2&skip=1", headers=auth_headers(admin_user)
    ).json()
    assert all_rows["total"] == 4
    assert len(all_rows["items"]) == 2

    confirmed = client.get(
        "/api/purchases?status=CONFIRMED", headers=auth_headers(admin_user)
    ).json()
    assert confirmed["total"] == 1
    assert confirmed["items"][0]["status"] == PurchaseStatuses.CONFIRMED

    by_supplier = client.get(
        f"/api/purchases?supplier_id={supplier_b.id}",
        headers=auth_headers(admin_user),
    ).json()
    assert by_supplier["total"] == 1

    by_number = client.get(
        f"/api/purchases?q={draft_b['purchase_number']}",
        headers=auth_headers(admin_user),
    ).json()
    assert by_number["total"] == 1
    assert by_number["items"][0]["id"] == draft_b["id"]
