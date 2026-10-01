from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_database_up(tmp_path):
    app = create_app(database_url=f"sqlite+pysqlite:///{tmp_path / 't.db'}")
    with TestClient(app) as client:
        body = client.get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] == "up"
