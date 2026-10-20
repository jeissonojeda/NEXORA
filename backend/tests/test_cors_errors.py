"""Regresión: las respuestas de error deben incluir cabeceras CORS.

Sin ellas, el navegador bloquea la respuesta y el frontend solo muestra un
"Network Error" sin el detalle real del backend.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.product_service import ProductService
from tests.conftest import auth_headers

ALLOWED_ORIGIN = "http://localhost:5173"
ORIGIN_HEADER = {"Origin": ALLOWED_ORIGIN}


def _headers(user) -> dict[str, str]:
    return {**auth_headers(user), **ORIGIN_HEADER}


def test_not_found_includes_cors_headers(client, admin_user):
    resp = client.get("/api/ruta-inexistente", headers=_headers(admin_user))
    assert resp.status_code == 404
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_app_error_includes_cors_headers(client, admin_user):
    resp = client.get(
        f"/api/products/{uuid.uuid4()}", headers=_headers(admin_user)
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "PRODUCT_NOT_FOUND"
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_internal_error_includes_cors_headers(
    client, admin_user, monkeypatch
):
    def boom(self, _product_id):  # noqa: ANN001
        raise RuntimeError("fallo de prueba CORS")

    monkeypatch.setattr(ProductService, "get_product", boom)

    # El handler de 500 es el que se ejecuta fuera del middleware CORS.
    faulty = TestClient(app, raise_server_exceptions=False)
    resp = faulty.get(
        f"/api/products/{uuid.uuid4()}", headers=_headers(admin_user)
    )

    assert resp.status_code == 500
    assert resp.json()["error_code"] == "INTERNAL_ERROR"
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert "fallo de prueba CORS" not in resp.text


def test_error_without_origin_has_no_cors_headers(client, admin_user):
    resp = client.get(
        f"/api/products/{uuid.uuid4()}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404
    assert "access-control-allow-origin" not in resp.headers
