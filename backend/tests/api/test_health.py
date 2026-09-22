"""Foundation-milestone smoke test: the app boots and the DB is reachable."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db() -> None:
    response = client.get("/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}
