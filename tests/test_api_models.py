import os

os.environ.setdefault("APP_CONFIG", "config.yaml.example")
os.environ.setdefault("MISTRAL_API_KEY", "dummy")

from fastapi.testclient import TestClient

from sgr_deep_research.api.endpoints import app, config
from sgr_deep_research.settings import LLMProvider


def test_models_filtered_for_mistral(monkeypatch):
    monkeypatch.setattr(config.llm, "provider", LLMProvider.MISTRAL)
    client = TestClient(app)
    response = client.get("/v1/models")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert ids == {"sgr-agent"}


def test_models_default_for_openai(monkeypatch):
    monkeypatch.setattr(config.llm, "provider", LLMProvider.OPENAI)
    client = TestClient(app)
    response = client.get("/v1/models")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert "sgr-agent" in ids
    assert len(ids) >= 3
