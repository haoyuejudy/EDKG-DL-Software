"""End-to-end tests against the real cached model assets."""

from __future__ import annotations

import pytest

from edkg_dl import Predictor
from edkg_dl.config import ProjectPaths


@pytest.fixture(scope="module")
def predictor() -> Predictor:
    """Load the real predictor once, skipping when assets are not cached."""
    paths = ProjectPaths.resolve(None)
    if not paths.settings.is_file():
        pytest.skip("model assets are not cached locally")
    return Predictor.from_assets()


@pytest.mark.slow
def test_real_single_prediction_structure(predictor: Predictor) -> None:
    """A real prediction produces a complete schema-version-2 result."""
    result = predictor.predict("CCO")
    payload = result.to_dict()

    assert payload["schema_version"] == 2
    assert payload["model_version"]
    assert payload["smiles"] == "CCO"
    assert payload["final_edc_prediction"] in (0, 1)
    assert isinstance(payload["qualitative_in_ad"], bool)
    assert payload["duration_seconds"] >= 0

    events = payload["events"]
    assert len(events) > 50
    for event in events.values():
        assert event["node_state"] in ("active", "inactive")
        assert event["qualitative"]["activity"] in (0, 1)

    assert len(payload["causal_chains"]) > 100
    sensitive = payload["sensitive_event"]
    if sensitive is not None:
        assert sensitive["value"] > 0


@pytest.mark.slow
def test_real_batch_partial_failure(predictor: Predictor) -> None:
    """A real batch tolerates an invalid SMILES alongside a valid one."""
    batch = predictor.predict_batch(["CCO", ""], max_items=2)
    assert len(batch.items) == 2
    assert batch.succeeded == 1
    assert batch.failed == 1
    assert batch.items[0].result is not None
    assert batch.items[1].error_code == "InvalidSmilesError"
    payload = batch.to_dict()
    assert payload["items"][1]["error"]["code"] == "InvalidSmilesError"
