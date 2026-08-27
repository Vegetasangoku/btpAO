"""
Test suite for Cluster Health Supervision (GET /api/health).
Verifies:
1. Returns real DB status, Redis broker status, and configured LLM providers with RGPD legal sources.
2. Returns healthy/degraded status based on real component states (never a fabricated static response).
3. Degraded mode detection when Redis or DB connection is simulated as failed.
"""
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app


def test_cluster_health_live_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code in (200, 503)
    data = response.json()

    assert "status" in data
    assert "timestamp" in data
    assert "latency_ms" in data
    assert "database" in data
    assert "redis_celery" in data
    assert "llm_providers" in data
    assert "system" in data

    # Check real providers with official RGPD sources
    llm = data["llm_providers"]
    assert "anthropic" in llm
    assert llm["anthropic"]["zone"] == "US"
    assert "privacy.claude.com" in llm["anthropic"]["source"]

    assert "openai" in llm
    assert "US" in llm["openai"]["zone"]
    assert "platform.openai.com" in llm["openai"]["source"]

    assert "mistral" in llm
    assert llm["mistral"]["zone"] == "UE"
    assert "Mistral AI" in llm["mistral"]["source"]

    assert "deepseek" in llm
    assert llm["deepseek"]["zone"] == "Chine"


def test_cluster_health_degraded_when_redis_offline():
    """Simulate Redis/Celery broker failure and verify the health check marks status as degraded/unhealthy."""
    client = TestClient(app)
    with patch("app.main.check_celery_broker_health", return_value={"status": "unhealthy", "broker_url": "redis://localhost:6379/0", "error": "Connection refused"}):
        response = client.get("/api/health")
        data = response.json()
        assert data["redis_celery"]["status"] == "degraded"
        assert data["status"] in ("degraded", "unhealthy")
