"""Tests de Ventas y FacturaciÃ³n (Fase 7).

Cubre: creaciÃ³n DRAFT con snapshot de precios, ediciÃ³n de carrito,
confirmaciÃ³n transaccional (descuento de stock + movimientos EXIT con
reference SALE), idempotencia, cancelaciÃ³n, mÃ©todos de pago (CASH/CARD/
TRANSFER/CREDIT), integraciÃ³n con crÃ©dito del cliente (cuentas por cobrar),
rollbacks completos y RBAC.
"""

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.models.customer import ReceivableAccount
from app.models.inventory import InventoryMovement
from app.models.product import Product
from tests.conftest import auth_headers

VTA_PATTERN = re.compile(r"^VTA-\d{4}-\d{6}$")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _item(product_id, qty=1, unit_price=None, discount="0", tax="0"):
    payload = {
        "product_id": str(product_id),
        "quantity": qty,
        "discount": discount,
        "tax": tax,
    }
    if unit_price is not None:
        payload["unit_price"] = unit_price
    return payload


def _create_sale(client, headers, items, **kwargs):
    payload = {"payment_method": "CASH", "items": items, **kwargs}
    return client.post("/api/sales", json=payload, headers=headers)


def _confirm(client, headers, sale_id):
    return client.post(f"/api/sales/{sale_id}/confirm", headers=headers)


def _movements_for(db_session, sale_id):
    return list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "SALE",
                InventoryMovement.reference_id == str(sale_id),
            )
        )
    )


# ----------------------------------------------------------------------
# CreaciÃ³n (DRAFT)
# ----------------------------------------------------------------------
class TestCreateSale:
    def test_create_sale_draft_ok(self, client, admin_user, make_product):
        p1 = make_product(sale_price="100.00")
        p2 = make_product(sale_price="50.00")
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p1.id, qty=2), _item(p2.id)],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "DRAFT"
        assert VTA_PATTERN.match(data["sale_number"])
        assert data["customer_id"] is None
        assert Decimal(data["subtotal"]) == Decimal("250.00")
        assert Decimal(data["total"]) == Decimal("250.00")
        assert len(data["items"]) == 2
        assert data["confirmed_at"] is None

    def test_create_sale_number_format_is_sequential(
        self, client, admin_user, make_product
    ):
        p = make_product()
        r1 = _create_sale(client, auth_headers(admin_user), [_item(p.id)])
        r2 = _create_sale(client, auth_headers(admin_user), [_item(p.id)])
        assert r1.status_code == 201 and r2.status_code == 201
        n1, n2 = r1.json()["sale_number"], r2.json()["sale_number"]
        year = datetime.now(timezone.utc).year
        assert n1.startswith(f"VTA-{year}-") and n2.startswith(f"VTA-{year}-")
        assert int(n2.rsplit("-", 1)[1]) == int(n1.rsplit("-", 1)[1]) + 1

    def test_create_sale_snapshot_default_unit_price(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(sale_price="100.00")
        response = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, qty=3)]
        )
        assert response.status_code == 201
        assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("100.00")

    def test_create_sale_snapshot_survives_price_changes(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(sale_price="100.00")
        response = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        )
        sale_id = response.json()["id"]
        # Cambia el precio actual: la venta creada conserva el snapshot.
        p.sale_price = Decimal("999.99")
        db_session.commit()
        detail = client.get(f"/api/sales/{sale_id}", headers=auth_headers(admin_user)).json()
        assert Decimal(detail["items"][0]["unit_price"]) == Decimal("100.00")

    def test_create_sale_explicit_unit_price_overrides(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        response = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, unit_price="90.50")]
        )
        assert response.status_code == 201
        item = response.json()["items"][0]
        assert Decimal(item["unit_price"]) == Decimal("90.50")
        assert Decimal(item["subtotal"]) == Decimal("90.50")

    def test_create_sale_with_customer_ok(
        self, client, admin_user, make_product, make_customer
    ):
        p = make_product()
        c = make_customer()
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id)],
            customer_id=str(c.id),
        )
        assert response.status_code == 201
        assert response.json()["customer_id"] == str(c.id)

    def test_create_sale_duplicate_product_409(
        self, client, admin_user, make_product
    ):
        p = make_product()
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id), _item(p.id)],
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "SALE_ITEM_DUPLICATE_PRODUCT"

    def test_create_sale_inactive_product_409(
        self, client, admin_user, make_product
    ):
        p = make_product(is_active=False)
        response = _create_sale(client, auth_headers(admin_user), [_item(p.id)])
        assert response.status_code == 409
        assert response.json()["error_code"] == "PRODUCT_INACTIVE"

    def test_create_sale_missing_product_404(self, client, admin_user):
        response = _create_sale(client, auth_headers(admin_user), [_item(uuid4())])
        assert response.status_code == 404
        assert response.json()["error_code"] == "PRODUCT_NOT_FOUND"

    def test_create_sale_zero_quantity_422(
        self, client, admin_user, make_product
    ):
        p = make_product()
        response = _create_sale(client, auth_headers(admin_user), [_item(p.id, qty=0)])
        assert response.status_code == 422

    def test_create_sale_item_discount_exceeds_subtotal_422(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=1, discount="150.00")],
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "ITEM_DISCOUNT_EXCEEDS_SUBTOTAL"

    def test_create_sale_header_discount_exceeds_subtotal_422(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id)],
            discount="500.00",
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "DISCOUNT_EXCEEDS_SUBTOTAL"

    def test_create_sale_invalid_payment_method_422(
        self, client, admin_user, make_product
    ):
        p = make_product()
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id)],
            payment_method="BITCOIN",
        )
        assert response.status_code == 422


