from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryMovement, MovementTypes
from app.models.purchase import MovementReferences, Purchase, PurchaseStatuses
from app.services.inventory_service import InventoryService
from tests.conftest import auth_headers


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
            name=f"Producto confirm {counter['n']}", **product_kwargs
        )
        return {
            "product_id": str(product.id),
            "quantity": quantity,
            "unit_cost": unit_cost,
            "discount": discount,
            "tax": tax,
        }

    return _item


def _confirmed_purchase(
    client: TestClient, user, supplier, item_factory, **item_kwargs
) -> dict:
    purchase = _create_purchase(
        client, user, supplier.id, items=[item_factory(**item_kwargs)]
    ).json()
    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm", headers=auth_headers(user)
    )
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# Confirmación DRAFT → CONFIRMED
# ---------------------------------------------------------------------------


def test_confirm_draft_updates_stock_and_creates_movement(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    make_product,
) -> None:
    supplier = make_supplier()
    product = make_product(stock=10)
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[
            {
                "product_id": str(product.id),
                "quantity": 10,
                "unit_cost": "5000.00",
            }
        ],
    ).json()

    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == PurchaseStatuses.CONFIRMED
    assert data["confirmed_at"] is not None

    db_session.expire_all()
    refreshed_product = db_session.get(type(product), product.id)
    assert refreshed_product.stock == 20

    movements = (
        db_session.query(InventoryMovement)
        .filter(InventoryMovement.product_id == product.id)
        .all()
    )
    assert len(movements) == 1
    movement = movements[0]
    assert movement.movement_type == MovementTypes.ENTRY
    assert movement.quantity == 10
    assert movement.previous_stock == 10
    assert movement.new_stock == 20
    assert movement.created_by == admin_user.id
    assert movement.reference_type == MovementReferences.PURCHASE
    assert movement.reference_id == purchase["id"]
    assert purchase["purchase_number"] in movement.reason


def test_confirm_empty_draft_rejected(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "PURCHASE_EMPTY"


def test_confirm_rejected_when_supplier_deactivated_after_draft(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    make_product,
    item_factory,
) -> None:
    from app.models.supplier import Supplier

    supplier = make_supplier(name="Proveedor a desactivar")
    item = item_factory(quantity=5)
    purchase = _create_purchase(client, admin_user, supplier.id, items=[item]).json()

    db_supplier = db_session.get(Supplier, supplier.id)
    db_supplier.is_active = False
    db_session.commit()

    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "SUPPLIER_INACTIVE"


def test_create_draft_with_multiple_items_keeps_stock_until_confirm(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    item_factory,
) -> None:
    """El builder en línea crea la compra con varios ítems en un solo POST.

    Mientras la compra sea DRAFT el stock no cambia; solo la confirmación
    aplica las entradas al inventario.
    """
    from app.models.product import Product

    supplier = make_supplier()
    item_a = item_factory(quantity=4, stock=0)
    item_b = item_factory(quantity=7, stock=0)
    product_a = UUID(item_a["product_id"])
    product_b = UUID(item_b["product_id"])

    created = _create_purchase(client, admin_user, supplier.id, items=[item_a, item_b])
    assert created.status_code == 201
    purchase = created.json()
    assert purchase["status"] == PurchaseStatuses.DRAFT
    assert len(purchase["items"]) == 2

    db_session.expire_all()
    assert db_session.get(Product, product_a).stock == 0
    assert db_session.get(Product, product_b).stock == 0
    assert db_session.query(InventoryMovement).count() == 0

    confirmed = client.post(
        f"/api/purchases/{purchase['id']}/confirm", headers=auth_headers(admin_user)
    )
    assert confirmed.status_code == 200

    db_session.expire_all()
    assert db_session.get(Product, product_a).stock == 4
    assert db_session.get(Product, product_b).stock == 7
    assert db_session.query(InventoryMovement).count() == 2


def test_create_purchase_with_duplicate_product_in_items_rejected(
    client: TestClient, admin_user, make_supplier, make_product
) -> None:
    supplier = make_supplier()
    product = make_product()
    item = {
        "product_id": str(product.id),
        "quantity": 1,
        "unit_cost": "10.00",
    }
    response = _create_purchase(client, admin_user, supplier.id, items=[item, item])
    assert response.status_code == 409
    assert response.json()["error_code"] == "PURCHASE_ITEM_DUPLICATE_PRODUCT"


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------


def test_double_confirmation_does_not_duplicate_stock_or_movements(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    make_product,
) -> None:
    supplier = make_supplier()
    product = make_product(stock=0)
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[
            {
                "product_id": str(product.id),
                "quantity": 10,
                "unit_cost": "1000.00",
            }
        ],
    ).json()

    first = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )
    second = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error_code"] == "PURCHASE_ALREADY_CONFIRMED"

    db_session.expire_all()
    refreshed = db_session.get(type(product), product.id)
    assert refreshed.stock == 10

    count = (
        db_session.query(InventoryMovement)
        .filter(InventoryMovement.reference_id == purchase["id"])
        .count()
    )
    assert count == 1


