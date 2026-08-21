"""
Pytest global test session configuration.
Sets test environment flags before test execution.
"""
import os

os.environ["APP_ENV"] = "test"
os.environ["CELERY_ALWAYS_EAGER"] = "true"

import app.core.celery_app as celery_module

# Ensure celery_app in test session uses test configuration
broker, backend = celery_module.get_celery_broker_urls(app_env="test", always_eager="true")
celery_module.celery_app.conf.update(
    broker_url=broker,
    result_backend=backend,
)