# ----------------------------------------------------------------------
# Consulta y listado
# ----------------------------------------------------------------------
class TestReadSales:
    def _seed(self, client, admin_user, make_product, status="DRAFT"):
        p = make_product(sale_price="120.00")
        response = _create_sale(client, auth_headers(admin_user), [_item(p.id, qty=2)])
        sale_id = response.json()["id"]
        if status == "CONFIRMED":
            assert _confirm(client, auth_headers(admin_user), sale_id).status_code == 200
        return p, sale_id

    def test_get_sale_detail_ok(self, client, admin_user, make_product):
        p, sale_id = self._seed(client, admin_user, make_product)
        response = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sale_id
        assert data["items"][0]["product_name"] == p.name
        assert data["created_by_username"] == admin_user.username

    def test_get_sale_not_found_404(self, client, admin_user):
        response = client.get(f"/api/sales/{uuid4()}", headers=auth_headers(admin_user))
        assert response.status_code == 404
        assert response.json()["error_code"] == "SALE_NOT_FOUND"

    def test_list_sales_filter_status(
        self, client, admin_user, make_product
    ):
        _, draft_id = self._seed(client, admin_user, make_product)
        _, confirmed_id = self._seed(
            client, admin_user, make_product, status="CONFIRMED"
        )
        response = client.get(
            "/api/sales?status=CONFIRMED", headers=auth_headers(admin_user)
        )
        assert response.status_code == 200
        data = response.json()
        ids = [s["id"] for s in data["items"]]
        assert confirmed_id in ids and draft_id not in ids
        assert all(s["status"] == "CONFIRMED" for s in data["items"])

    def test_list_sales_search_by_number(
        self, client, admin_user, make_product
    ):
        _, sale_id = self._seed(client, admin_user, make_product)
        number = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()["sale_number"]
        response = client.get(
            f"/api/sales?q={number[-6:]}", headers=auth_headers(admin_user)
        )
        assert response.status_code == 200
        assert any(s["id"] == sale_id for s in response.json()["items"])

    def test_list_sales_pagination(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="10.00")
        for _ in range(3):
            _create_sale(client, auth_headers(admin_user), [_item(p.id)])
        response = client.get(
            "/api/sales?skip=0&limit=2", headers=auth_headers(admin_user)
        )
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_list_sales_invalid_status_422(self, client, admin_user):
        response = client.get(
            "/api/sales?status=NOPE", headers=auth_headers(admin_user)
        )
        assert response.status_code == 422


