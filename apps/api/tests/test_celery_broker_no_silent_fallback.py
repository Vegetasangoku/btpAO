"""
Tests verifying no silent fallback to memory:// broker outside of test mode,
and validating the /health/celery monitoring endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from app.core.celery_app import check_celery_broker_health, get_celery_broker_urls
from app.core.config import settings
from app.main import app


def test_no_silent_broker_fallback_in_production():
    """In production mode with eager=false, broker URL must remain the configured Redis URL and NOT switch to memory://."""
    broker, backend = get_celery_broker_urls(app_env="production", always_eager="false")
    assert broker == settings.CELERY_BROKER_URL
    assert not broker.startswith("memory://")
    assert backend == settings.CELERY_RESULT_BACKEND


def test_no_silent_broker_fallback_in_development():
    """In development mode with eager=false, broker URL must remain the configured Redis URL."""
    broker, backend = get_celery_broker_urls(app_env="development", always_eager="false")
    assert broker == settings.CELERY_BROKER_URL
    assert not broker.startswith("memory://")


def test_explicit_in_memory_allowed_only_for_test_or_eager():
    """memory:// is only returned when app_env is test/testing or always_eager is true."""
    # 1. Test env
    broker, backend = get_celery_broker_urls(app_env="test", always_eager="false")
    assert broker == "memory://"
    assert backend == "rpc://"

    # 2. Testing env
    broker_t, backend_t = get_celery_broker_urls(app_env="testing", always_eager="false")
    assert broker_t == "memory://"

    # 3. Always eager flag
    broker_e, backend_e = get_celery_broker_urls(app_env="production", always_eager="true")
    assert broker_e == "memory://"


def test_celery_healthcheck_endpoint_in_test_mode():
    """GET /health/celery returns 200 with structured info in test environment."""
    client = TestClient(app)
    res = client.get("/health/celery")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "broker" in data
    assert data["mode"] in ("test_in_memory", "distributed_broker")


def test_celery_healthcheck_detects_unreachable_broker_without_silent_mutation(monkeypatch):
    """When a remote broker is unreachable in distributed mode, healthcheck reports unhealthy with explicit error and does not mutate broker."""
    from celery import Celery

    dummy_celery = Celery("dummy", broker="redis://nonexistent-redis-host:6379/9")

    # Temporarily point check_celery_broker_health to dummy app
    import app.core.celery_app as celery_module
    monkeypatch.setattr(celery_module, "celery_app", dummy_celery)

    health = check_celery_broker_health()
    assert health["status"] == "unhealthy"
    assert health["broker"] == "redis://nonexistent-redis-host:6379/9"
    assert "error" in health
    # Ensure broker wasn't silently rewritten to memory://
    assert dummy_celery.conf.broker_url == "redis://nonexistent-redis-host:6379/9"