def test_cancelled_cannot_be_confirmed(
    client: TestClient,
    admin_user,
    db_session: Session,
    make_supplier,
    make_product,
) -> None:
    supplier = make_supplier()
    product = make_product(stock=3)
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[
            {
                "product_id": str(product.id),
                "quantity": 10,
                "unit_cost": "1000.00",
            }
        ],
    ).json()
    delete_response = client.delete(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    )
    assert delete_response.status_code == 204

    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "PURCHASE_CANCELLED"

    db_session.expire_all()
    assert db_session.get(type(product), product.id).stock == 3
    movements = (
        db_session.query(InventoryMovement)
        .filter(InventoryMovement.product_id == product.id)
        .count()
    )
    assert movements == 0


def test_delete_draft_cancels_logically(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = client.delete(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 204

    detail = client.get(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    ).json()
    assert detail["status"] == PurchaseStatuses.CANCELLED


def test_delete_twice_returns_conflict(
    client: TestClient, admin_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()
    client.delete(f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user))

    response = client.delete(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Estados: CONFIRMED es inmutable
# ---------------------------------------------------------------------------


def test_confirmed_cannot_be_edited(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    purchase = _confirmed_purchase(client, admin_user, make_supplier(), item_factory)

    header_patch = client.patch(
        f"/api/purchases/{purchase['id']}",
        json={"notes": "intento"},
        headers=auth_headers(admin_user),
    )
    assert header_patch.status_code == 409
    assert header_patch.json()["error_code"] == "PURCHASE_ALREADY_CONFIRMED"

    add_item = client.post(
        f"/api/purchases/{purchase['id']}/items",
        json={
            "product_id": purchase["items"][0]["product_id"],
            "quantity": 1,
            "unit_cost": "1.00",
        },
        headers=auth_headers(admin_user),
    )
    assert add_item.status_code == 409

    patch_item = client.patch(
        f"/api/purchases/{purchase['id']}/items/{purchase['items'][0]['id']}",
        json={"quantity": 99},
        headers=auth_headers(admin_user),
    )
    assert patch_item.status_code == 409

    delete_item = client.delete(
        f"/api/purchases/{purchase['id']}/items/{purchase['items'][0]['id']}",
        headers=auth_headers(admin_user),
    )
    assert delete_item.status_code == 409


def test_confirmed_cannot_be_deleted(
    client: TestClient, admin_user, make_supplier, item_factory
) -> None:
    purchase = _confirmed_purchase(client, admin_user, make_supplier(), item_factory)

    response = client.delete(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "PURCHASE_ALREADY_CONFIRMED"


# ---------------------------------------------------------------------------
# Transaccionalidad: rollback completo ante fallo
# ---------------------------------------------------------------------------


def test_confirmation_failure_rolls_back_completely(
    client: TestClient,
    admin_user,
    db_session: Session,
    monkeypatch,
    make_supplier,
    make_product,
) -> None:
    supplier = make_supplier()
    product_a = make_product(name="Prod A rollback", stock=5)
    product_b = make_product(name="Prod B rollback", stock=7)
    purchase = _create_purchase(
        client,
        admin_user,
        supplier.id,
        items=[
            {"product_id": str(product_a.id), "quantity": 10, "unit_cost": "1.00"},
            {"product_id": str(product_b.id), "quantity": 20, "unit_cost": "2.00"},
        ],
    ).json()

    real_apply_entry = InventoryService.apply_entry
    calls = {"n": 0}

    def failing_apply_entry(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("fallo simulado de inventario")
        return real_apply_entry(self, *args, **kwargs)

    monkeypatch.setattr(InventoryService, "apply_entry", failing_apply_entry)

    with pytest.raises(RuntimeError, match="fallo simulado"):
        client.post(
            f"/api/purchases/{purchase['id']}/confirm",
            headers=auth_headers(admin_user),
        )
    monkeypatch.undo()

    db_session.expire_all()
    # La compra permanece DRAFT.
    stored_status = db_session.scalar(
        select(Purchase.status).where(Purchase.id == UUID(purchase["id"]))
    )
    assert stored_status == PurchaseStatuses.DRAFT

    # El stock no cambia en ningún producto.
    assert db_session.get(type(product_a), product_a.id).stock == 5
    assert db_session.get(type(product_b), product_b.id).stock == 7

    # No quedan movimientos parciales.
    movements = db_session.query(InventoryMovement).count()
    assert movements == 0

    # Recuperación: ahora sí se puede confirmar.
    retry = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(admin_user),
    )
    assert retry.status_code == 200
    db_session.expire_all()
    assert db_session.get(type(product_a), product_a.id).stock == 15
    assert db_session.get(type(product_b), product_b.id).stock == 27
    assert (
        db_session.query(InventoryMovement)
        .filter(InventoryMovement.reference_type == MovementReferences.PURCHASE)
        .count()
        == 2
    )


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_cashier_can_list_purchases(client: TestClient, cashier_user) -> None:
    response = client.get("/api/purchases", headers=auth_headers(cashier_user))
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_cashier_can_get_purchase_detail(
    client: TestClient, admin_user, cashier_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(
        client, admin_user, supplier.id, items=[item_factory()]
    ).json()

    response = client.get(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(cashier_user)
    )
    assert response.status_code == 200


def test_cashier_cannot_create(client: TestClient, cashier_user, make_supplier) -> None:
    supplier = make_supplier()
    response = _create_purchase(client, cashier_user, supplier.id)
    assert response.status_code == 403
    assert response.json()["error_code"] == "PERMISSION_DENIED"


def test_cashier_cannot_update_header(
    client: TestClient, admin_user, cashier_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = client.patch(
        f"/api/purchases/{purchase['id']}",
        json={"notes": "no permitido"},
        headers=auth_headers(cashier_user),
    )
    assert response.status_code == 403


def test_cashier_cannot_add_items(
    client: TestClient, admin_user, cashier_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = client.post(
        f"/api/purchases/{purchase['id']}/items",
        json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
            "unit_cost": "1.00",
        },
        headers=auth_headers(cashier_user),
    )
    assert response.status_code == 403


def test_cashier_cannot_confirm(
    client: TestClient, admin_user, cashier_user, make_supplier, item_factory
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(
        client, admin_user, supplier.id, items=[item_factory()]
    ).json()

    response = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(cashier_user),
    )
    assert response.status_code == 403


def test_cashier_cannot_cancel(
    client: TestClient, admin_user, cashier_user, make_supplier
) -> None:
    supplier = make_supplier()
    purchase = _create_purchase(client, admin_user, supplier.id).json()

    response = client.delete(
        f"/api/purchases/{purchase['id']}", headers=auth_headers(cashier_user)
    )
    assert response.status_code == 403


def test_inventory_manager_full_lifecycle(
    client: TestClient,
    inventory_manager_user,
    make_supplier,
    make_product,
    item_factory,
) -> None:
    supplier = make_supplier(name="Proveedor inv manager")
    item = item_factory(quantity=6, unit_cost="100.00")

    created = _create_purchase(
        client, inventory_manager_user, supplier.id, items=[item]
    )
    assert created.status_code == 201
    purchase = created.json()

    patched = client.patch(
        f"/api/purchases/{purchase['id']}",
        json={"notes": "editada por inv manager"},
        headers=auth_headers(inventory_manager_user),
    )
    assert patched.status_code == 200

    confirmed = client.post(
        f"/api/purchases/{purchase['id']}/confirm",
        headers=auth_headers(inventory_manager_user),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == PurchaseStatuses.CONFIRMED

    draft_two = _create_purchase(
        client, inventory_manager_user, supplier.id
    ).json()
    cancelled = client.delete(
        f"/api/purchases/{draft_two['id']}",
        headers=auth_headers(inventory_manager_user),
    )
    assert cancelled.status_code == 204