# ----------------------------------------------------------------------
# EdiciÃ³n en DRAFT
# ----------------------------------------------------------------------
class TestEditDraftSale:
    def test_update_sale_discount_tax_notes_recalculates(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, qty=2)]
        ).json()["id"]
        response = client.patch(
            f"/api/sales/{sale_id}",
            json={"discount": "30.00", "tax": "10.00", "notes": "delivery"},
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["subtotal"]) == Decimal("200.00")
        assert Decimal(data["total"]) == Decimal("180.00")
        assert data["notes"] == "delivery"

    def test_add_item_updates_totals(
        self, client, admin_user, make_product
    ):
        p1 = make_product(sale_price="100.00")
        p2 = make_product(sale_price="40.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p1.id)]
        ).json()["id"]
        response = client.post(
            f"/api/sales/{sale_id}/items",
            json=_item(p2.id, qty=2),
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 201
        detail = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert len(detail["items"]) == 2
        assert Decimal(detail["subtotal"]) == Decimal("180.00")

    def test_add_existing_product_409(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        response = client.post(
            f"/api/sales/{sale_id}/items",
            json=_item(p.id),
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 409

    def test_update_item_quantity_recalculates(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, qty=1)]
        ).json()["id"]
        item_id = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()["items"][0]["id"]
        response = client.patch(
            f"/api/sales/{sale_id}/items/{item_id}",
            json={"quantity": 5},
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 200
        assert Decimal(response.json()["subtotal"]) == Decimal("500.00")
        detail = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert Decimal(detail["total"]) == Decimal("500.00")

    def test_remove_item_updates_totals(
        self, client, admin_user, make_product
    ):
        p1 = make_product(sale_price="100.00")
        p2 = make_product(sale_price="50.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p1.id), _item(p2.id)]
        ).json()["id"]
        items = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()["items"]
        target = next(i for i in items if i["product_name"] == p1.name)
        response = client.delete(
            f"/api/sales/{sale_id}/items/{target['id']}",
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 204
        detail = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert len(detail["items"]) == 1
        assert Decimal(detail["subtotal"]) == Decimal("50.00")


# ----------------------------------------------------------------------
# ConfirmaciÃ³n: stock, movimientos e idempotencia
# ----------------------------------------------------------------------
class TestConfirmSale:
    def test_confirm_sale_deducts_stock_exact(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(stock=10, sale_price="100.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, qty=4)]
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200
        db_session.expire_all()
        assert db_session.get(Product, p.id).stock == 6

    def test_confirm_sale_creates_one_exit_movement_per_item(
        self, client, admin_user, make_product, db_session
    ):
        p1 = make_product(stock=10, sale_price="100.00")
        p2 = make_product(stock=5, sale_price="60.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p1.id, qty=3), _item(p2.id, qty=2)],
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200
        db_session.expire_all()

        movements = _movements_for(db_session, sale_id)
        assert len(movements) == 2
        by_product = {m.product_id: m for m in movements}
        m1, m2 = by_product[p1.id], by_product[p2.id]
        assert m1.movement_type == "EXIT" and m2.movement_type == "EXIT"
        assert m1.quantity == 3 and m2.quantity == 2
        assert m1.previous_stock == 10 and m1.new_stock == 7
        assert m2.previous_stock == 5 and m2.new_stock == 3
        assert m1.reference_id == sale_id and m2.reference_id == sale_id
        assert m1.created_by == admin_user.id
        assert f"Venta" in (m1.reason or "")

    def test_confirm_sale_sets_status_and_timestamp(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        data = response.json()
        assert data["status"] == "CONFIRMED"
        assert data["confirmed_at"] is not None

    def test_confirm_empty_sale_422(
        self, client, admin_user, make_product
    ):
        sale_id = _create_sale(client, auth_headers(admin_user), []).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 422
        assert response.json()["error_code"] == "SALE_EMPTY"

    def test_confirm_sale_with_product_becoming_inactive_409(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(stock=10)
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        p.is_active = False
        db_session.commit()
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 409
        assert response.json()["error_code"] == "PRODUCT_INACTIVE"

    def test_confirm_insufficient_stock_rolls_back_everything(
        self, client, admin_user, make_product, db_session
    ):
        ok_product = make_product(stock=10, sale_price="100.00")
        short_product = make_product(stock=1, sale_price="200.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(ok_product.id, qty=2), _item(short_product.id, qty=5)],
        ).json()["id"]

        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 409
        assert response.json()["error_code"] == "INSUFFICIENT_STOCK"

        db_session.expire_all()
        # Rollback completo: ni el primer producto pierde stock.
        assert db_session.get(Product, ok_product.id).stock == 10
        assert db_session.get(Product, short_product.id).stock == 1
        assert _movements_for(db_session, sale_id) == []
        sale = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert sale["status"] == "DRAFT"

    def test_reconfirm_sale_is_rejected_and_harmless(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(stock=10, sale_price="100.00")
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id, qty=2)]
        ).json()["id"]
        assert _confirm(client, auth_headers(admin_user), sale_id).status_code == 200
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 409
        assert response.json()["error_code"] == "SALE_ALREADY_CONFIRMED"
        db_session.expire_all()
        assert db_session.get(Product, p.id).stock == 8
        assert len(_movements_for(db_session, sale_id)) == 1


# ----------------------------------------------------------------------
# CancelaciÃ³n
# ----------------------------------------------------------------------
class TestCancelSale:
    def test_cancel_draft_sale_ok(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        response = client.delete(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        )
        assert response.status_code == 204
        detail = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert detail["status"] == "CANCELLED"

    def test_cancel_confirmed_sale_409(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        _confirm(client, auth_headers(admin_user), sale_id)
        response = client.delete(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "SALE_ALREADY_CONFIRMED"

    def test_cancel_twice_409(self, client, admin_user, make_product):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        assert (
            client.delete(f"/api/sales/{sale_id}", headers=auth_headers(admin_user)).status_code
            == 204
        )
        response = client.delete(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "SALE_ALREADY_CANCELLED"

    def test_confirm_cancelled_sale_409(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        client.delete(f"/api/sales/{sale_id}", headers=auth_headers(admin_user))
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 409
        assert response.json()["error_code"] == "SALE_CANCELLED"

    def test_edit_cancelled_sale_409(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        client.delete(f"/api/sales/{sale_id}", headers=auth_headers(admin_user))
        response = client.patch(
            f"/api/sales/{sale_id}",
            json={"notes": "x"},
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 409


# ----------------------------------------------------------------------
# MÃ©todos de pago
# ----------------------------------------------------------------------
class TestSalePayments:
    def test_cash_insufficient_payment_422_on_confirm(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="100.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=3)],  # total 300
            amount_paid="100.00",
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 422
        assert response.json()["error_code"] == "PAYMENT_INSUFFICIENT"

    def test_cash_payment_computes_change_due(
        self, client, admin_user, make_product, db_session
    ):
        p = make_product(sale_price="100.00", stock=10)
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=3)],  # total 300
            amount_paid="350.00",
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount_paid"]) == Decimal("350.00")
        assert Decimal(data["change_due"]) == Decimal("50.00")
        db_session.expire_all()
        assert db_session.get(Product, p.id).stock == 7

    def test_card_payment_records_total_as_paid(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="80.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=2)],
            payment_method="CARD",
            amount_paid="999.99",
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount_paid"]) == Decimal("160.00")
        assert Decimal(data["change_due"]) == Decimal("0.00")

    def test_transfer_payment_records_total_as_paid(
        self, client, admin_user, make_product
    ):
        p = make_product(sale_price="45.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=1)],
            payment_method="TRANSFER",
        ).json()["id"]
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200
        assert Decimal(response.json()["amount_paid"]) == Decimal("45.00")

    def test_credit_without_customer_422_at_creation(
        self, client, admin_user, make_product
    ):
        p = make_product()
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id)],
            payment_method="CREDIT",
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "CUSTOMER_REQUIRED_FOR_CREDIT"

    def test_credit_with_disabled_customer_409(
        self, client, admin_user, make_product, make_customer
    ):
        p = make_product()
        c = make_customer(credit_enabled=False, credit_limit="100000.00")
        response = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id)],
            payment_method="CREDIT",
            customer_id=str(c.id),
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "CREDIT_NOT_ENABLED"

    def test_update_sale_to_credit_requires_customer(
        self, client, admin_user, make_product
    ):
        p = make_product()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        response = client.patch(
            f"/api/sales/{sale_id}",
            json={"payment_method": "CREDIT"},
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 422

    def test_update_sale_assign_customer_ok(
        self, client, admin_user, make_product, make_customer
    ):
        p = make_product()
        c = make_customer()
        sale_id = _create_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        ).json()["id"]
        response = client.patch(
            f"/api/sales/{sale_id}",
            json={"customer_id": str(c.id)},
            headers=auth_headers(admin_user),
        )
        assert response.status_code == 200
        assert response.json()["customer"]["name"] == c.name


# ----------------------------------------------------------------------
# IntegraciÃ³n con crÃ©dito y cuentas por cobrar (Fase 6)
# ----------------------------------------------------------------------
class TestCreditIntegration:
    def _credit_sale(
        self, client, admin_user, make_product, make_customer,
        total_items_qty=3,
    ):
        p = make_product(sale_price="100.00", stock=50)
        c = make_customer(credit_enabled=True, credit_limit="100000.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=total_items_qty)],
            payment_method="CREDIT",
            customer_id=str(c.id),
        ).json()["id"]
        return p, c, sale_id

    def test_credit_sale_creates_receivable_account(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        p, c, sale_id = self._credit_sale(
            client, admin_user, make_product, make_customer
        )
        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 200

        account = db_session.scalars(
            select(ReceivableAccount).where(ReceivableAccount.customer_id == c.id)
        ).first()
        assert account is not None
        assert account.reference_type == "SALE"
        assert account.reference_id == sale_id
        assert Decimal(str(account.original_amount)) == Decimal("300.00")
        assert Decimal(str(account.balance)) == Decimal("300.00")
        assert account.status == "OPEN"

    def test_credit_sale_increases_customer_balance(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        _, c, sale_id = self._credit_sale(
            client, admin_user, make_product, make_customer
        )
        assert _confirm(client, auth_headers(admin_user), sale_id).status_code == 200
        db_session.expire_all()
        customer = db_session.get(type(c), c.id)
        assert Decimal(str(customer.current_balance)) == Decimal("300.00")

    def test_cash_sale_never_touches_credit_balance(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        p = make_product(sale_price="100.00")
        c = make_customer(credit_enabled=True, credit_limit="100000.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=2)],
            customer_id=str(c.id),  # contado CON cliente: no toca saldo
        ).json()["id"]
        assert _confirm(client, auth_headers(admin_user), sale_id).status_code == 200
        db_session.expire_all()
        customer = db_session.get(type(c), c.id)
        assert Decimal(str(customer.current_balance)) == Decimal("0.00")
        accounts = db_session.scalar(
            select(func.count()).select_from(ReceivableAccount)
        )
        assert accounts == 0

    def test_credit_sale_exceeding_limit_rolls_back_stock_and_credit(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        p = make_product(sale_price="100.00", stock=20)
        c = make_customer(credit_enabled=True, credit_limit="100.00")
        sale_id = _create_sale(
            client,
            auth_headers(admin_user),
            [_item(p.id, qty=3)],  # total 300 > cupo 100
            payment_method="CREDIT",
            customer_id=str(c.id),
        ).json()["id"]

        response = _confirm(client, auth_headers(admin_user), sale_id)
        assert response.status_code == 409
        assert response.json()["error_code"] == "CREDIT_LIMIT_EXCEEDED"

        db_session.expire_all()
        # Rollback completo: stock, saldo y cuentas intactos.
        assert db_session.get(Product, p.id).stock == 20
        customer = db_session.get(type(c), c.id)
        assert Decimal(str(customer.current_balance)) == Decimal("0.00")
        assert _movements_for(db_session, sale_id) == []
        assert (
            db_session.scalar(select(func.count()).select_from(ReceivableAccount))
            == 0
        )
        sale = client.get(
            f"/api/sales/{sale_id}", headers=auth_headers(admin_user)
        ).json()
        assert sale["status"] == "DRAFT"

    def test_credit_sale_then_full_payment_closes_account(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        _, c, sale_id = self._credit_sale(
            client, admin_user, make_product, make_customer
        )
        assert _confirm(client, auth_headers(admin_user), sale_id).status_code == 200
        statement = client.get(
            f"/api/customers/{c.id}/statement", headers=auth_headers(admin_user)
        ).json()
        account_id = statement["accounts"]["items"][0]["id"]

        payment = client.post(
            f"/api/receivables/{account_id}/payments",
            json={
                "amount": "300.00",
                "payment_method": "CASH",
                "idempotency_key": f"pay-{sale_id}",
            },
            headers=auth_headers(admin_user),
        )
        assert payment.status_code == 201

        db_session.expire_all()
        account = db_session.get(ReceivableAccount, uuid.UUID(account_id))
        assert account.status == "PAID"
        customer = db_session.get(type(c), c.id)
        assert Decimal(str(customer.current_balance)) == Decimal("0.00")


# ----------------------------------------------------------------------
# RBAC
# ----------------------------------------------------------------------
class TestSalesRbac:
    def test_cashier_can_run_complete_pos_flow(
        self, client, cashier_user, make_product
    ):
        p = make_product(sale_price="100.00", stock=10)
        headers = auth_headers(cashier_user)
        created = _create_sale(client, headers, [_item(p.id, qty=2)])
        assert created.status_code == 201
        sale_id = created.json()["id"]
        confirmed = _confirm(client, headers, sale_id)
        assert confirmed.status_code == 200
        listed = client.get("/api/sales", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

    def test_inventory_manager_reads_but_cannot_sell(
        self, client, inventory_manager_user, cashier_user, make_product
    ):
        p = make_product(sale_price="100.00", stock=10)
        manager_headers = auth_headers(inventory_manager_user)
        assert client.get("/api/sales", headers=manager_headers).status_code == 200

        created = _create_sale(
            client, manager_headers, [_item(p.id)]
        )
        assert created.status_code == 403

        # Una venta del cajero existe; el encargado no puede confirmarla/cancelarla.
        cashier_headers = auth_headers(cashier_user)
        sale_id = _create_sale(
            client, cashier_headers, [_item(p.id)]
        ).json()["id"]
        assert _confirm(client, manager_headers, sale_id).status_code == 403
        assert (
            client.delete(f"/api/sales/{sale_id}", headers=manager_headers).status_code
            == 403
        )

    def test_unauthenticated_401(self, client, make_product):
        p = make_product()
        assert client.post("/api/sales", json={"payment_method": "CASH"}).status_code == 401
        assert client.get("/api/sales").status_code == 401

    def test_no_role_user_403(self, client, no_role_user):
        response = client.get("/api/sales", headers=auth_headers(no_role_user))
        assert response.status_code == 403
