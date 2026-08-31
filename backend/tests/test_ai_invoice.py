"""Tests del escaneo de facturas (Gemini Vision) y detección de duplicados."""

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.ai_action import AIInvoiceScan
from app.services.ai_operational_service import AIOperationalService
from tests.fakes import FakeGeminiClient

VISION_JSON = (
    '{"supplier_name": "Distribuidora ABC", "invoice_number": "F-00123", '
    '"total": 120.50, "items": [{"product_name": "Pan Blanco", "quantity": 10, '
    '"unit_price": 3.00, "total": 30.00}, {"product_name": "Arroz", '
    '"quantity": 5, "unit_price": 18.10, "total": 90.50}]}'
)


def test_scan_parses_and_persists_invoice(db_session: Session, admin_user):
    fake = FakeGeminiClient(vision_text=VISION_JSON)
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.scan_invoice(
        admin_user, "factura.png", "image/png", b"imagen"
    )

    assert fake.vision_calls == 1
    assert resp.supplier_name == "Distribuidora ABC"
    assert resp.invoice_number == "F-00123"
    assert str(resp.total) == "120.50"
    assert len(resp.items) == 2
    assert resp.duplicate is False
    assert resp.duplicate_of is None

    scan = db_session.get(AIInvoiceScan, resp.scan_id)
    assert scan is not None
    assert scan.supplier_name == "Distribuidora ABC"
    assert scan.invoice_number == "F-00123"


def test_scan_matches_catalog_products(
    db_session: Session, admin_user, make_product
):
    make_product(name="Pan Blanco", barcode="75011")
    fake = FakeGeminiClient(vision_text=VISION_JSON)
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.scan_invoice(admin_user, "f.png", "image/png", b"x")

    names = [pm.name for pm in resp.product_matches]
    assert "Pan Blanco" in names


def test_scan_detects_duplicate_invoice(db_session: Session, admin_user):
    fake = FakeGeminiClient(vision_text=VISION_JSON)
    svc = AIOperationalService(db_session, client=fake)
    first = svc.scan_invoice(admin_user, "f1.png", "image/png", b"x")
    second = svc.scan_invoice(admin_user, "f2.png", "image/png", b"y")

    assert second.duplicate is True
    assert str(second.duplicate_of) == str(first.scan_id)


def test_scan_rejects_unsupported_file_type(db_session: Session, admin_user):
    fake = FakeGeminiClient(vision_text=VISION_JSON)
    svc = AIOperationalService(db_session, client=fake)
    try:
        svc.scan_invoice(admin_user, "doc.txt", "text/plain", b"data")
        assert False, "debería haber rechazado el tipo de archivo"
    except AppError as e:
        assert e.status_code == 422
        assert e.error_code == "UNSUPPORTED_FILE_TYPE"


def test_scan_tolerates_non_json_response(db_session: Session, admin_user):
    fake = FakeGeminiClient(vision_text="no es json")
    svc = AIOperationalService(db_session, client=fake)
    resp = svc.scan_invoice(admin_user, "f.png", "image/png", b"x")
    assert resp.scan_id is not None
    # sin datos => no duplicado, items vacíos
    assert resp.items == []
