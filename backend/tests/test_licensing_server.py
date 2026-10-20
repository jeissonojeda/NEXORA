"""Pruebas del servicio central de licencias (API + servicios)."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.licensing.documents import verify_license_document
from app.licensing.keys import generate_keypair_pem, load_public_key
from app.licensing.server.db import LicenseBase, get_license_db
from app.licensing.server.deps import get_signer_dep
from app.licensing.server.main import app
from app.licensing.server.models import License, LicenseAdmin
from app.licensing.server.rate_limit import rate_limiter
from app.licensing.server.security import hash_password
from app.licensing.server.signing import LicenseSigner
from app.licensing.server.utils import utc_now

ADMIN_PASSWORD = "SuperSecret123"


@dataclass
class Central:
    client: TestClient
    signer: LicenseSigner
    session: sessionmaker


@pytest.fixture(scope="function")
def central() -> Generator[Central, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    LicenseBase.metadata.create_all(bind=engine)

    private_pem, public_pem = generate_keypair_pem()
    signer = LicenseSigner(private_pem, public_pem)

    def override_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_license_db] = override_db
    app.dependency_overrides[get_signer_dep] = lambda: signer
    rate_limiter.reset()

    with TestingSession() as db:
        db.add(
            LicenseAdmin(
                username="owner",
                email="owner@nexora.test",
                password_hash=hash_password(ADMIN_PASSWORD),
            )
        )
        db.commit()

    with TestClient(app) as client:
        yield Central(client=client, signer=signer, session=TestingSession)

    app.dependency_overrides.clear()


def _login(client: TestClient) -> str:
    resp = client.post(
        "/api/admin/auth/login",
        data={"username": "owner", "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_license(client, token, *, max_installations=1, license_type="PERPETUAL"):
    customer = client.post(
        "/api/admin/customers",
        json={"name": "Supermercado Demo"},
        headers=_auth(token),
    )
    assert customer.status_code == 201, customer.text
    license_resp = client.post(
        "/api/admin/licenses",
        json={
            "customer_id": customer.json()["id"],
            "license_type": license_type,
            "max_installations": max_installations,
            "features": ["sales", "inventory"],
        },
        headers=_auth(token),
    )
    assert license_resp.status_code == 201, license_resp.text
    return license_resp.json()


def _activate(client, license, installation_id, fingerprint):
    return client.post(
        "/api/public/activate",
        json={
            "license_key": license["license_key"],
            "installation_id": installation_id,
            "fingerprint": fingerprint,
        },
    )


def test_login_rejects_bad_credentials(central: Central):
    resp = central.client.post(
        "/api/admin/auth/login",
        data={"username": "owner", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


def test_admin_endpoints_require_token(central: Central):
    assert central.client.get("/api/admin/licenses").status_code == 401


def test_create_license_generates_unique_key(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)
    assert license["license_key"].startswith("NEXORA-")
    assert license["active_installations"] == 0
    assert license["status"] == "ACTIVE"


def test_online_activation_issues_verifiable_document(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)

    resp = central.client.post(
        "/api/public/activate",
        json={
            "license_key": license["license_key"],
            "installation_id": "install-aaa",
            "fingerprint": "fingerprint-aaa",
            "app_version": "1.0.0",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ACTIVE"

    public_key = load_public_key(central.signer.public_key_pem)
    payload = verify_license_document(
        resp.json()["document"], public_key, expected_key_id=central.signer.key_id
    )
    assert payload["installation_id"] == "install-aaa"
    assert payload["license_key"] == license["license_key"]


def test_activation_is_idempotent_for_same_installation(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)
    assert _activate(central.client, license, "install-aaa", "fp-aaa").status_code == 200
    assert _activate(central.client, license, "install-aaa", "fp-aaa").status_code == 200

    listed = central.client.get(
        f"/api/admin/licenses/{license['id']}/installations", headers=_auth(token)
    )
    assert len(listed.json()) == 1


def test_activation_enforces_installation_limit(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token, max_installations=1)
    assert _activate(central.client, license, "install-1", "fp-1").status_code == 200

    blocked = _activate(central.client, license, "install-2", "fp-2")
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "INSTALLATION_LIMIT_REACHED"


def test_releasing_installation_frees_capacity(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token, max_installations=1)
    _activate(central.client, license, "install-1", "fp-1")

    release = central.client.post(
        f"/api/admin/licenses/{license['id']}/installations/install-1/release",
        json={"reason": "Equipo reemplazado"},
        headers=_auth(token),
    )
    assert release.status_code == 200
    assert _activate(central.client, license, "install-2", "fp-2").status_code == 200


def test_revoked_license_cannot_activate(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)
    central.client.patch(
        f"/api/admin/licenses/{license['id']}/status",
        json={"status": "REVOKED", "reason": "Fraude"},
        headers=_auth(token),
    )
    resp = _activate(central.client, license, "install-x", "fp-x")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "LICENSE_REVOKED"


def test_expired_subscription_cannot_activate(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token, license_type="MONTHLY")
    with central.session() as db:
        row = db.scalar(select(License).where(License.license_key == license["license_key"]))
        row.expires_at = utc_now() - timedelta(days=1)
        db.commit()
    resp = _activate(central.client, license, "install-exp", "fp-exp")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "LICENSE_EXPIRED"


def test_subscription_within_grace_still_activates(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token, license_type="ANNUAL")
    with central.session() as db:
        row = db.scalar(select(License).where(License.license_key == license["license_key"]))
        row.grace_days = 5
        row.expires_at = utc_now() - timedelta(days=1)
        db.commit()
    assert _activate(central.client, license, "install-g", "fp-g").status_code == 200


def test_manual_activation_flow(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)

    from app.licensing.documents import (
        build_activation_request,
        encode_activation_request,
    )

    code = encode_activation_request(
        build_activation_request(
            license_key=license["license_key"],
            installation_id="install-manual",
            fingerprint="fp-manual",
            nonce="nonce-1",
            app_version="1.0.0",
        )
    )
    created = central.client.post("/api/public/manual-request", json={"request_code": code})
    assert created.status_code == 200, created.text

    pending = central.client.get(
        "/api/admin/manual-requests", params={"status": "PENDING"}, headers=_auth(token)
    )
    assert len(pending.json()) == 1

    authorized = central.client.post(
        f"/api/admin/manual-requests/{created.json()['id']}/authorize",
        headers=_auth(token),
    )
    assert authorized.status_code == 200, authorized.text
    public_key = load_public_key(central.signer.public_key_pem)
    payload = verify_license_document(
        authorized.json()["response_document"],
        public_key,
        expected_key_id=central.signer.key_id,
    )
    assert payload["installation_id"] == "install-manual"
    assert payload["nonce"] == "nonce-1"


def test_manual_request_is_idempotent(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)

    from app.licensing.documents import (
        build_activation_request,
        encode_activation_request,
    )

    code = encode_activation_request(
        build_activation_request(
            license_key=license["license_key"],
            installation_id="install-manual-2",
            fingerprint="fp-manual-2",
            nonce="n",
            app_version="1.0.0",
        )
    )
    first = central.client.post("/api/public/manual-request", json={"request_code": code})
    second = central.client.post("/api/public/manual-request", json={"request_code": code})
    assert first.json()["id"] == second.json()["id"]


def test_transfer_releases_origin_installation(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token, max_installations=1)
    _activate(central.client, license, "install-old", "fp-old")

    transfer = central.client.post(
        "/api/admin/transfers",
        json={
            "license_id": license["id"],
            "from_installation_id": "install-old",
            "reason": "Migración de servidor",
        },
        headers=_auth(token),
    )
    assert transfer.status_code == 201, transfer.text
    assert _activate(central.client, license, "install-new", "fp-new").status_code == 200


def test_public_status_requires_exact_key(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)
    ok = central.client.get(f"/api/public/status/{license['license_key']}")
    assert ok.status_code == 200
    assert ok.json()["active_installations"] == 0
    missing = central.client.get("/api/public/status/NEXORA-0000-0000-0000")
    assert missing.status_code == 404


def test_audit_events_are_recorded(central: Central):
    token = _login(central.client)
    license = _setup_license(central.client, token)
    _activate(central.client, license, "install-audit", "fp-audit")
    events = central.client.get("/api/admin/audit", headers=_auth(token))
    assert events.status_code == 200
    actions = {e["action"] for e in events.json()}
    assert "ACTIVATION_SUCCESS" in actions
    assert "LICENSE_CREATED" in actions
