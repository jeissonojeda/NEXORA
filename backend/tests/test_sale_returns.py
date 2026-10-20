"""Tests de Devoluciones y Cambios de Ventas (Módulo 1).

Cubre: devolución total/parcial transaccional (reingreso de stock + reembolso
en un único COMMIT), reembolsos CASH/CARD/CREDIT, cambio (EXCHANGE) con nueva
venta de reemplazo atómica, idempotencia, condiciones de reingreso (RESALE/
DAMAGED), validaciones, RBAC e historial.
"""

import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models.cash import CashMovement
from app.models.customer import ReceivableAccount
from app.models.inventory import InventoryMovement
from app.models.product import Product
from tests.conftest import auth_headers

DEV_PATTERN = re.compile(r"^DEV-\d{4}-\d{6}$")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _item(product_id, qty=1, unit_price=None):
    payload = {"product_id": str(product_id), "quantity": qty}
    if unit_price is not None:
        payload["unit_price"] = unit_price
    return payload


def _create_confirmed_sale(client, headers, items, **kwargs):
    payload = {"payment_method": "CASH", "items": items, **kwargs}
    r = client.post("/api/sales", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    sale_id = r.json()["id"]
    rc = client.post(f"/api/sales/{sale_id}/confirm", headers=headers)
    assert rc.status_code == 200, rc.text
    return rc.json()


def _open_register(client, headers, opening="0.00"):
    r = client.post(
        "/api/cash/registers/open",
        json={"opening_amount": opening},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _return(client, headers, sale_id, payload):
    return client.post(f"/api/sales/{sale_id}/returns", json=payload, headers=headers)


# ----------------------------------------------------------------------
# Devolución con reembolso en efectivo
# ----------------------------------------------------------------------
class TestCashReturn:
    def test_full_return_cash_ok(self, client, admin_user, make_product, db_session):
        headers = auth_headers(admin_user)
        _open_register(client, headers, "1000.00")
        p = make_product(sale_price="100.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=3)])
        db_session.refresh(p)
        assert p.stock == 7  # 3 descontados al confirmar

        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "reason": "Producto defectuoso",
                "items": [{"sale_item_id": sale_item_id, "quantity": 3}],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert DEV_PATTERN.match(data["return_number"])
        assert data["status"] == "COMPLETED"
        assert data["return_type"] == "RETURN"
        assert data["refund_method"] == "CASH"
        assert Decimal(data["total"]) == Decimal("300.00")
        assert Decimal(data["refunded_amount"]) == Decimal("300.00")
        assert Decimal(data["credit_applied"]) == Decimal("0.00")
        assert len(data["items"]) == 1
        assert data["items"][0]["restock"] is True

        # Stock reingresado (movimiento RETURN con reference SALE_RETURN).
        db_session.refresh(p)
        assert p.stock == 10
        movements = list(
            db_session.scalars(
                select(InventoryMovement).where(
                    InventoryMovement.reference_type == "SALE_RETURN",
                    InventoryMovement.reference_id == str(data["id"]),
                )
            )
        )
        assert len(movements) == 1
        assert movements[0].movement_type == "RETURN"
        assert movements[0].quantity == 3

        # Movimiento CASH_OUT de caja por el reembolso.
        cash_moves = list(
            db_session.scalars(
                select(CashMovement).where(
                    CashMovement.reference_type == "SALE_RETURN",
                    CashMovement.reference_id == str(data["id"]),
                )
            )
        )
        assert len(cash_moves) == 1
        assert cash_moves[0].movement_type == "CASH_OUT"
        assert Decimal(cash_moves[0].amount) == Decimal("300.00")

    def test_partial_return_keeps_rest_of_sale(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="50.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=5)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
            },
        )
        assert r.status_code == 201, r.text
        assert Decimal(r.json()["total"]) == Decimal("100.00")
        db_session.refresh(p)
        assert p.stock == 7  # 5 descontados + 2 devueltos

    def test_return_exceeds_sold_quantity_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="100.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=2)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 3}],
            },
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "RETURN_EXCEEDS_SOLD"

    def test_cascading_partial_returns_respect_available(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="10.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=3)])
        sale_item_id = sale["items"][0]["id"]

        r1 = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
            },
        )
        assert r1.status_code == 201
        r2 = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r2.status_code == 201
        # Ya no queda nada por devolver.
        r3 = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r3.status_code == 409
        assert r3.json()["error_code"] == "RETURN_EXCEEDS_SOLD"

    def test_return_cash_without_open_register_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="100.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "REGISTER_NOT_OPEN"

    def test_return_proportional_discount_and_tax(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        from app.models.tax import Tax

        tax = Tax(name="IVA 19%", rate=Decimal("19"))
        db_session.add(tax)
        db_session.commit()
        p = make_product(sale_price="200.00", stock=10, tax_id=tax.id)
        r_sale = client.post(
            "/api/sales",
            json={
                "payment_method": "CASH",
                "discount": "10.00",
                "items": [
                    {
                        "product_id": str(p.id),
                        "quantity": 4,
                        "tax_rate": "19",
                    }
                ],
            },
            headers=headers,
        )
        assert r_sale.status_code == 201, r_sale.text
        sale = r_sale.json()
        rc = client.post(f"/api/sales/{sale['id']}/confirm", headers=headers)
        assert rc.status_code == 200
        sale = rc.json()

        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        # Proporción 2/4 del ítem: subtotal 800→400, impuesto 152→76.
        # El descuento 10 es de cabecera y NO se reparte en las líneas.
        assert Decimal(data["subtotal"]) == Decimal("400.00")
        assert Decimal(data["tax"]) == Decimal("76.00")
        assert Decimal(data["total"]) == Decimal("476.00")
        assert Decimal(data["items"][0]["discount"]) == Decimal("0.00")


# ----------------------------------------------------------------------
# Reembolso externo (CARD/TRANSFER) y condiciones de reingreso
# ----------------------------------------------------------------------
class TestExternalRefundAndConditions:
    def test_return_card_external_no_cash_movement(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="80.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CARD",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert Decimal(data["refunded_amount"]) == Decimal("80.00")
        # Sin movimiento de caja: el reverso de tarjeta es externo.
        cash_moves = list(
            db_session.scalars(
                select(CashMovement).where(
                    CashMovement.reference_type == "SALE_RETURN",
                    CashMovement.reference_id == str(data["id"]),
                )
            )
        )
        assert cash_moves == []
        # Stock sí reingresa (RESALE por defecto).
        db_session.refresh(p)
        assert p.stock == 5

    def test_damaged_condition_does_not_restock(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="30.00", stock=4)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=2)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                        "condition": "DAMAGED",
                    }
                ],
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["items"][0]["restock"] is False
        db_session.refresh(p)
        assert p.stock == 2  # 2 descontados, 0 reingresados

    def test_review_condition_does_not_restock(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="30.00", stock=4)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=2)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 2,
                        "condition": "REVIEW",
                    }
                ],
            },
        )
        assert r.status_code == 201
        db_session.refresh(p)
        assert p.stock == 2


