"""Pruebas del licenciamiento en la instalación local."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.licensing.constants import LocalLicenseStatus
from app.licensing.documents import (
    build_license_payload,
    encode_license_document,
    sign_license_document,
)
from app.licensing.keys import generate_keypair_pem
from app.licensing.local import service
from app.licensing.local import verifier as verifier_module
from app.licensing.local.fingerprint import fingerprint_hash, machine_fingerprint
from app.licensing.local.verifier import LicenseVerifier
from app.licensing.server.signing import LicenseSigner
from app.licensing.server.utils import utc_now
from app.models.license import LocalLicense

from tests.conftest import auth_headers


@pytest.fixture
def signer_and_verifier(monkeypatch):
    private_pem, public_pem = generate_keypair_pem()
    signer = LicenseSigner(private_pem, public_pem)
    verifier = LicenseVerifier(public_pem)
    monkeypatch.setattr(verifier_module, "get_verifier", lambda: verifier)
    return signer, verifier


def _make_document(signer, db, *, license_type="PERPETUAL", expires_at=None, grace_days=0):
    installation = service.ensure_installation(db)
    payload = build_license_payload(
        license_id=str(uuid4()),
        license_key="NEXORA-TEST-0001",
        customer_name="Supermercado Local",
        plan_code="STANDARD",
        license_type=license_type,
        expires_at=expires_at,
        grace_days=grace_days,
        features=["sales", "inventory"],
        installation_id=installation.installation_id,
        installation_fingerprint=fingerprint_hash(machine_fingerprint()),
    )
    return signer.sign(payload)


def test_installation_identity_is_stable(db_session):
    first = service.ensure_installation(db_session)
    second = service.ensure_installation(db_session)
    assert first.installation_id == second.installation_id


def test_status_is_not_activated_by_default(db_session):
    payload = service.build_status_payload(db_session)
    assert payload["status"] == LocalLicenseStatus.NOT_ACTIVATED.value
    assert payload["activated"] is False


def test_import_manual_response_activates_license(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)
    code = encode_license_document(document)

    license = service.import_manual_response(db_session, code)
    assert license.status == LocalLicenseStatus.ACTIVE.value
    assert license.license_key == "NEXORA-TEST-0001"

    payload = service.build_status_payload(db_session)
    assert payload["status"] == LocalLicenseStatus.ACTIVE.value
    assert payload["features"] == ["inventory", "sales"]


def test_document_for_other_installation_is_rejected(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    payload = build_license_payload(
        license_id=str(uuid4()),
        license_key="NEXORA-TEST-0002",
        customer_name="Otro",
        plan_code="STD",
        license_type="PERPETUAL",
        installation_id="otra-instalacion",
        installation_fingerprint=fingerprint_hash(machine_fingerprint()),
    )
    code = encode_license_document(signer.sign(payload))
    with pytest.raises(AppError) as exc:
        service.import_manual_response(db_session, code)
    assert exc.value.error_code == "LICENSE_INSTALLATION_MISMATCH"


def test_document_for_other_machine_is_rejected(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    installation = service.ensure_installation(db_session)
    payload = build_license_payload(
        license_id=str(uuid4()),
        license_key="NEXORA-TEST-0003",
        customer_name="Otro",
        plan_code="STD",
        license_type="PERPETUAL",
        installation_id=installation.installation_id,
        installation_fingerprint="huella-de-otra-maquina",
    )
    code = encode_license_document(signer.sign(payload))
    with pytest.raises(AppError) as exc:
        service.import_manual_response(db_session, code)
    assert exc.value.error_code == "LICENSE_FINGERPRINT_MISMATCH"


def test_tampered_document_is_rejected(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)
    document["payload"]["license_type"] = "HACK"
    with pytest.raises(AppError) as exc:
        service.import_manual_response(db_session, encode_license_document(document))
    assert exc.value.error_code == "LICENSE_SIGNATURE_INVALID"


def test_expired_subscription_marks_expired(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(
        signer,
        db_session,
        license_type="MONTHLY",
        expires_at=(utc_now() - timedelta(days=10)).isoformat(),
    )
    service.import_manual_response(db_session, encode_license_document(document))
    payload = service.build_status_payload(db_session)
    assert payload["status"] == LocalLicenseStatus.EXPIRED.value
    assert payload["activated"] is False


def test_subscription_in_grace_is_allowed(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(
        signer,
        db_session,
        license_type="ANNUAL",
        expires_at=(utc_now() - timedelta(days=1)).isoformat(),
        grace_days=5,
    )
    service.import_manual_response(db_session, encode_license_document(document))
    payload = service.build_status_payload(db_session)
    assert payload["status"] == LocalLicenseStatus.GRACE.value
    assert payload["activated"] is True


def test_clock_rollback_is_detected(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)
    service.import_manual_response(db_session, encode_license_document(document))

    license = service.get_active_license(db_session)
    license.last_seen_at = utc_now() + timedelta(days=3)
    db_session.commit()

    payload = service.build_status_payload(db_session)
    assert payload["status"] == LocalLicenseStatus.CLOCK_ROLLBACK.value
    assert payload["clock_rollback"] is True


def test_online_activation_uses_central(monkeypatch, db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"status": "ACTIVE", "document": document}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            assert json["installation_id"]
            assert json["fingerprint"]
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "Client", FakeClient)
    license = service.activate_online(db_session, "NEXORA-TEST-0001")
    assert license.status == LocalLicenseStatus.ACTIVE.value


# ----------------------------------------------------------------------
# Enforcement
# ----------------------------------------------------------------------
def test_business_route_allowed_when_enforcement_disabled(client, admin_user):
    resp = client.get("/api/products", headers=auth_headers(admin_user))
    assert resp.status_code == 200


def test_status_endpoint_is_always_accessible(client):
    resp = client.get("/api/license/status")
    assert resp.status_code == 200
    assert resp.json()["enforced"] is False


def test_business_route_blocked_without_license(
    client, admin_user, monkeypatch
):
    monkeypatch.setattr(service, "is_enforcement_enabled", lambda: True)
    resp = client.get("/api/products", headers=auth_headers(admin_user))
    assert resp.status_code == 402
    assert resp.json()["error_code"] == "LICENSE_NOT_ACTIVATED"


def test_business_route_allowed_with_valid_license(
    client, db_session, admin_user, signer_and_verifier, monkeypatch
):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)
    service.import_manual_response(db_session, encode_license_document(document))

    monkeypatch.setattr(service, "is_enforcement_enabled", lambda: True)
    resp = client.get("/api/products", headers=auth_headers(admin_user))
    assert resp.status_code == 200


def test_expired_license_blocks_business_route(
    client, db_session, admin_user, signer_and_verifier, monkeypatch
):
    signer, _ = signer_and_verifier
    document = _make_document(
        signer,
        db_session,
        license_type="MONTHLY",
        expires_at=(utc_now() - timedelta(days=30)).isoformat(),
    )
    service.import_manual_response(db_session, encode_license_document(document))

    monkeypatch.setattr(service, "is_enforcement_enabled", lambda: True)
    resp = client.get("/api/products", headers=auth_headers(admin_user))
    assert resp.status_code == 402
    assert resp.json()["error_code"] == "LICENSE_EXPIRED"


def test_license_status_reports_stored_license(
    client, db_session, signer_and_verifier
):
    signer, _ = signer_and_verifier
    document = _make_document(signer, db_session)
    service.import_manual_response(db_session, encode_license_document(document))
    resp = client.get("/api/license/status")
    body = resp.json()
    assert body["status"] == LocalLicenseStatus.ACTIVE.value
    assert body["license_key"] == "NEXORA-TEST-0001"


def test_only_one_local_license_is_kept(db_session, signer_and_verifier):
    signer, _ = signer_and_verifier
    service.import_manual_response(
        db_session, encode_license_document(_make_document(signer, db_session))
    )
    assert db_session.query(LocalLicense).count() == 1
