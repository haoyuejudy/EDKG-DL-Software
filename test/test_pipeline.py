"""Functional pipeline integration tests with injected stub components."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from edkg_dl.config import Settings
from edkg_dl.pipeline import PredictionPipeline
from edkg_dl.schemas import AOPRelation


class StubExtractor:
    """Feature extractor stand-in returning a one-row frame."""

    def extract(self, smiles: str) -> Any:
        """Return a single-row feature frame."""
        return pd.DataFrame({"feature": [1.0]}, index=[smiles])


class StubRegistry:
    """Endpoint registry stand-in with canned per-event outputs."""

    def __init__(self) -> None:
        """Configure canned outputs and an empty call log."""
        self.calls: list[tuple[str, str]] = []
        self._outputs = {
            ("qualitative", "E0"): (1, True),
            ("qualitative", "E1"): (1, True),
            ("qualitative", "E2"): (1, True),
            ("qualitative", "E3"): (0, False),
            ("qualitative", "E4"): (1, True),
            ("quantitative", "E0"): (0.5, True),
            ("quantitative", "E1"): (-1.0, False),
            ("quantitative", "E2"): (-2.0, False),
            ("edc", "edc"): (1, True),
        }

    def predict(self, kind: str, event_id: str, features: Any) -> tuple[Any, bool]:
        """Record the call and return the canned output."""
        self.calls.append((kind, event_id))
        return self._outputs[(kind, event_id)]


class StubGraph:
    """Graph predictor stand-in returning a fixed classification."""

    def __init__(self, prediction: int = 0) -> None:
        """Store the fixed classification."""
        self.prediction = prediction

    def predict(self, qualitative_results: dict[str, int]) -> tuple[int, tuple[Any, ...]]:
        """Return the fixed classification plus one relation."""
        return self.prediction, (AOPRelation("E1", "E0", 0.5, "High"),)


@pytest.fixture
def stub_registry() -> StubRegistry:
    """Provide a registry stub with a call log."""
    return StubRegistry()


@pytest.fixture
def pipeline(settings_file: Any, stub_registry: StubRegistry) -> PredictionPipeline:
    """Build a pipeline wired entirely to stub components."""
    return PredictionPipeline(
        settings=Settings.load(settings_file),
        feature_extractor=StubExtractor(),
        model_registry=stub_registry,
        graph_predictor=StubGraph(0),
        model_version="stub-1",
    )


def test_predict_full_flow(pipeline: PredictionPipeline, stub_registry: StubRegistry) -> None:
    """The orchestrated flow produces a complete structured result."""
    result = pipeline.predict("  CCO  ")

    assert result.smiles == "CCO"
    assert result.model_version == "stub-1"
    assert list(result.events) == ["E0", "E1", "E2", "E3", "E4"]

    active = result.events["E0"]
    assert active.qualitative_activity == 1
    assert active.quantitative_activity == pytest.approx(10**0.5)
    inactive = result.events["E3"]
    assert inactive.qualitative_activity == 0
    assert inactive.quantitative_activity is None
    unmodelled = result.events["E4"]
    assert unmodelled.qualitative_activity == 1
    assert unmodelled.quantitative_activity is None

    assert ("quantitative", "E3") not in stub_registry.calls
    assert ("quantitative", "E4") not in stub_registry.calls
    assert ("edc", "edc") in stub_registry.calls

    assert result.sensitive_event is not None
    assert result.sensitive_event.event_id == "E0"
    assert result.sensitive_event.value == pytest.approx(10**0.5)
    statuses = {candidate.event_id: candidate.status for candidate in result.ao_candidates}
    assert statuses == {"E0": "selected", "E3": "inactive"}

    chain = result.causal_chains[0]
    assert chain.aop_id == "AOP-1"
    assert chain.valid is True
    assert chain.monotonic is True
    assert chain.all_quantitative_in_ad is False
    assert result.sensitive_event_causally_validated is True

    assert result.sensitive_paths == (("E0", "E4"),)
    assert result.paths_truncated is False

    assert result.tabular_edc_prediction == 1
    assert result.graph_edc_prediction == 0
    assert result.final_edc_prediction == 1
    assert result.qualitative_in_ad is True
    assert result.quantitative_in_ad is False
    assert result.aop_relations == (AOPRelation("E1", "E0", 0.5, "High"),)

    assert result.started_at is not None
    assert result.finished_at is not None
    assert result.duration_seconds >= 0


def test_predict_result_is_json_serializable(pipeline: PredictionPipeline) -> None:
    """The full result dict survives JSON encoding."""
    payload = json.dumps(pipeline.predict("CCO").to_dict(), ensure_ascii=False)
    data = json.loads(payload)
    assert data["events"]["E3"]["node_state"] == "inactive"
    assert data["events"]["E0"]["node_state"] == "active"
    assert data["causal_chains"][0]["valid"] is True


def test_predict_with_features_returns_features(pipeline: PredictionPipeline) -> None:
    """The feature-returning variant exposes the extracted frame."""
    result, features = pipeline.predict_with_features("CCO")
    assert result.smiles == "CCO"
    assert features.shape == (1, 1)


def test_predict_features_uses_precomputed_frame(pipeline: PredictionPipeline) -> None:
    """Prediction can run from a precomputed feature row."""
    features = pd.DataFrame({"feature": [1.0]}, index=["CCO"])
    result = pipeline.predict_features("CCO", features)
    assert result.sensitive_event is not None
    assert result.sensitive_event.event_id == "E0"


def test_predict_failure_isolation_in_batch(pipeline: PredictionPipeline) -> None:
    """The stubbed pipeline integrates with batch failure isolation."""
    from edkg_dl.api import Predictor

    batch = Predictor(pipeline=pipeline).predict_batch(["CCO"], max_items=1)
    assert batch.succeeded == 1
