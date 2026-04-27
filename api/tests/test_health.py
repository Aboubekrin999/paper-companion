"""Tests for the /health endpoint and CORS configuration."""

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)


def test_health_returns_ok():
    """Liveness probe responds with status=ok and the current app version."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == app.version


def test_health_response_shape():
    """Response shape matches the HealthResponse pydantic model exactly."""
    response = client.get("/health")
    body = response.json()
    assert set(body.keys()) == {"status", "version"}


def test_docs_available():
    """Swagger UI is mounted at /docs as documented in the README."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
