"""Tests del registro de tools y del preview de acciones de IA."""

from sqlalchemy.orm import Session

from app.ai.tools import ACTION_TOOL_MAP, READ_EXECUTORS, get_action_tool_or_404
from app.core.exceptions import AppError
from app.core.rbac import Roles
from app.services.ai_operational_service import AIOperationalService


def test_read_tools_have_executors():
    from app.ai.tools import READ_TOOLS

    for tool in READ_TOOLS:
        assert tool["name"] in READ_EXECUTORS
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"


def test_action_tools_define_permission_and_type():
    from app.ai.tools import ACTION_TOOLS

    action_names = {"create_purchase", "adjust_inventory", "create_product",
                    "create_supplier", "register_payment"}
    assert set(ACTION_TOOL_MAP) == action_names
    for tool in ACTION_TOOLS:
        assert tool.get("permission")
        assert tool.get("action_type")
        assert "parameters" in tool


def test_get_action_tool_unknown_raises_404(db_session: Session):
    try:
        get_action_tool_or_404("not_a_tool")
        assert False, "debería haber lanzado AppError"
    except AppError as e:
        assert e.status_code == 404
        assert e.error_code == "AI_ACTION_TOOL_NOT_FOUND"


def test_preview_purchase_returns_display(
    db_session: Session, admin_user, make_supplier, make_product
):
    supplier = make_supplier()
    product = make_product()
    svc = AIOperationalService(db_session)
    resp = svc.preview_action(
        admin_user,
        "create_purchase",
        {
            "supplier_id": str(supplier.id),
            "items": [{"product_id": str(product.id), "quantity": 5, "unit_cost": "10.00"}],
            "notes": "reposicion",
        },
        idempotency_key=None,
    )
    assert resp.action_type == "purchase"
    assert resp.action_name == "create_purchase"
    assert resp.requires_confirmation is True
    assert resp.args["supplier_id"] == str(supplier.id)
    assert resp.display["supplier"] == supplier.name


def test_preview_requires_native_permission(
    db_session: Session, inventory_manager_user
):
    # INVENTORY_MANAGER no tiene receivables.payment => no puede previsualizar
    # un pago vía IA (defensa en profundidad).
    svc = AIOperationalService(db_session)
    try:
        svc.preview_action(
            inventory_manager_user,
            "register_payment",
            {"account_id": "a", "amount": "10.00", "payment_method": "CASH"},
            idempotency_key=None,
        )
        assert False, "debería haber denegado el pago"
    except AppError as e:
        assert e.status_code == 403
        assert e.error_code == "PERMISSION_DENIED"


def test_preview_inventory_ok_for_inventory_manager(
    db_session: Session, inventory_manager_user, make_product
):
    product = make_product(stock=5)
    svc = AIOperationalService(db_session)
    resp = svc.preview_action(
        inventory_manager_user,
        "adjust_inventory",
        {"product_id": str(product.id), "new_stock": 15, "reason": "conteo"},
        idempotency_key=None,
    )
    assert resp.action_type == "inventory"
    assert resp.display["current_stock"] == 5
    assert resp.display["new_stock"] == 15


def test_role_hierarchy_directory():
    assert Roles.ADMIN