# ----------------------------------------------------------------------
# Reembolso a crédito (cuenta por cobrar de la venta)
# ----------------------------------------------------------------------
class TestCreditRefund:
    def _confirmed_credit_sale(self, client, headers, product, customer):
        r = client.post(
            "/api/sales",
            json={
                "payment_method": "CREDIT",
                "customer_id": str(customer["id"]),
                "items": [_item(product.id, qty=2)],
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        rc = client.post(f"/api/sales/{r.json()['id']}/confirm", headers=headers)
        assert rc.status_code == 200, rc.text
        return rc.json()

    def test_credit_return_reduces_receivable_and_balance(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="100.00", stock=10)
        customer = make_customer(credit_enabled=True, credit_limit="1000.00")
        sale = self._confirmed_credit_sale(
            client, headers, p, {"id": customer.id}
        )
        assert Decimal(customer.current_balance) == Decimal("200.00")

        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CREDIT",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r.status_code == 201, r.text
        assert Decimal(r.json()["refunded_amount"]) == Decimal("100.00")

        db_session.refresh(customer)
        assert Decimal(customer.current_balance) == Decimal("100.00")
        account = db_session.scalars(
            select(ReceivableAccount).where(
                ReceivableAccount.reference_type == "SALE",
                ReceivableAccount.reference_id == str(sale["id"]),
            )
        ).first()
        assert account is not None
        assert Decimal(account.balance) == Decimal("100.00")
        assert Decimal(account.original_amount) == Decimal("100.00")

    def test_credit_return_exceeding_balance_rejected(
        self, client, admin_user, make_product, make_customer, db_session
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="100.00", stock=10)
        customer = make_customer(credit_enabled=True, credit_limit="1000.00")
        sale = self._confirmed_credit_sale(
            client, headers, p, {"id": customer.id}
        )
        # Abona 150 de los 200: saldo 50.
        account = db_session.scalars(
            select(ReceivableAccount).where(
                ReceivableAccount.reference_type == "SALE",
                ReceivableAccount.reference_id == str(sale["id"]),
            )
        ).first()
        rp = client.post(
            f"/api/receivables/{account.id}/payments",
            json={
                "amount": "150.00",
                "payment_method": "CASH",
            },
            headers=headers,
        )
        assert rp.status_code in (200, 201), rp.text

        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CREDIT",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
            },
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "REFUND_EXCEEDS_BALANCE"

    def test_credit_return_on_cash_sale_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="50.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CREDIT",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "SALE_HAS_NO_RECEIVABLE"


# ----------------------------------------------------------------------
# Cambio (EXCHANGE)
# ----------------------------------------------------------------------
class TestExchange:
    def test_exchange_creates_replacement_sale_atomically(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers, "500.00")
        p_old = make_product(name="Viejo", sale_price="100.00", stock=10)
        p_new = make_product(name="Nuevo", sale_price="120.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p_old.id, qty=2)])
        db_session.refresh(p_old)
        assert p_old.stock == 8

        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
                "exchange_items": [_item(p_new.id, qty=2)],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["return_type"] == "EXCHANGE"
        assert data["exchange_sale_id"] is not None
        # Crédito 200 cubre el total de la nueva venta (240): aplicado 200,
        # excedente 0; el cliente paga la diferencia vía la nueva venta.
        assert Decimal(data["credit_applied"]) == Decimal("200.00")
        assert Decimal(data["refunded_amount"]) == Decimal("0.00")

        # Nueva venta CONFIRMED con descuento 200.
        new_sale = client.get(
            f"/api/sales/{data['exchange_sale_id']}", headers=headers
        ).json()
        assert new_sale["status"] == "CONFIRMED"
        assert Decimal(new_sale["discount"]) == Decimal("200.00")
        assert Decimal(new_sale["total"]) == Decimal("40.00")
        assert "Cambio por devolución" in (new_sale["notes"] or "")

        # Stock: viejo 8+2=10, nuevo 10-2=8.
        db_session.refresh(p_old)
        db_session.refresh(p_new)
        assert p_old.stock == 10
        assert p_new.stock == 8

    def test_exchange_with_excess_refunds_cash(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers, "500.00")
        p_old = make_product(name="Caro", sale_price="100.00", stock=10)
        p_new = make_product(name="Barato", sale_price="30.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p_old.id, qty=2)])
        sale_item_id = sale["items"][0]["id"]

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 2}],
                "exchange_items": [_item(p_new.id)],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        # Crédito 200; nueva venta 30 → aplicado 30, excedente 170 en efectivo.
        assert Decimal(data["credit_applied"]) == Decimal("30.00")
        assert Decimal(data["refunded_amount"]) == Decimal("170.00")
        cash_moves = list(
            db_session.scalars(
                select(CashMovement).where(
                    CashMovement.reference_type == "SALE_RETURN",
                    CashMovement.reference_id == str(data["id"]),
                )
            )
        )
        assert len(cash_moves) == 1
        assert Decimal(cash_moves[0].amount) == Decimal("170.00")

    def test_exchange_invalid_product_rolls_back_everything(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p_old = make_product(sale_price="100.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p_old.id)])
        sale_item_id = sale["items"][0]["id"]
        db_session.refresh(p_old)
        stock_before = p_old.stock

        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
                # Producto inexistente: la transacción entera debe revertirse.
                "exchange_items": [_item(uuid.uuid4())],
            },
        )
        assert r.status_code == 404
        db_session.refresh(p_old)
        assert p_old.stock == stock_before  # rollback completo
        returns = client.get(
            f"/api/sales/{sale['id']}/returns", headers=headers
        ).json()
        assert returns["total"] == 0


# ----------------------------------------------------------------------
# Idempotencia, validaciones y estado
# ----------------------------------------------------------------------
class TestValidationsAndIdempotency:
    def test_idempotency_key_returns_same_document(
        self, client, admin_user, make_product, db_session
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="25.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=2)])
        sale_item_id = sale["items"][0]["id"]

        payload = {
            "refund_method": "CASH",
            "idempotency_key": "dev-key-001",
            "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
        }
        r1 = _return(client, headers, sale["id"], payload)
        assert r1.status_code == 201
        r2 = _return(client, headers, sale["id"], payload)
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]
        # El stock no se reingresó dos veces.
        db_session.refresh(p)
        assert p.stock == 9  # 10 - 2 + 1 (una sola devolución)

    def test_return_draft_sale_rejected(self, client, admin_user, make_product):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="10.00", stock=5)
        r = client.post(
            "/api/sales",
            json={"payment_method": "CASH", "items": [_item(p.id)]},
            headers=headers,
        )
        sale = r.json()
        sale_item_id = sale["items"][0]["id"]
        rr = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert rr.status_code == 409
        assert rr.json()["error_code"] == "SALE_NOT_CONFIRMED"

    def test_return_empty_items_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        r = _return(
            client, headers, sale["id"], {"refund_method": "CASH", "items": []}
        )
        assert r.status_code == 422

    def test_return_item_not_from_sale_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p1 = make_product(sale_price="10.00", stock=5)
        p2 = make_product(sale_price="20.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p1.id)])
        other = _create_confirmed_sale(client, headers, [_item(p2.id)])
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [
                    {"sale_item_id": other["items"][0]["id"], "quantity": 1}
                ],
            },
        )
        assert r.status_code == 404
        assert r.json()["error_code"] == "SALE_ITEM_NOT_FOUND"

    def test_invalid_refund_method_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "BITCOIN",
                "items": [
                    {"sale_item_id": sale["items"][0]["id"], "quantity": 1}
                ],
            },
        )
        assert r.status_code == 422

    def test_invalid_condition_rejected(self, client, admin_user, make_product):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CARD",
                "items": [
                    {
                        "sale_item_id": sale["items"][0]["id"],
                        "quantity": 1,
                        "condition": "TOY",
                    }
                ],
            },
        )
        assert r.status_code == 422

    def test_duplicate_item_in_payload_rejected(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=3)])
        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CARD",
                "items": [
                    {"sale_item_id": sale_item_id, "quantity": 1},
                    {"sale_item_id": sale_item_id, "quantity": 1},
                ],
            },
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "RETURN_ITEM_DUPLICATE"


