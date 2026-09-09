"""Tests for the pure domain computations under ``edkg_dl.domain``."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from edkg_dl.domain import (
    CausalChainPolicy,
    aggregate_applicability,
    evaluate_causal_chains,
    find_sensitive_paths,
    select_sensitive_ao,
)
from edkg_dl.domain.applicability import ApplicabilityDomain
from edkg_dl.schemas import EventPrediction


def event(
    event_id: str,
    event_type: str,
    *,
    activity: int = 1,
    value: float | None = 0.0,
    in_ad: bool | None = True,
) -> EventPrediction:
    """Build a shorthand event prediction for domain tests."""
    return EventPrediction(
        event_id=event_id,
        metadata={"Type": event_type},
        qualitative_activity=activity,
        qualitative_in_ad=True,
        quantitative_activity=value,
        quantitative_in_ad=in_ad,
    )


class TestAggregateApplicability:
    """Majority-vote aggregation semantics."""

    def test_empty_returns_none(self) -> None:
        """No endpoint verdicts yield ``None``."""
        assert aggregate_applicability([]) is None

    def test_tie_counts_as_inside(self) -> None:
        """Ties count as inside the domain."""
        assert aggregate_applicability([True, False]) is True

    def test_majority_wins(self) -> None:
        """The majority threshold decides the aggregate."""
        assert aggregate_applicability([False, False, True]) is False
        assert aggregate_applicability([True, True, False]) is True
        assert aggregate_applicability([True]) is True


class TestApplicabilityDomain:
    """Euclidean-distance applicability domain."""

    def test_build_from_training_frame(self) -> None:
        """The domain centroid and cutoff come from the training matrix."""
        training = pd.DataFrame(
            {"f1": [0.0, 2.0], "f2": [0.0, 2.0]},
            index=["s0", "s1"],
        )
        domain = ApplicabilityDomain.from_training_frame(training)
        assert domain.feature_names == ("f1", "f2")
        assert domain.center == (1.0, 1.0)
        assert domain.cutoff == pytest.approx(2**0.5)

    def test_contains_boundary_and_outside(self) -> None:
        """Distance equal to the cutoff stays inside; beyond is outside."""
        training = pd.DataFrame({"f1": [0.0, 2.0], "f2": [0.0, 2.0]}, index=["s0", "s1"])
        domain = ApplicabilityDomain.from_training_frame(training)
        boundary = pd.DataFrame({"f1": [2.0], "f2": [0.0]}, index=["m"])
        far = pd.DataFrame({"f1": [50.0], "f2": [50.0]}, index=["m"])
        assert domain.contains(boundary) is True
        assert domain.contains(far) is False

    def test_contains_requires_single_row(self) -> None:
        """Multi-row frames are rejected."""
        training = pd.DataFrame({"f1": [0.0, 2.0], "f2": [0.0, 2.0]}, index=["s0", "s1"])
        domain = ApplicabilityDomain.from_training_frame(training)
        two_rows = pd.DataFrame({"f1": [0.0, 1.0], "f2": [0.0, 1.0]}, index=["a", "b"])
        with pytest.raises(ValueError, match="exactly one sample"):
            domain.contains(two_rows)

    def test_contains_missing_column(self) -> None:
        """Missing feature columns raise ``KeyError``."""
        training = pd.DataFrame({"f1": [0.0, 2.0], "f2": [0.0, 2.0]}, index=["s0", "s1"])
        domain = ApplicabilityDomain.from_training_frame(training)
        with pytest.raises(KeyError):
            domain.contains(pd.DataFrame({"f1": [1.0]}, index=["m"]))


class TestFindSensitivePaths:
    """Bounded path discovery from the sensitive event."""

    INDEX_TO_EVENT = {0: "E0", 1: "E1", 2: "E2"}
    EDGES = ((0, 1), (1, 2))

    def _find(self, **overrides: Any) -> Any:
        """Run the search with defaults over the shared three-event chain."""
        parameters: dict[str, Any] = {
            "index_to_event": self.INDEX_TO_EVENT,
            "edges": self.EDGES,
            "active_events": {"E0", "E1", "E2"},
            "sensitive_event": "E0",
        }
        parameters.update(overrides)
        return find_sensitive_paths(**parameters)

    def test_paths_follow_edge_direction_from_sensitive(self) -> None:
        """Paths start at the sensitive event and follow configured edges."""
        result = self._find()
        assert result.paths == (("E0", "E1"), ("E0", "E1", "E2"))
        assert result.truncated is False

    def test_no_sensitive_event_returns_empty(self) -> None:
        """Without a sensitive event nothing is searched."""
        result = self._find(sensitive_event=None)
        assert result.paths == ()
        assert result.truncated is False

    def test_inactive_events_break_paths(self) -> None:
        """Edges touching inactive events are excluded from the graph."""
        result = self._find(active_events={"E0", "E2"})
        assert result.paths == ()

    def test_sensitive_outside_graph_returns_empty(self) -> None:
        """A sensitive event without active edges yields no paths."""
        result = self._find(sensitive_event="E2")
        assert result.paths == ()
        assert result.truncated is False

    def test_unknown_sensitive_event_returns_empty(self) -> None:
        """An event ID absent from the mapping yields no paths."""
        result = self._find(sensitive_event="missing")
        assert result.paths == ()

    def test_max_paths_truncates_with_flag(self) -> None:
        """The cardinality bound reports leftover paths."""
        result = self._find(max_paths=1)
        assert result.paths == (("E0", "E1"),)
        assert result.truncated is True

    def test_exact_max_paths_is_not_truncated(self) -> None:
        """A bound equal to the path count reports no truncation."""
        result = self._find(max_paths=2)
        assert len(result.paths) == 2
        assert result.truncated is False

    def test_max_length_limits_edges(self) -> None:
        """The length cutoff keeps only short simple paths."""
        result = self._find(max_length=1)
        assert result.paths == (("E0", "E1"),)

    def test_max_paths_below_one_raises(self) -> None:
        """A non-positive cardinality bound is rejected."""
        with pytest.raises(ValueError, match="max_paths"):
            self._find(max_paths=0)


class TestSelectSensitiveAo:
    """Sensitive AO candidate selection."""

    def _select(self, predictions: dict[str, EventPrediction], quantitative: set[str]) -> Any:
        """Run selection with the given predictions and quantitative set."""
        return select_sensitive_ao(
            event_predictions=predictions,
            quantitative_event_ids=quantitative,
        )

    def test_selects_minimum_value(self) -> None:
        """The eligible AO with the smallest quantitative value wins."""
        predictions = {
            "E0": event("E0", "AO", value=5.0),
            "E1": event("E1", "AO", value=2.0),
            "E2": event("E2", "KE", value=0.5),
        }
        selection = self._select(predictions, {"E0", "E1", "E2"})
        assert selection.selected is not None
        assert selection.selected.event_id == "E1"
        assert selection.selected.value == 2.0
        statuses = {item.event_id: item.status for item in selection.candidates}
        assert statuses == {"E0": "eligible", "E1": "selected"}

    def test_tie_breaks_by_event_order(self) -> None:
        """Equal values resolve to the earlier event in prediction order."""
        predictions = {
            "E0": event("E0", "AO", value=3.0),
            "E1": event("E1", "AO", value=3.0),
        }
        selection = self._select(predictions, {"E0", "E1"})
        assert selection.selected is not None
        assert selection.selected.event_id == "E0"

    def test_candidate_statuses(self) -> None:
        """Every AO reports a structured eligibility status."""
        predictions = {
            "E0": event("E0", "AO"),
            "E1": event("E1", "AO", activity=0),
            "E2": event("E2", "AO", value=None),
        }
        selection = self._select(predictions, {"E0", "E1", "E2"})
        assert selection.selected is not None
        assert selection.selected.event_id == "E0"
        statuses = {item.event_id: item.status for item in selection.candidates}
        assert statuses == {"E0": "selected", "E1": "inactive", "E2": "missing_quantitative_result"}

    def test_ao_without_quantitative_model(self) -> None:
        """AOs lacking a quantitative model are reported as such."""
        predictions = {"E0": event("E0", "AO")}
        selection = self._select(predictions, set())
        assert selection.selected is None
        candidate = selection.candidates[0]
        assert candidate.status == "no_quantitative_model"
        assert candidate.has_quantitative_model is False
        assert candidate.eligible is False

    def test_no_eligible_ao_selects_none(self) -> None:
        """No eligible candidates means no sensitive event."""
        predictions = {"E0": event("E0", "AO", activity=0)}
        selection = self._select(predictions, {"E0"})
        assert selection.selected is None


class TestEvaluateCausalChains:
    """AOP causal-chain evaluation under the default policy."""

    def test_valid_strictly_increasing_chain(self) -> None:
        """An all-active, strictly increasing chain ending at an AO is valid."""
        predictions = {
            "E0": event("E0", "MIE", value=0.1),
            "E1": event("E1", "KE", value=0.5),
            "E2": event("E2", "AO", value=1.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1", "E2"]},
            event_predictions=predictions,
        )
        assert len(chains) == 1
        chain = chains[0]
        assert chain.valid is True
        assert chain.failure_reasons == ()
        assert chain.monotonic is True
        assert chain.terminal_type == "AO"

    def test_inactive_event_invalidates(self) -> None:
        """An inactive member produces the inactive_event reason."""
        predictions = {
            "E0": event("E0", "MIE", value=0.1),
            "E1": event("E1", "KE", activity=0, value=0.5),
            "E2": event("E2", "AO", value=1.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1", "E2"]},
            event_predictions=predictions,
        )
        assert chains[0].valid is False
        assert chains[0].all_active is False
        assert "inactive_event" in chains[0].failure_reasons

    def test_missing_quantitative_value(self) -> None:
        """A missing value blocks monotonicity evaluation."""
        predictions = {
            "E0": event("E0", "MIE", value=None),
            "E1": event("E1", "AO", value=1.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1"]},
            event_predictions=predictions,
        )
        chain = chains[0]
        assert chain.monotonic is None
        assert "missing_quantitative_value" in chain.failure_reasons

    def test_non_monotonic_values(self) -> None:
        """Non-increasing values invalidate the chain."""
        predictions = {
            "E0": event("E0", "MIE", value=1.0),
            "E1": event("E1", "KE", value=0.5),
            "E2": event("E2", "AO", value=1.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1", "E2"]},
            event_predictions=predictions,
        )
        assert chains[0].monotonic is False
        assert "non_monotonic_values" in chains[0].failure_reasons

    def test_terminal_not_ao(self) -> None:
        """A non-AO terminal event is reported."""
        predictions = {
            "E0": event("E0", "MIE", value=0.1),
            "E1": event("E1", "KE", value=0.5),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1"]},
            event_predictions=predictions,
        )
        assert "terminal_not_ao" in chains[0].failure_reasons

    def test_single_event_chain_rejected_by_default(self) -> None:
        """Single-event chains are invalid unless explicitly allowed."""
        predictions = {"E0": event("E0", "AO", value=1.0)}
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-0": ["E0"]},
            event_predictions=predictions,
        )
        assert chains[0].valid is False
        assert "single_event_chain" in chains[0].failure_reasons

    def test_single_event_chain_allowed_by_policy(self) -> None:
        """The allow_single_event policy accepts single-event chains."""
        predictions = {"E0": event("E0", "AO", value=1.0)}
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-0": ["E0"]},
            event_predictions=predictions,
            policy=CausalChainPolicy(allow_single_event=True),
        )
        assert chains[0].valid is True

    def test_equal_values_pass_with_non_decreasing_policy(self) -> None:
        """Non-strict policies accept repeated adjacent values."""
        predictions = {
            "E0": event("E0", "MIE", value=0.5),
            "E1": event("E1", "KE", value=0.5),
            "E2": event("E2", "AO", value=1.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1", "E2"]},
            event_predictions=predictions,
            policy=CausalChainPolicy(monotonicity="non_decreasing"),
        )
        assert chains[0].valid is True
        assert chains[0].monotonic is True

    def test_require_quantitative_in_ad_policy(self) -> None:
        """Out-of-domain quantitative results invalidate under the strict policy."""
        predictions = {
            "E0": event("E0", "MIE", value=0.1, in_ad=False),
            "E1": event("E1", "AO", value=1.0, in_ad=True),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-1": ["E0", "E1"]},
            event_predictions=predictions,
            policy=CausalChainPolicy(require_quantitative_in_ad=True),
        )
        assert chains[0].all_quantitative_in_ad is False
        assert "quantitative_outside_ad" in chains[0].failure_reasons

    def test_unknown_monotonicity_raises(self) -> None:
        """Unsupported monotonicity names are rejected."""
        with pytest.raises(ValueError, match="Unsupported"):
            evaluate_causal_chains(
                aop_to_events={"AOP-1": ["E0"]},
                event_predictions={"E0": event("E0", "AO")},
                policy=CausalChainPolicy(monotonicity="bogus"),
            )

    def test_multiple_chains_preserve_order(self) -> None:
        """Chains are returned in configuration order."""
        predictions = {
            "E0": event("E0", "AO", value=1.0),
            "E1": event("E1", "AO", value=2.0),
        }
        chains = evaluate_causal_chains(
            aop_to_events={"AOP-2": ["E1"], "AOP-1": ["E0"]},
            event_predictions=predictions,
        )
        assert [chain.aop_id for chain in chains] == ["AOP-2", "AOP-1"]
