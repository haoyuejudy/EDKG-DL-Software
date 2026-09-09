"""Shared fixtures and builders for the EDKG-DL test suite."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from edkg_dl.domain import CausalChainPolicy
from edkg_dl.schemas import (
    AOCandidate,
    AOPRelation,
    CausalChainResult,
    EventPrediction,
    PredictionResult,
    SensitiveEvent,
)


def build_settings_payload() -> dict[str, Any]:
    """Build a valid five-event settings payload shared across tests."""
    return {
        "index2Event": {"0": "E0", "1": "E1", "2": "E2", "3": "E3", "4": "E4"},
        "edgeIndex": [[2, 1, 0], [1, 0, 4]],
        "edgeConfidence": [3, 5, 1],
        "eventInfo": {
            "E0": {"Type": "AO"},
            "E1": {"Type": "KE"},
            "E2": {"Type": "MIE"},
            "E3": {"Type": "AO"},
            "E4": {"Type": "KE"},
        },
        "qualitativeAOPSingleEventsIndexes": [1],
        "qualitativeAOPSingleEventsWOE": ["High"],
        "quantitative_indexes": [0, 1, 2, 3],
        "AOP2Event": {"AOP-1": ["E2", "E1", "E0"]},
    }


def build_result(smiles: str = "CCO") -> PredictionResult:
    """Build a minimal but complete prediction result for report and API tests."""
    return PredictionResult(
        smiles=smiles,
        events={
            "E1": EventPrediction("E1", {"Type": "KE"}, 1, True, 0.5, True),
            "E2": EventPrediction("E2", {"Type": "AO"}, 1, True, 1.5, False),
        },
        tabular_edc_prediction=1,
        graph_edc_prediction=0,
        qualitative_in_ad=True,
        quantitative_in_ad=True,
        sensitive_event=SensitiveEvent("E2", 1.5),
        sensitive_paths=(("E1", "E2"),),
        aop_relations=(AOPRelation("E1", "E2", 1.5, "High"),),
        ao_candidates=(AOCandidate("E2", 1.5, 1, False, True, True, "selected"),),
        causal_chains=(
            CausalChainResult(
                "AOP-1", ("E1", "E2"), (0.5, 1.5), "E2", "AO", True, True, True, False, True, ()
            ),
        ),
        sensitive_event_causally_validated=True,
        model_version="test",
    )


class StubPipeline:
    """Configurable pipeline stand-in used by API and HTTP tests."""

    model_version = "stub-1"

    def __init__(
        self,
        results: dict[str, PredictionResult] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        """Store canned per-SMILES results and errors."""
        self.causal_chain_policy = CausalChainPolicy()
        self.model_registry = SimpleNamespace(cached_model_count=0)
        self.settings = SimpleNamespace(
            event_info={"E1": {"Type": "KE"}, "E2": {"Type": "AO"}},
            quantitative_indexes=frozenset({2}),
            aop_to_events={"AOP-1": ["E1", "E2"]},
        )
        self._results = results or {}
        self._errors = errors or {}

    def predict(self, smiles: str) -> PredictionResult:
        """Return the canned result or raise the configured error."""
        if smiles in self._errors:
            raise self._errors[smiles]
        return self._results.get(smiles, build_result(smiles))

    def predict_with_features(self, smiles: str) -> tuple[PredictionResult, None]:
        """Mirror the pipeline variant that also returns features."""
        return self.predict(smiles), None


@pytest.fixture
def settings_payload() -> dict[str, Any]:
    """Provide a fresh valid settings payload for mutation."""
    return build_settings_payload()


@pytest.fixture
def settings_file(tmp_path: Path, settings_payload: dict[str, Any]) -> Path:
    """Write the valid settings payload to a temporary JSON file."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings_payload), encoding="utf-8")
    return path


@pytest.fixture
def make_result() -> Any:
    """Expose the shared minimal result builder."""
    return build_result


@pytest.fixture
def result() -> PredictionResult:
    """Provide a default minimal prediction result."""
    return build_result()


@pytest.fixture
def stub_pipeline() -> StubPipeline:
    """Provide a permissive stub pipeline."""
    return StubPipeline()
