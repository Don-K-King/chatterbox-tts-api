"""Tests for the voice export API endpoint."""

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import voices
from tests import conftest as test_conftest

# Disable the API health check autouse fixture for this module. The test uses a local
# FastAPI TestClient and does not require the external service to be running.
os.environ.setdefault("CHATTERBOX_SKIP_API_HEALTH", "true")
test_conftest.SKIP_API_HEALTH_CHECK = True


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the voices router registered."""

    app = FastAPI()
    app.include_router(voices.base_router, prefix="/v1")
    return app


def test_voice_export_returns_zip_archive():
    """GET /v1/voices/export should return a ZIP archive with a 200 status."""

    app = create_test_app()

    with TestClient(app) as client:
        response = client.get("/v1/voices/export")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "application/zip" in content_type
    assert response.content, "Expected non-empty ZIP payload"
