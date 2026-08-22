from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD, auth_headers

USER_PAYLOAD = {
    "username": "newuser1",
    "email": "newuser1@demomail.com",
    "password": "NewUser123",
    "first_name": "New",
    "last_name": "User",
    "role_name": "CASHIER",
}


def test_admin_can_create_user(client: TestClient, admin_user) -> None:
    response = client.post(
        "/api/users", json=USER_PAYLOAD, headers=auth_headers(admin_user)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser1"
    assert data["roles"][0]["name"] == "CASHIER"
    assert "password_hash" not in data


def test_create_user_with_duplicate_username_returns_409(
    client: TestClient, admin_user
) -> None:
    payload = USER_PAYLOAD | {"username": admin_user.username}
    response = client.post(
        "/api/users", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "USERNAME_ALREADY_EXISTS"


def test_create_user_with_duplicate_email_returns_409(
    client: TestClient, admin_user
) -> None:
    payload = USER_PAYLOAD | {"email": admin_user.email}
    response = client.post(
        "/api/users", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def test_create_user_with_weak_password_rejected_422(
    client: TestClient, admin_user
) -> None:
    for weak in ("short", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere"):
        payload = USER_PAYLOAD | {"password": weak}
        response = client.post(
            "/api/users", json=payload, headers=auth_headers(admin_user)
        )
        assert response.status_code == 422, f"password '{weak}' no rechazada"


def test_create_user_with_invalid_role_rejected(
    client: TestClient, admin_user
) -> None:
    payload = USER_PAYLOAD | {"role_name": "SUPERGOD"}
    response = client.post(
        "/api/users", json=payload, headers=auth_headers(admin_user)
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_ROLE"


def test_admin_can_list_users(client: TestClient, admin_user, cashier_user) -> None:
    response = client.get("/api/users", headers=auth_headers(admin_user))
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()]
    assert "admin1" in usernames
    assert "cashier1" in usernames


def test_admin_can_get_user_by_id(client: TestClient, admin_user, cashier_user) -> None:
    response = client.get(f"/api/users/{cashier_user.id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    assert response.json()["id"] == str(cashier_user.id)


def test_admin_get_nonexistent_user_returns_404(
    client: TestClient, admin_user
) -> None:
    from uuid import uuid4

    response = client.get(f"/api/users/{uuid4()}", headers=auth_headers(admin_user))
    assert response.status_code == 404


def test_admin_can_change_role_via_patch(
    client: TestClient, admin_user, cashier_user
) -> None:
    response = client.patch(
        f"/api/users/{cashier_user.id}",
        json={"role_name": "INVENTORY_MANAGER"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    roles = [r["name"] for r in response.json()["roles"]]
    assert roles == ["INVENTORY_MANAGER"]


def test_admin_can_deactivate_and_reactivate_via_patch(
    client: TestClient, admin_user, cashier_user
) -> None:
    response = client.patch(
        f"/api/users/{cashier_user.id}",
        json={"is_active": False},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    login_response = client.post(
        "/api/auth/login",
        data={"username": "cashier1", "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 403


def test_delete_performs_logical_deactivation(
    client: TestClient, admin_user, cashier_user
) -> None:
    response = client.delete(
        f"/api/users/{cashier_user.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 204
    get_response = client.get(
        f"/api/users/{cashier_user.id}", headers=auth_headers(admin_user)
    )
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


def test_admin_cannot_deactivate_self(
    client: TestClient, admin_user
) -> None:
    response = client.delete(
        f"/api/users/{admin_user.id}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CANNOT_DEACTIVATE_SELF"


def test_cashier_cannot_manage_users(client: TestClient, cashier_user) -> None:
    headers = auth_headers(cashier_user)
    assert client.get("/api/users", headers=headers).status_code == 403
    assert (
        client.post("/api/users", json=USER_PAYLOAD, headers=headers).status_code
        == 403
    )
    assert client.get("/api/users/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 403
    assert (
        client.patch(
            "/api/users/00000000-0000-0000-0000-000000000000",
            json={"is_active": False},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            "/api/users/00000000-0000-0000-0000-000000000000", headers=headers
        ).status_code
        == 403
    )


def test_inventory_manager_cannot_manage_users(
    client: TestClient, inventory_manager_user
) -> None:
    headers = auth_headers(inventory_manager_user)
    assert client.get("/api/users", headers=headers).status_code == 403
    assert (
        client.post("/api/users", json=USER_PAYLOAD, headers=headers).status_code
        == 403
    )


def test_user_without_role_cannot_manage_users(
    client: TestClient, no_role_user
) -> None:
    headers = auth_headers(no_role_user)
    assert client.get("/api/users", headers=headers).status_code == 403


def test_users_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/users").status_code == 401
    assert client.post("/api/users", json=USER_PAYLOAD).status_code == 401


def test_permission_denied_error_format(client: TestClient, cashier_user) -> None:
    response = client.get("/api/users", headers=auth_headers(cashier_user))
    body = response.json()
    assert body["error_code"] == "PERMISSION_DENIED"
    assert body["status_code"] == 403
