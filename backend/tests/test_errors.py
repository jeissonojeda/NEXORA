def test_not_found_endpoint(client):
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "NOT_FOUND"


def test_health_response_structure(client):
    response = client.get("/api/health")
    data = response.json()
    required_fields = ["status", "database", "environment"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