# ----------------------------------------------------------------------
# Historial, consulta y anulación
# ----------------------------------------------------------------------
class TestHistoryAndCancel:
    def test_list_returns_for_sale(
        self, client, admin_user, make_product
    ):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="10.00", stock=10)
        sale = _create_confirmed_sale(client, headers, [_item(p.id, qty=3)])
        sale_item_id = sale["items"][0]["id"]
        r = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert r.status_code == 201

        listing = client.get(
            f"/api/sales/{sale['id']}/returns", headers=headers
        )
        assert listing.status_code == 200
        data = listing.json()
        assert data["total"] == 1
        assert DEV_PATTERN.match(data["items"][0]["return_number"])

    def test_get_return_detail(self, client, admin_user, make_product):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="15.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        sale_item_id = sale["items"][0]["id"]
        created = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        ).json()

        detail = client.get(
            f"/api/sales/returns/{created['id']}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["id"] == created["id"]
        assert detail.json()["created_by_username"] == admin_user.username

    def test_get_return_not_found(self, client, admin_user):
        r = client.get(
            f"/api/sales/returns/{uuid.uuid4()}", headers=auth_headers(admin_user)
        )
        assert r.status_code == 404

    def test_cancel_return(self, client, admin_user, make_product, db_session):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="40.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        sale_item_id = sale["items"][0]["id"]
        created = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        ).json()

        r = client.delete(
            f"/api/sales/returns/{created['id']}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"
        # Anular no revierte stock automáticamente (corrección administrativa).
        db_session.refresh(p)
        assert p.stock == 5

    def test_cancel_twice_rejected(self, client, admin_user, make_product):
        headers = auth_headers(admin_user)
        _open_register(client, headers)
        p = make_product(sale_price="40.00", stock=5)
        sale = _create_confirmed_sale(client, headers, [_item(p.id)])
        created = _return(
            client,
            headers,
            sale["id"],
            {
                "refund_method": "CASH",
                "items": [
                    {"sale_item_id": sale["items"][0]["id"], "quantity": 1}
                ],
            },
        ).json()
        r1 = client.delete(
            f"/api/sales/returns/{created['id']}", headers=headers
        )
        assert r1.status_code == 200
        r2 = client.delete(
            f"/api/sales/returns/{created['id']}", headers=headers
        )
        assert r2.status_code == 409
        assert r2.json()["error_code"] == "RETURN_ALREADY_CANCELLED"


# ----------------------------------------------------------------------
# RBAC
# ----------------------------------------------------------------------
class TestRBAC:
    def test_cashier_can_return(self, client, cashier_user, make_product):
        headers = auth_headers(cashier_user)
        _open_register(client, headers)
        p = make_product(sale_price="10.00", stock=5)
        r = client.post(
            "/api/sales",
            json={"payment_method": "CASH", "items": [_item(p.id)]},
            headers=headers,
        )
        sale_id = r.json()["id"]
        client.post(f"/api/sales/{sale_id}/confirm", headers=headers)
        sale_item_id = r.json()["items"][0]["id"]
        # Recarga detalle (los ítems tienen id tras crear).
        detail = client.get(f"/api/sales/{sale_id}", headers=headers).json()
        sale_item_id = detail["items"][0]["id"]
        rr = _return(
            client,
            headers,
            sale_id,
            {
                "refund_method": "CASH",
                "items": [{"sale_item_id": sale_item_id, "quantity": 1}],
            },
        )
        assert rr.status_code == 201

    def test_inventory_manager_cannot_return(
        self, client, admin_user, inventory_manager_user, make_product
    ):
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        )
        r = _return(
            client,
            auth_headers(inventory_manager_user),
            sale["id"],
            {
                "refund_method": "CARD",
                "items": [
                    {"sale_item_id": sale["items"][0]["id"], "quantity": 1}
                ],
            },
        )
        assert r.status_code == 403

    def test_no_role_user_cannot_return(
        self, client, admin_user, no_role_user, make_product
    ):
        p = make_product(sale_price="10.00", stock=5)
        sale = _create_confirmed_sale(
            client, auth_headers(admin_user), [_item(p.id)]
        )
        r = _return(
            client,
            auth_headers(no_role_user),
            sale["id"],
            {
                "refund_method": "CARD",
                "items": [
                    {"sale_item_id": sale["items"][0]["id"], "quantity": 1}
                ],
            },
        )
        assert r.status_code == 403
