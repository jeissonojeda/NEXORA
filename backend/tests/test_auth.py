from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD, auth_headers


def test_login_with_valid_credentials_returns_token(
    client: TestClient, admin_user
) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_accepts_email_as_identifier(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_returns_generic_401(
    client: TestClient, admin_user
) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "WrongPass999"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "INVALID_CREDENTIALS"
    assert body["detail"] == "Usuario o contraseña incorrectos"


def test_login_with_nonexistent_user_returns_same_error_as_wrong_password(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": "ghost_user", "password": "Whatever123"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "INVALID_CREDENTIALS"
    assert body["detail"] == "Usuario o contraseña incorrectos"


def test_login_with_inactive_user_returns_403(
    client: TestClient, inactive_user
) -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": inactive_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "USER_INACTIVE"


def test_me_returns_authenticated_user_data(client: TestClient, cashier_user) -> None:
    response = client.get("/api/auth/me", headers=auth_headers(cashier_user))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == cashier_user.username
    assert data["email"] == cashier_user.email
    assert data["roles"][0]["name"] == "CASHIER"


def test_me_never_exposes_password_hash(client: TestClient, admin_user) -> None:
    response = client.get("/api/auth/me", headers=auth_headers(admin_user))
    data = response.json()
    serialized = str(data)
    assert "password_hash" not in data.keys()
    assert admin_user.password_hash not in serialized


def test_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.real.jwt"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error_code"] == "NOT_AUTHENTICATED"


def test_me_with_expired_token_returns_401(client: TestClient, admin_user) -> None:
    from datetime import timedelta

    from app.core.security import create_access_token

    expired_token = create_access_token(
        data={"sub": str(admin_user.id)},
        expires_delta=timedelta(seconds=-30),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


def test_me_with_malformed_subject_returns_401(client: TestClient) -> None:
    from app.core.security import create_access_token

    bad_token = create_access_token(data={"sub": "not-a-uuid"})
    headers = {"Authorization": f"Bearer {bad_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


def test_inactive_user_with_valid_token_gets_403_on_protected_endpoints(
    client: TestClient, inactive_user
) -> None:
    response = client.get("/api/auth/me", headers=auth_headers(inactive_user))
    assert response.status_code == 403
    assert response.json()["error_code"] == "USER_INACTIVE"
