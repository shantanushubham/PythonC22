"""The committed openapi.json must describe what the service actually does."""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from app.main import app  # noqa: E402
from export_openapi import SPEC_PATH, render_spec  # noqa: E402

client = TestClient(app)


def test_committed_spec_is_up_to_date():
    assert SPEC_PATH.read_text() == render_spec(), (
        "openapi.json is stale. Run: uv run python scripts/export_openapi.py"
    )


def test_spec_is_served():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == json.loads(SPEC_PATH.read_text())
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_openapi_endpoint_returns_the_same_spec():
    response = client.get("/openapi")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == client.get("/openapi.json").json()


def test_spec_endpoints_are_not_listed_in_the_spec():
    assert "/openapi" not in app.openapi()["paths"]


def test_spec_documents_400_not_422():
    spec = app.openapi()

    for operations in spec["paths"].values():
        for operation in operations.values():
            assert "422" not in operation["responses"]
    assert "400" in spec["paths"]["/api/v1/payments"]["post"]["responses"]
    assert "HTTPValidationError" not in spec["components"]["schemas"]


def test_operations_have_stable_ids():
    spec = app.openapi()

    ids = {
        operation["operationId"]
        for operations in spec["paths"].values()
        for operation in operations.values()
    }
    assert ids == {"getHealth", "createPayment", "getPayment"}


def test_payment_responses_match_documented_status_codes():
    responses = app.openapi()["paths"]["/api/v1/payments"]["post"]["responses"]

    assert set(responses) == {"200", "400", "402", "409", "500"}
    assert "Idempotent-Replayed" in responses["200"]["headers"]
