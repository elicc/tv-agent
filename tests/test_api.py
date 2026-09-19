from pathlib import Path

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_health_reports_service_without_secrets(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "tv-agent.db",
        douban_api_key=None,
        llm_api_key=None,
        service_api_key=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tv-agent",
        "version": "0.2.0",
        "doubanConfigured": False,
        "llmConfigured": False,
        "authenticationEnabled": False,
    }
