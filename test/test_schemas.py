"""Tests for the stable serialization contracts in ``edkg_dl.schemas``."""

from __future__ import annotations

import json

import numpy as np
import pytest

from edkg_dl.schemas import (
    AOCandidate,
    AOPRelation,
    CausalChainResult,
    EventPrediction,
    PredictionResult,
    SensitiveEvent,
    to_json_value,
)


def test_to_json_value_converts_numpy_scalars_and_containers() -> None:
    """NumPy scalars, arrays, mappings, and tuples become JSON-compatible."""
    assert to_json_value(np.float32(2.5)) == 2.5
    assert to_json_value(np.asarray([1, 2])) == [1, 2]
    assert to_json_value({"b": np.int64(1), "a": (1, 2)}) == {"b": 1, "a": [1, 2]}
    assert to_json_value("plain") == "plain"


def test_event_prediction_round_trip_and_node_state() -> None:
    """Event predictions serialize and deserialize with a derived node state."""
    event = EventPrediction("E1", {"Type": "KE"}, 1, True, 0.5, False)
    restored = EventPrediction.from_dict(event.to_dict())
    assert restored == event
    payload = event.to_dict()
    assert payload["node_state"] == "active"
    assert payload["quantitative"] == {"activity": 0.5, "in_ad": False}

    inactive = EventPrediction("E2", {}, 0, False, None, None)
    assert inactive.to_dict()["node_state"] == "inactive"
    assert inactive.to_dict()["quantitative"] is None


def test_ao_candidate_round_trip() -> None:
    """AO candidates round-trip through their dict form."""
    candidate = AOCandidate("E2", 1.5, 1, False, True, True, "selected")
    assert AOCandidate.from_dict(candidate.to_dict()) == candidate
    missing_value = AOCandidate("E3", None, 0, None, False, False, "inactive")
    assert AOCandidate.from_dict(missing_value.to_dict()) == missing_value


def test_causal_chain_result_round_trip() -> None:
    """Causal-chain results round-trip through their dict form."""
    chain = CausalChainResult(
        "AOP-1",
        ("E1", "E2"),
        (0.5, None),
        "E2",
        "AO",
        False,
        False,
        None,
        None,
        False,
        ("inactive_event", "missing_quantitative_value"),
    )
    assert CausalChainResult.from_dict(chain.to_dict()) == chain


def test_prediction_result_round_trip(result: PredictionResult) -> None:
    """Complete results survive a to_dict/from_dict round trip unchanged."""
    restored = PredictionResult.from_dict(result.to_dict())
    assert restored == result
    assert PredictionResult.from_dict(restored.to_dict()) == result


def test_prediction_result_dict_is_json_serializable(result: PredictionResult) -> None:
    """The serialized result is directly JSON-dumpable."""
    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    assert json.loads(payload)["smiles"] == result.smiles


@pytest.mark.parametrize(
    ("tabular", "graph", "expected"),
    [(0, 0, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1)],
)
def test_final_edc_prediction_or_semantics(tabular: int, graph: int, expected: int) -> None:
    """The final verdict is the logical OR of both model tracks."""
    result = PredictionResult(
        smiles="CCO",
        events={},
        tabular_edc_prediction=tabular,
        graph_edc_prediction=graph,
        qualitative_in_ad=True,
        quantitative_in_ad=None,
        sensitive_event=None,
        sensitive_paths=(),
        aop_relations=(),
    )
    assert result.final_edc_prediction == expected


def test_legacy_info_and_tuple(make_result) -> None:
    """Legacy conversions reproduce the historical nested mapping and tuple."""
    result = make_result()
    info = result.legacy_info()
    assert info["E1"]["qualitativeActivity"] == 1
    assert info["E1"]["qualitativeAD"] is True
    assert info["E2"]["quantitativeActivity"] == 1.5
    assert info["E2"]["quantitativeAD"] is False
    legacy = result.to_legacy_tuple()
    assert len(legacy) == 9
    assert legacy[1] == 1
    assert legacy[2] == 0
    assert legacy[3] == [{"source": "E1", "target": "E2", "value": 1.5, "WOE": "High"}]
    assert legacy[5] is True
    assert legacy[6] == "E2"
    assert legacy[7] == 1.5
    assert legacy[8] == [["E1", "E2"]]


def test_sensitive_event_and_relation_dicts() -> None:
    """Small contract objects expose flat JSON-compatible dicts."""
    assert SensitiveEvent("E2", 1.5).to_dict() == {"event_id": "E2", "value": 1.5}
    relation = AOPRelation("E1", "E2", 1.5, "High")
    assert relation.to_dict() == {
        "source": "E1",
        "target": "E2",
        "value": 1.5,
        "weight_of_evidence": "High",
    }
