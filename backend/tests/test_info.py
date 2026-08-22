def test_app_info(client) -> None:
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sistema de Facturación e Inventario con IA"
    assert data["version"] == "1.0.0"
    assert "environment" in data


def test_app_info_does_not_expose_secrets(client) -> None:
    response = client.get("/api/info")
    data = response.json()
    sensitive_keys = {"secret_key", "database_url", "openai_api_key"}
    exposed = {key.lower() for key in data.keys()}
    assert not sensitive_keys & exposed
