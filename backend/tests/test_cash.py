"""Tests del módulo de Caja y Control de Efectivo (Fase 8).

Cubre: apertura/cierre transaccional, movimientos OPENING/CASH_IN/CASH_OUT,
integración con ventas (CASH/CARD/TRANSFER/CREDIT), integración con pagos de
cuentas por cobrar, idempotencia por referencia, cálculo de efectivo
esperado/diferencia, RBAC y consistencia ante fallos.
"""

from decimal import Decimal

import pytest

from app.models.cash import cash_delta
from tests.conftest import auth_headers


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _open(client, headers, amount="100000.00", notes=None):
    payload: dict = {"opening_amount": amount}
    if notes is not None:
        payload["notes"] = notes
    return client.post("/api/cash/registers/open", json=payload, headers=headers)


def _current(client, headers):
    return client.get("/api/cash/registers/current", headers=headers)


def _movement(client, headers, mtype, amount, description):
    return client.post(
        "/api/cash/movements",
        json={
            "movement_type": mtype,
            "amount": amount,
            "description": description,
        },
        headers=headers,
    )


def _close(client, headers, register_id, counted="0.00"):
    return client.post(
        f"/api/cash/registers/{register_id}/close",
        json={"counted_amount": counted},
        headers=headers,
    )


def _movements_of_type(client, headers, register_id, movement_type):
    response = client.get(
        f"/api/cash/registers/{register_id}/movements",
        params={"movement_type": movement_type},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_sale(client, headers, product, quantity=2, payment_method="CASH",
                 customer_id=None, amount_paid=None):
    item = {"product_id": str(product.id), "quantity": quantity}
    payload: dict = {"payment_method": payment_method, "items": [item]}
    if customer_id is not None:
        payload["customer_id"] = str(customer_id)
    if amount_paid is not None:
        payload["amount_paid"] = amount_paid
    created = client.post("/api/sales", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    sale_id = created.json()["id"]
    confirmed = client.post(f"/api/sales/{sale_id}/confirm", headers=headers)
    return created.json(), confirmed


def _make_credit_customer(client, admin_headers):
    customer = client.post(
        "/api/customers",
        json={
            "name": "Cliente Crédito Caja",
            "credit_enabled": True,
            "credit_limit": "100000",
        },
        headers=admin_headers,
    )
    assert customer.status_code == 201, customer.text
    return customer.json()["id"]


def _credit_customer_with_sale(client, admin_headers, product):
    customer_id = _make_credit_customer(client, admin_headers)
    _, confirm = _create_sale(
        client,
        admin_headers,
        product,
        quantity=1,
        payment_method="CREDIT",
        customer_id=customer_id,
    )
    assert confirm.status_code == 200, confirm.text
    statement = client.get(
        f"/api/customers/{customer_id}/statement", headers=admin_headers
    )
    accounts = statement.json()["accounts"]["items"]
    receivable_id = accounts[0]["id"]
    return customer_id, receivable_id


@pytest.fixture(scope="function")
def cashier_headers(cashier_user):
    return auth_headers(cashier_user)


@pytest.fixture(scope="function")
def admin_headers(admin_user):
    return auth_headers(admin_user)


@pytest.fixture(scope="function")
def invmgr_headers(inventory_manager_user):
    return auth_headers(inventory_manager_user)


# ----------------------------------------------------------------------
# Apertura
# ----------------------------------------------------------------------
class TestApertura:
    def test_open_register_success_crea_movimiento_opening_misma_tx(
        self, client, cashier_headers
    ):
        response = _open(client, cashier_headers, "50000")
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "OPEN"
        assert data["opening_amount"] == "50000.00"
        opening_moves = _movements_of_type(
            client, cashier_headers, data["id"], "OPENING"
        )
        assert opening_moves["total"] == 1
        move = opening_moves["items"][0]
        assert Decimal(move["amount"]) == Decimal("50000.00")

    def test_open_register_monto_cero_permitido(self, client, cashier_headers):
        response = _open(client, cashier_headers, "0.00")
        assert response.status_code == 201, response.text

    def test_open_register_monto_negativo_rechazado(
        self, client, cashier_headers
    ):
        response = _open(client, cashier_headers, "-100")
        assert response.status_code == 422

    def test_doble_apertura_mismo_usuario_409(self, client, cashier_headers):
        first = _open(client, cashier_headers)
        assert first.status_code == 201
        second = _open(client, cashier_headers)
        assert second.status_code == 409
        assert second.json()["error_code"] == "REGISTER_ALREADY_OPEN"

    def test_reabrir_tras_cierre_permite_nueva_caja(
        self, client, cashier_headers
    ):
        first = _open(client, cashier_headers, "1000").json()
        closed = _close(client, cashier_headers, first["id"], "1000")
        assert closed.status_code == 200
        reopened = _open(client, cashier_headers, "2000")
        assert reopened.status_code == 201
        current = _current(client, cashier_headers)
        assert current.json()["opening_amount"] == "2000.00"

    def test_usuarios_distintos_tienen_cajas_independientes(
        self, client, admin_headers, cashier_headers
    ):
        assert _open(client, admin_headers).status_code == 201
        assert _open(client, cashier_headers).status_code == 201

    def test_apertura_inventario_manager_403(self, client, invmgr_headers):
        assert _open(client, invmgr_headers).status_code == 403

    def test_apertura_sin_rol_403(self, client, db_session, no_role_user):
        headers = auth_headers(no_role_user)
        assert _open(client, headers).status_code == 403

    def test_apertura_anonimo_401(self, client):
        response = _open(client, {})
        assert response.status_code == 401


# ----------------------------------------------------------------------
# Integración con ventas
# ----------------------------------------------------------------------
class TestVentasIntegracion:
    def test_venta_cash_crea_movimiento_y_aumenta_efectivo(
        self, client, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "100000")
        product = make_product(sale_price="2000.00", stock=10)
        sale, confirm = _create_sale(
            client, cashier_headers, product, quantity=2,
            payment_method="CASH",
        )
        assert confirm.status_code == 200
        register_id = _current(client, cashier_headers).json()["id"]
        sales_moves = _movements_of_type(
            client, cashier_headers, register_id, "SALE"
        )
        assert sales_moves["total"] == 1
        move = sales_moves["items"][0]
        assert Decimal(move["amount"]) == Decimal("4000.00")
        assert move["payment_method"] == "CASH"
        assert move["reference_type"] == "SALE"
        assert move["reference_id"] == sale["id"]
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["expected_cash"] == "104000.00"
        assert summary["cash_sales_total"] == "4000.00"

    def test_vuelto_no_altera_efectivo_esperado(
        self, client, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(sale_price="2000.00", stock=10)
        _, confirm = _create_sale(
            client, cashier_headers, product, quantity=1,
            payment_method="CASH", amount_paid="10000",
        )
        assert confirm.status_code == 200
        assert confirm.json()["change_due"] == "8000.00"
        summary = _current(client, cashier_headers).json()["summary"]
        # En caja entra el TOTAL (2000): el vuelto sale del cajón.
        assert summary["expected_cash"] == "2000.00"

    def test_venta_card_registra_movimiento_sin_efectivo(
        self, client, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "50000")
        product = make_product(stock=5)
        _, confirm = _create_sale(
            client, cashier_headers, product, quantity=1,
            payment_method="CARD",
        )
        assert confirm.status_code == 200
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["card_sales_total"] == "100.00"
        assert summary["cash_sales_total"] == "0.00"
        assert summary["expected_cash"] == "50000.00"

    def test_venta_transfer_registra_sin_efectivo(
        self, client, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        _, confirm = _create_sale(
            client, cashier_headers, product, quantity=3,
            payment_method="TRANSFER",
        )
        assert confirm.status_code == 200
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["transfer_sales_total"] == "300.00"
        assert summary["expected_cash"] == "0.00"

    def test_venta_credit_no_genera_movimiento_de_caja(
        self, client, admin_headers, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "10000")
        product = make_product(stock=5)
        customer_id = _make_credit_customer(client, admin_headers)
        _, confirm = _create_sale(
            client, admin_headers, product, quantity=1,
            payment_method="CREDIT",
            customer_id=customer_id,
        )
        assert confirm.status_code == 200
        register_id = _current(client, cashier_headers).json()["id"]
        assert (
            _movements_of_type(client, cashier_headers, register_id, "SALE")[
                "total"
            ]
            == 0
        )
        assert (
            _current(client, cashier_headers).json()["summary"][
                "expected_cash"
            ]
            == "10000.00"
        )

    def test_reconfirmar_venta_no_duplica_movimiento(
        self, client, cashier_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        created = client.post(
                "/api/sales",
            json={
                "payment_method": "CASH",
                "items": [{"product_id": str(product.id), "quantity": 2}],
            },
            headers=cashier_headers,
        )
        sale_id = created.json()["id"]
        first = client.post(f"/api/sales/{sale_id}/confirm", headers=cashier_headers)
        second = client.post(
            f"/api/sales/{sale_id}/confirm", headers=cashier_headers
        )
        assert first.status_code == 200
        assert second.status_code == 409
        register_id = _current(client, cashier_headers).json()["id"]
        sales_moves = _movements_of_type(
            client, cashier_headers, register_id, "SALE"
        )
        assert sales_moves["total"] == 1
        assert sales_moves["items"][0]["reference_id"] == sale_id

    def test_venta_sin_caja_abierta_no_falla_y_no_registra(
        self, client, admin_headers, make_product
    ):
        product = make_product(stock=5)
        _, confirm = _create_sale(
            client, admin_headers, product, quantity=1,
            payment_method="CASH",
        )
        assert confirm.status_code == 200
        registers = client.get("/api/cash/registers", headers=admin_headers)
        assert registers.json()["total"] == 0


# ----------------------------------------------------------------------
# Integración con cuentas por cobrar
# ----------------------------------------------------------------------
class TestCuentasPorCobrarIntegracion:
    def test_pago_cash_crea_movimiento_receivable_payment(
        self, client, cashier_headers, admin_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        _, receivable_id = _credit_customer_with_sale(
            client, admin_headers, product
        )
        payment = client.post(
            f"/api/receivables/{receivable_id}/payments",
            json={"amount": "100", "payment_method": "CASH"},
            headers=cashier_headers,
        )
        assert payment.status_code == 201, payment.text
        register_id = _current(client, cashier_headers).json()["id"]
        moves = _movements_of_type(
            client, cashier_headers, register_id, "RECEIVABLE_PAYMENT"
        )
        assert moves["total"] == 1
        move = moves["items"][0]
        assert Decimal(move["amount"]) == Decimal("100.00")
        assert move["payment_method"] == "CASH"
        assert move["reference_id"] == payment.json()["id"]
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["expected_cash"] == "100.00"

    def test_pago_card_registra_sin_efectivo(
        self, client, cashier_headers, admin_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        _, receivable_id = _credit_customer_with_sale(
            client, admin_headers, product
        )
        payment = client.post(
            f"/api/receivables/{receivable_id}/payments",
            json={"amount": "40", "payment_method": "CARD"},
            headers=cashier_headers,
        )
        assert payment.status_code == 201
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["card_receivable_payments_total"] == "40.00"
        assert summary["expected_cash"] == "0.00"

    def test_pago_transfer_registra_sin_efectivo(
        self, client, cashier_headers, admin_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        _, receivable_id = _credit_customer_with_sale(
            client, admin_headers, product
        )
        payment = client.post(
            f"/api/receivables/{receivable_id}/payments",
            json={"amount": "60", "payment_method": "TRANSFER"},
            headers=cashier_headers,
        )
        assert payment.status_code == 201
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["transfer_receivable_payments_total"] == "60.00"
        assert summary["expected_cash"] == "0.00"

    def test_pago_repetido_con_clave_no_duplica_movimiento(
        self, client, cashier_headers, admin_headers, make_product
    ):
        _open(client, cashier_headers, "0")
        product = make_product(stock=5)
        _, receivable_id = _credit_customer_with_sale(
            client, admin_headers, product
        )
        payload = {
            "amount": "50",
            "payment_method": "CASH",
            "idempotency_key": "clave-caja-001",
        }
        first = client.post(
            f"/api/receivables/{receivable_id}/payments",
            json=payload,
            headers=cashier_headers,
        )
        replay = client.post(
            f"/api/receivables/{receivable_id}/payments",
            json=payload,
            headers=cashier_headers,
        )
        assert first.status_code == 201
        assert replay.status_code in (200, 201)
        assert replay.json()["id"] == first.json()["id"]
        register_id = _current(client, cashier_headers).json()["id"]
        moves = _movements_of_type(
            client, cashier_headers, register_id, "RECEIVABLE_PAYMENT"
        )
        assert moves["total"] == 1
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["expected_cash"] == "50.00"

    def test_cierre_congela_efectivo_esperado_del_turno(
        self, client, cashier_headers, admin_headers, make_product
    ):
        _open(client, cashier_headers, "1000")
        product = make_product(stock=5)
        _, receivable_id = _credit_customer_with_sale(
            client, admin_headers, product
        )
        client.post(
            f"/api/receivables/{receivable_id}/payments",
            json={"amount": "30", "payment_method": "CASH"},
            headers=cashier_headers,
        )
        register_id = _current(client, cashier_headers).json()["id"]
        closed = _close(client, cashier_headers, register_id, "1030")
        assert closed.status_code == 200
        data = closed.json()
        assert data["expected_amount"] == "1030.00"
        assert data["difference"] == "0.00"


# ----------------------------------------------------------------------
# Movimientos manuales
# ----------------------------------------------------------------------
class TestMovimientosManuales:
    def test_cash_ingreso_exitoso(self, client, cashier_headers):
        _open(client, cashier_headers, "100")
        response = _movement(
            client, cashier_headers, "CASH_IN", "250", "Ingreso adicional"
        )
        assert response.status_code == 201, response.text
        assert response.json()["movement_type"] == "CASH_IN"
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["cash_in_total"] == "250.00"
        assert summary["expected_cash"] == "350.00"

    def test_cash_egreso_exitoso(self, client, cashier_headers):
        _open(client, cashier_headers, "300")
        response = _movement(
            client, cashier_headers, "CASH_OUT", "120", "Compra insumos"
        )
        assert response.status_code == 201
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["cash_out_total"] == "120.00"
        assert summary["expected_cash"] == "180.00"

    def test_egreso_que_deja_saldo_negativo_409(self, client, cashier_headers):
        _open(client, cashier_headers, "100")
        response = _movement(
            client, cashier_headers, "CASH_OUT", "500", "Retiro grande"
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "INSUFFICIENT_CASH"
        summary = _current(client, cashier_headers).json()["summary"]
        assert summary["expected_cash"] == "100.00"

    def test_motivo_obligatorio(self, client, cashier_headers):
        _open(client, cashier_headers)
        response = client.post(
            "/api/cash/movements",
            json={
                "movement_type": "CASH_IN",
                "amount": "10",
                "description": "",
            },
            headers=cashier_headers,
        )
        assert response.status_code == 422

    def test_monto_debe_ser_positivo(self, client, cashier_headers):
        _open(client, cashier_headers)
        response = _movement(
            client, cashier_headers, "CASH_IN", "0", "Monto inválido"
        )
        assert response.status_code == 422

    def test_tipo_manual_invalido_rechazado(self, client, cashier_headers):
        _open(client, cashier_headers)
        response = client.post(
            "/api/cash/movements",
            json={
                "movement_type": "ADJUSTMENT",
                "amount": "10",
                "description": "No permitido vía API",
            },
            headers=cashier_headers,
        )
        assert response.status_code == 422

    def test_movimiento_manual_sin_caja_abierta_409(
        self, client, cashier_headers
    ):
        response = _movement(
            client, cashier_headers, "CASH_IN", "10", "Sin caja abierta"
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "REGISTER_NOT_OPEN"

    def test_movimientos_inventario_manager_403(self, client, invmgr_headers):
        response = _movement(
            client, invmgr_headers, "CASH_IN", "10", "Denegado por rol"
        )
        assert response.status_code == 403

    def test_movimientos_sin_rol_403(self, client, no_role_user):
        headers = auth_headers(no_role_user)
        response = _movement(client, headers, "CASH_IN", "10", "Sin rol")
        assert response.status_code == 403


# ----------------------------------------------------------------------
# Cierre
# ----------------------------------------------------------------------
class TestCierre:
    def test_calculo_efectivo_esperado_completo(
        self, client, cashier_headers, make_product
    ):
        """Apertura + venta cash + card (no cuenta) + ingreso - egreso."""
        register = _open(client, cashier_headers, "100000").json()
        product = make_product(sale_price="2000.00", stock=20)

        _, confirm_cash = _create_sale(
            client, cashier_headers, product, quantity=2,
            payment_method="CASH",
        )
        assert confirm_cash.status_code == 200
        _create_sale(
            client, cashier_headers, product, quantity=3,
            payment_method="CARD",
        )
        _movement(client, cashier_headers, "CASH_IN", "50000", "Fondo extra")
        _movement(client, cashier_headers, "CASH_OUT", "20000", "Gasto menor")

        detail = client.get(
            f"/api/cash/registers/{register['id']}", headers=cashier_headers
        ).json()
        summary = detail["summary"]
        assert summary["opening_total"] == "100000.00"
        assert summary["cash_sales_total"] == "4000.00"
        assert summary["card_sales_total"] == "6000.00"
        assert summary["cash_in_total"] == "50000.00"
        assert summary["cash_out_total"] == "20000.00"
        assert summary["expected_cash"] == "134000.00"

        closed = _close(client, cashier_headers, register["id"], "134000")
        assert closed.status_code == 200
        data = closed.json()
        assert data["status"] == "CLOSED"
        assert data["expected_amount"] == "134000.00"
        assert data["counted_amount"] == "134000.00"
        assert data["difference"] == "0.00"
        assert data["closed_at"] is not None
        assert data["closed_by_username"] is not None

    def test_faltante_queda_registrado_negativo(
        self, client, cashier_headers
    ):
        register = _open(client, cashier_headers, "1000").json()
        closed = _close(client, cashier_headers, register["id"], "900")
        assert closed.status_code == 200
        assert closed.json()["difference"] == "-100.00"

    def test_sobrante_queda_registrado_positivo(self, client, cashier_headers):
        register = _open(client, cashier_headers, "1000").json()
        closed = _close(client, cashier_headers, register["id"], "1050.50")
        assert closed.status_code == 200
        assert closed.json()["difference"] == "50.50"

    def test_doble_cierre_409(self, client, cashier_headers):
        register = _open(client, cashier_headers, "100").json()
        first = _close(client, cashier_headers, register["id"], "100")
        second = _close(client, cashier_headers, register["id"], "100")
        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["error_code"] == "REGISTER_ALREADY_CLOSED"

    def test_cierre_caja_inexistente_404(self, client, cashier_headers):
        import uuid as uuid_module

        response = _close(client, cashier_headers, uuid_module.uuid4(), "0")
        assert response.status_code == 404

    def test_cierre_rbac(self, client, invmgr_headers, cashier_headers):
        register = _open(client, cashier_headers, "0").json()
        denied = _close(client, invmgr_headers, register["id"], "0")
        assert denied.status_code == 403
        allowed = _close(client, cashier_headers, register["id"], "0")
        assert allowed.status_code == 200

    def test_confirmacion_fallida_no_deja_movimientos(
        self, client, cashier_headers, make_product
    ):
        """Venta sin stock → rollback total y caja intacta."""
        register = _open(client, cashier_headers, "5000").json()
        product = make_product(stock=1)
        created = client.post(
                "/api/sales",
            json={
                "payment_method": "CASH",
                "items": [{"product_id": str(product.id), "quantity": 99}],
            },
            headers=cashier_headers,
        )
        sale_id = created.json()["id"]
        confirm = client.post(
            f"/api/sales/{sale_id}/confirm", headers=cashier_headers
        )
        assert confirm.status_code == 409
        moves = client.get(
            f"/api/cash/registers/{register['id']}/movements",
            headers=cashier_headers,
        ).json()
        assert moves["total"] == 1  # solo el OPENING
        summary = client.get(
            f"/api/cash/registers/{register['id']}", headers=cashier_headers
        ).json()["summary"]
        assert summary["expected_cash"] == "5000.00"


# ----------------------------------------------------------------------
# Consultas / reportes
# ----------------------------------------------------------------------
class TestConsultasYReportes:
    def test_current_sin_caja_devuelve_null(self, client, cashier_headers):
        response = _current(client, cashier_headers)
        assert response.status_code == 200
        assert response.json() is None

    def test_historial_de_cajas_con_filtros(self, client, cashier_headers):
        first = _open(client, cashier_headers, "100").json()
        _close(client, cashier_headers, first["id"], "100")
        _open(client, cashier_headers, "200")

        all_registers = client.get("/api/cash/registers", headers=cashier_headers)
        assert all_registers.status_code == 200
        assert all_registers.json()["total"] == 2

        only_open = client.get(
            "/api/cash/registers",
            params={"status": "OPEN"},
            headers=cashier_headers,
        )
        assert only_open.json()["total"] == 1
        assert only_open.json()["items"][0]["opening_amount"] == "200.00"

        only_closed = client.get(
            "/api/cash/registers",
            params={"status": "CLOSED"},
            headers=cashier_headers,
        )
        assert only_closed.json()["total"] == 1
        assert only_closed.json()["items"][0]["difference"] == "0.00"

    def test_detalle_de_caja_incluye_resumen(self, client, cashier_headers):
        register = _open(client, cashier_headers, "1234.50").json()
        detail = client.get(
            f"/api/cash/registers/{register['id']}", headers=cashier_headers
        ).json()
        assert detail["user_username"] is not None
        assert detail["summary"]["opening_total"] == "1234.50"
        assert detail["summary"]["expected_cash"] == "1234.50"
        assert detail["summary"]["movement_count"] == 1

    def test_listado_movimientos_paginado_y_filtro(
        self, client, cashier_headers
    ):
        register = _open(client, cashier_headers, "100").json()
        for i in range(3):
            _movement(
                client,
                cashier_headers,
                "CASH_IN",
                "10",
                f"Ingreso {i}",
            )
        page = client.get(
            f"/api/cash/registers/{register['id']}/movements",
            params={"limit": 2, "skip": 0},
            headers=cashier_headers,
        ).json()
        assert page["total"] == 4
        assert len(page["items"]) == 2

        filtered = client.get(
            f"/api/cash/registers/{register['id']}/movements",
            params={"movement_type": "CASH_OUT"},
            headers=cashier_headers,
        ).json()
        assert filtered["total"] == 0

    def test_reporte_requiere_permiso_cash_report(
        self, client, cashier_headers, admin_headers
    ):
        register = _open(client, cashier_headers, "0").json()
        denied = client.get(
            f"/api/cash/registers/{register['id']}/summary",
            headers=cashier_headers,
        )
        assert denied.status_code == 403
        allowed = client.get(
            f"/api/cash/registers/{register['id']}/summary",
            headers=admin_headers,
        )
        assert allowed.status_code == 200
        assert allowed.json()["expected_cash"] == "0.00"

    def test_consultas_anonimas_401(self, client, cashier_headers):
        register = _open(client, cashier_headers, "0").json()
        assert client.get("/api/cash/registers").status_code == 401
        path = f"/api/cash/registers/{register['id']}"
        assert client.get(path).status_code == 401
        assert (
            client.get(f"{path}/movements").status_code
            == 401
        )


# ----------------------------------------------------------------------
# cash_delta (unidad de la regla de efectivo)
# ----------------------------------------------------------------------
class TestCashDelta:
    @pytest.mark.parametrize(
        "movement_type,method,expected",
        [
            ("OPENING", None, Decimal("1")),
            ("CASH_IN", None, Decimal("1")),
            ("CASH_OUT", None, Decimal("-1")),
            ("SALE", "CASH", Decimal("1")),
            ("SALE", "CARD", Decimal("0")),
            ("SALE", "TRANSFER", Decimal("0")),
            ("RECEIVABLE_PAYMENT", "CASH", Decimal("1")),
            ("RECEIVABLE_PAYMENT", "CARD", Decimal("0")),
            ("ADJUSTMENT", None, Decimal("0")),
        ],
    )
    def test_regla_de_efectivo_por_tipo_metodo(
        self, movement_type, method, expected
    ):
        assert cash_delta(movement_type, method) == expected

