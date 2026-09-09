"""HTTP API tests against a stub predictor, skipped without the API extras."""

from __future__ import annotations

import pytest


fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi.testclient")

from conftest import StubPipeline
from fastapi.testclient import TestClient

from edkg_dl import Predictor
from edkg_dl.exceptions import InvalidSmilesError
from edkg_dl.http_api import create_app


@pytest.fixture
def client(stub_pipeline: StubPipeline) -> TestClient:
    """Provide a test client wired to the stub pipeline."""
    return TestClient(create_app(predictor=Predictor(pipeline=stub_pipeline)))


def test_create_app_rejects_invalid_batch_cap(stub_pipeline: StubPipeline) -> None:
    """The batch cap is bounded between 1 and 100."""
    with pytest.raises(ValueError, match="max_batch_size"):
        create_app(predictor=Predictor(pipeline=stub_pipeline), max_batch_size=0)
    with pytest.raises(ValueError, match="max_batch_size"):
        create_app(predictor=Predictor(pipeline=stub_pipeline), max_batch_size=101)


def test_health(client: TestClient) -> None:
    """Liveness does not depend on model inference."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_model_version(client: TestClient) -> None:
    """Readiness exposes the pipeline version and cache size."""
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["model_version"] == "stub-1"
    assert payload["cached_model_count"] == 0


def test_model_info_reports_settings(client: TestClient) -> None:
    """Model info summarizes events, AOs, and the causal-chain policy."""
    payload = client.get("/v1/model-info").json()
    assert payload["event_count"] == 2
    assert payload["ao_count"] == 1
    assert payload["quantitative_event_count"] == 1
    assert payload["causal_chain_count"] == 1
    assert payload["causal_chain_policy"]["monotonicity"] == "strict_increasing"


def test_single_prediction(client: TestClient) -> None:
    """A valid request returns the full result mapping."""
    response = client.post("/v1/predictions", json={"smiles": "CCO"})
    assert response.status_code == 200
    assert response.json()["smiles"] == "CCO"


def test_single_prediction_blank_smiles_rejected(client: TestClient) -> None:
    """Blank SMILES fail request validation."""
    response = client.post("/v1/predictions", json={"smiles": "   "})
    assert response.status_code == 422


def test_single_prediction_handled_error(client: TestClient) -> None:
    """Handled prediction errors map to 422 with a code."""
    stub = StubPipeline(errors={"bad": InvalidSmilesError("bad SMILES")})
    error_client = TestClient(create_app(predictor=Predictor(pipeline=stub)))
    response = error_client.post("/v1/predictions", json={"smiles": "bad"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "InvalidSmilesError"


def test_batch_prediction(client: TestClient) -> None:
    """A batch preserves order and reports counts."""
    response = client.post(
        "/v1/predictions/batch", json={"smiles": ["CCO", "CCC"], "max_workers": 2}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["succeeded"] == 2
    assert [item["smiles"] for item in payload["items"]] == ["CCO", "CCC"]


def test_batch_exceeding_service_cap(stub_pipeline: StubPipeline) -> None:
    """Batches beyond the service cap are rejected with 413."""
    capped = TestClient(create_app(predictor=Predictor(pipeline=stub_pipeline), max_batch_size=1))
    response = capped.post("/v1/predictions/batch", json={"smiles": ["CCO", "CCC"]})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "BatchTooLarge"


def test_batch_invalid_request(client: TestClient) -> None:
    """Empty batches and bad worker counts fail request validation."""
    empty = client.post("/v1/predictions/batch", json={"smiles": []})
    assert empty.status_code == 422
    bad_workers = client.post("/v1/predictions/batch", json={"smiles": ["CCO"], "max_workers": 9})
    assert bad_workers.status_code == 422
