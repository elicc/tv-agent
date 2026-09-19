from fastapi.testclient import TestClient

from tv_agent.main import app


def test_health_reports_service_without_secrets() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tv-agent",
        "version": "0.1.0",
        "douban_configured": False,
        "llm_configured": False,
    }
