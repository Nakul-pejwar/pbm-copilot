from fastapi.testclient import TestClient

from app import config as config_module
from app.main import app

client = TestClient(app)


def test_api_config_defaults():
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "pbm-copilot-api"
    assert body["auth_required"] is False


def test_api_upload_rejected_without_token_when_configured(monkeypatch):
    monkeypatch.setattr(config_module.settings, "api_token", "sekret")
    r = client.post(
        "/api/upload",
        files={"file": ("x.csv", b"", "text/csv")},
        data={"company_name": "Token Test Co"},
    )
    assert r.status_code == 401


def test_api_upload_accepted_with_token_when_configured(monkeypatch):
    monkeypatch.setattr(config_module.settings, "api_token", "sekret")
    r = client.post(
        "/api/upload",
        headers={"X-API-Token": "sekret"},
        files={"file": ("x.csv", b"", "text/csv")},
        data={"company_name": "Token Test Co"},
    )
    assert r.status_code == 400
    assert "file" in r.json()["detail"].lower()