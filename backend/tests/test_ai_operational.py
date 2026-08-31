"""Tests del servicio operativo de IA: chat con tools y confirm de acciones."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.ai_action import AIActionHistory, AIActionStatuses
from app.models.purchase import Purchase, PurchaseStatuses
from app.services.ai_operational_service import AIOperationalService
from tests.fakes import FakeGeminiClient, fc_call, text_response


def test_chat_executes_read_tool_and_returns_text(
    db_session: Session, admin_user, make_product
):
    make_product(name="Leche Entera", barcode="7501000000001", stock=3)
    fake = FakeGeminiClient(
        generate_script=[
            fc_call("search_products", {"q": "leche"}),
            text_response("Encontré productos con leche en su nombre."),
        ]
    )
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.chat(admin_user, "busca leche")

    assert fake.generate_calls == 2
    assert len(resp.tool_results) == 1
    assert resp.tool_results[0].name == "search_products"
    assert len(resp.tool_results[0].output) == 1
    assert resp.tool_results[0].output[0]["name"] == "Leche Entera"
    assert resp.message == "Encontré productos con leche en su nombre."
    assert resp.action_proposals == []


def test_chat_captures_action_proposal_without_executing(
    db_session: Session, admin_user, make_supplier, make_product
):
    supplier = make_supplier()
    product = make_product()
    fake = FakeGeminiClient(
        generate_script=[
            fc_call(
                "create_purchase",
                {
                    "supplier_id": str(supplier.id),
                    "items": [{"product_id": str(product.id), "quantity": 5, "unit_cost": "10.00"}],
                },
            ),
            text_response("He propuesto la compra; revísala y confírmala."),
        ]
    )
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.chat(admin_user, "reponer inventario con proveedor")

    assert len(resp.action_proposals) == 1
    prop = resp.action_proposals[0]
    assert prop.action_name == "create_purchase"
    assert prop.action_type == "purchase"
    assert prop.args["supplier_id"] == str(supplier.id)
    assert resp.message == "He propuesto la compra; revísala y confírmala."


def test_chat_does_not_create_purchase_on_proposal(
    db_session: Session, admin_user, make_supplier, make_product
):
    supplier = make_supplier()
    product = make_product(stock=0)
    fake = FakeGeminiClient(
        generate_script=[
            fc_call(
                "create_purchase",
                {"supplier_id": str(supplier.id),
                 "items": [{"product_id": str(product.id), "quantity": 2, "unit_cost": "5"}],
                 "notes": "repos"},
            ),
            text_response("propuesta lista"),
        ]
    )
    svc = AIOperationalService(db_session, client=fake)
    svc.chat(admin_user, "compra")

    purchases = db_session.query(Purchase).all()
    assert purchases == []
    assert product.stock == 0


def test_confirm_purchase_is_transactional_and_updates_stock(
    db_session: Session, admin_user, make_supplier, make_product
):
    supplier = make_supplier()
    product = make_product(stock=0)
    svc = AIOperationalService(db_session)
    args = {
        "supplier_id": str(supplier.id),
        "items": [{"product_id": str(product.id), "quantity": 10, "unit_cost": "5.00"}],
        "notes": "reposicion via IA",
    }
    out = svc.confirm_action(admin_user, "create_purchase", args, "key-purchase-1")

    assert out["status"] == "CONFIRMED"
    assert out["action_type"] == "purchase"
    assert out["reference_id"]

    purchase = db_session.get(Purchase, UUID(out["reference_id"]))
    assert purchase is not None
    assert purchase.status == PurchaseStatuses.CONFIRMED
    db_session.refresh(product)
    assert product.stock == 10

    audit = (
        db_session.query(AIActionHistory)
        .filter(AIActionHistory.idempotency_key == "key-purchase-1")
        .one()
    )
    assert audit.status == AIActionStatuses.CONFIRMED
    assert audit.action_name == "create_purchase"


def test_confirm_purchase_is_idempotent(
    db_session: Session, admin_user, make_supplier, make_product
):
    supplier = make_supplier()
    product = make_product(stock=0)
    svc = AIOperationalService(db_session)
    args = {
        "supplier_id": str(supplier.id),
        "items": [{"product_id": str(product.id), "quantity": 3, "unit_cost": "2.00"}],
    }
    first = svc.confirm_action(admin_user, "create_purchase", args, "key-dup")
    second = svc.confirm_action(admin_user, "create_purchase", args, "key-dup")

    assert first["reference_id"] == second["reference_id"]
    assert second["replayed"] is True
    db_session.refresh(product)
    # el stock SOLO se aplicó una vez
    assert product.stock == 3
    purchases = db_session.query(Purchase).count()
    assert purchases == 1


def test_confirm_inventory_adjust(
    db_session: Session, admin_user, make_product
):
    product = make_product(stock=4)
    svc = AIOperationalService(db_session)
    out = svc.confirm_action(
        admin_user,
        "adjust_inventory",
        {"product_id": str(product.id), "new_stock": 20, "reason": "conteo fisico"},
        "key-inv-1",
    )
    assert out["status"] == "CONFIRMED"
    db_session.refresh(product)
    assert product.stock == 20


def test_confirm_failed_action_is_recorded(
    db_session: Session, admin_user, make_product
):
    product = make_product()
    svc = AIOperationalService(db_session)
    # proveedor inexistente => PurchaseService lanza AppError 404
    try:
        svc.confirm_action(
            admin_user,
            "create_purchase",
            {
                "supplier_id": str(UUID("00000000-0000-0000-0000-000000000099")),
                "items": [
                    {"product_id": str(product.id), "quantity": 1, "unit_cost": "1"}
                ],
            },
            "key-fail",
        )
        assert False, "debería haber fallado"
    except AppError:
        pass
    audit = (
        db_session.query(AIActionHistory)
        .filter(AIActionHistory.idempotency_key == "key-fail")
        .one()
    )
    assert audit.status == AIActionStatuses.FAILED
