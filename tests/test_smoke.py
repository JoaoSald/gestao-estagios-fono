"""Smoke test da FASE 2: a API sobe, a home renderiza e o /health responde
(inclusive tocando no banco). Usa o TestClient do FastAPI (httpx)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"   # exige o Postgres de pé (DATABASE_URL do .env)


def test_index_renderiza():
    r = client.get("/")
    assert r.status_code == 200
    assert "Gestão de Estágios" in r.text
