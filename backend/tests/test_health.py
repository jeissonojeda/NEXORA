def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert "environment" in data


def test_health_check_database_status(client):
    response = client.get("/api/health")
    data = response.json()
    assert data["database"] == "ok"
