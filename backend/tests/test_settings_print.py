"""Tests de configuración de impresión y logotipo (Fase 3)."""

import io

import pytest

from app.core.config import get_settings
from app.services import logo_service as logo_module
from app.services.logo_service import MAX_LOGO_BYTES
from tests.conftest import auth_headers

# PNG 1x1 válido (firma + IHDR + IDAT + IEND mínimos).
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f"
    "15c4890000000d4944415478da63fcffff3f0300050001a5f6453f000000"
    "0049454e44ae426082"
)
JPEG_1PX = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


@pytest.fixture
def uploads_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOADS_DIR", str(tmp_path))
    yield tmp_path


def _get_print_settings(client, admin_user):
    resp = client.get("/api/settings", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    return resp.json()


def test_get_settings_includes_print_fields(client, admin_user):
    data = _get_print_settings(client, admin_user)
    assert data["paper_width"] == "80mm"
    assert data["print_copies"] == 1
    assert data["print_show_logo"] is True
    assert "print_show_company_name" in data
    assert "print_alignment" in data
    assert "print_show_city" in data
    assert "logo_filename" in data
    assert data["logo_filename"] is None


def test_update_print_settings(client, admin_user):
    payload = {
        "paper_width": "58mm",
        "print_copies": 2,
        "print_font_size": "10px",
        "print_show_logo": False,
        "print_logo_align": "center",
        "print_logo_size": "large",
        "print_show_barcode": True,
        "print_footer_text": "Fin del comprobante",
    }
    resp = client.put(
        "/api/settings", json=payload, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_width"] == "58mm"
    assert data["print_copies"] == 2
    assert data["print_show_logo"] is False
    assert data["print_logo_align"] == "center"
    assert data["print_show_barcode"] is True
    assert data["print_footer_text"] == "Fin del comprobante"


def test_update_print_settings_rejects_invalid_paper_width(client, admin_user):
    resp = client.put(
        "/api/settings",
        json={"paper_width": "A3-inexistente"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


def test_update_print_settings_requires_permission(client, cashier_user):
    resp = client.put(
        "/api/settings",
        json={"paper_width": "58mm"},
        headers=auth_headers(cashier_user),
    )
    assert resp.status_code == 403


def test_upload_logo_png(client, admin_user, uploads_tmp):
    files = {"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")}
    resp = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["logo_mime_type"] == "image/png"
    assert data["logo_size_bytes"] == len(PNG_1PX)
    assert data["logo_filename"].endswith(".png")
    # El nombre generado no debe reutilizar el nombre del cliente.
    assert data["logo_filename"] != "logo.png"

    # El archivo existe realmente en disco.
    saved = uploads_tmp / "logos" / data["logo_filename"]
    assert saved.is_file()
    assert saved.read_bytes() == PNG_1PX


def test_upload_logo_jpeg(client, admin_user, uploads_tmp):
    files = {"file": ("foto.jpg", io.BytesIO(JPEG_1PX), "image/jpeg")}
    resp = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["logo_mime_type"] == "image/jpeg"


def test_upload_logo_rejects_fake_extension(client, admin_user, uploads_tmp):
    # Extensión .png pero contenido que no es una imagen real.
    files = {"file": ("malicioso.png", io.BytesIO(b"no soy una imagen"), "image/png")}
    resp = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "LOGO_INVALID_FORMAT"


def test_upload_logo_rejects_too_large(client, admin_user, uploads_tmp):
    big = PNG_1PX + b"\x00" * (MAX_LOGO_BYTES + 10)
    files = {"file": ("grande.png", io.BytesIO(big), "image/png")}
    resp = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "LOGO_TOO_LARGE"


def test_upload_logo_requires_permission(client, cashier_user, uploads_tmp):
    files = {"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")}
    resp = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(cashier_user)
    )
    assert resp.status_code == 403


def test_get_logo_after_upload(client, admin_user, uploads_tmp):
    files = {"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")}
    client.post("/api/settings/logo", files=files, headers=auth_headers(admin_user))

    resp = client.get("/api/settings/logo", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == PNG_1PX


def test_get_logo_not_configured(client, admin_user):
    resp = client.get("/api/settings/logo", headers=auth_headers(admin_user))
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "LOGO_NOT_FOUND"


def test_delete_logo_removes_file(client, admin_user, uploads_tmp):
    files = {"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")}
    upload = client.post(
        "/api/settings/logo", files=files, headers=auth_headers(admin_user)
    ).json()
    saved = uploads_tmp / "logos" / upload["logo_filename"]
    assert saved.is_file()

    resp = client.delete("/api/settings/logo", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["logo_filename"] is None
    assert not saved.is_file()


def test_upload_logo_replaces_previous_file(client, admin_user, uploads_tmp):
    first = client.post(
        "/api/settings/logo",
        files={"file": ("a.png", io.BytesIO(PNG_1PX), "image/png")},
        headers=auth_headers(admin_user),
    ).json()
    first_path = uploads_tmp / "logos" / first["logo_filename"]
    assert first_path.is_file()

    second = client.post(
        "/api/settings/logo",
        files={"file": ("b.jpg", io.BytesIO(JPEG_1PX), "image/jpeg")},
        headers=auth_headers(admin_user),
    ).json()
    assert second["logo_filename"] != first["logo_filename"]
    assert not first_path.is_file()


def test_logo_service_never_deletes_outside_uploads(tmp_path, monkeypatch):
    """El nombre que se borra se toma de la BD, nunca del cliente."""
    monkeypatch.setattr(get_settings(), "UPLOADS_DIR", str(tmp_path))
    # Un nombre con traversal jamás debe usarse como ruta directa.
    target = tmp_path.parent / "victima.txt"
    target.write_text("importante", encoding="utf-8")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        service = logo_module.LogoService(db)
        service._delete_file_if_exists("../victima.txt")
        assert target.is_file()
    finally:
        db.close()
