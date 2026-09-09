"""AOP causal-chain evaluation based on qualitative activation and quantitative monotonicity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from ..schemas import CausalChainResult, EventPrediction


Monotonicity = Literal[
    "strict_increasing",
    "non_decreasing",
    "strict_decreasing",
    "non_increasing",
]


@dataclass(frozen=True)
class CausalChainPolicy:
    """Explicit policy controlling causal-chain validity evaluation."""

    monotonicity: Monotonicity = "strict_increasing"
    require_terminal_ao: bool = True
    require_all_active: bool = True
    require_quantitative_in_ad: bool = False
    allow_single_event: bool = False


def evaluate_causal_chains(
    *,
    aop_to_events: Mapping[str, list[str]],
    event_predictions: Mapping[str, EventPrediction],
    policy: CausalChainPolicy | None = None,
) -> tuple[CausalChainResult, ...]:
    """Evaluate each configured AOP causal chain.

    Args:
        aop_to_events: Mapping of AOP ID to its ordered event chain.
        event_predictions: All event predictions for this request.
        policy: Causal-chain validity policy; defaults to the
            strict-increasing policy compatible with the legacy algorithm.

    Returns:
        Structured causal-chain results in configuration order.

    Raises:
        ValueError: Raised when the policy monotonicity name is unsupported.
    """
    active_policy = policy or CausalChainPolicy()
    _validate_monotonicity(active_policy.monotonicity)
    results: list[CausalChainResult] = []

    for aop_id, configured_events in aop_to_events.items():
        events = tuple(configured_events)
        predictions = tuple(event_predictions[event_id] for event_id in events)
        values = tuple(prediction.quantitative_activity for prediction in predictions)
        terminal = predictions[-1]
        terminal_type = terminal.metadata.get("Type")
        all_active = all(prediction.qualitative_activity == 1 for prediction in predictions)
        all_quantified = all(value is not None for value in values)
        in_ad_values = tuple(prediction.quantitative_in_ad for prediction in predictions)
        all_in_ad = None if any(value is None for value in in_ad_values) else all(in_ad_values)

        monotonic = None
        if len(values) >= 2 and all_quantified:
            numeric_values = tuple(float(value) for value in values if value is not None)
            monotonic = _is_monotonic(numeric_values, active_policy.monotonicity)

        reasons: list[str] = []
        if active_policy.require_terminal_ao and terminal_type != "AO":
            reasons.append("terminal_not_ao")
        if len(events) == 1 and not active_policy.allow_single_event:
            reasons.append("single_event_chain")
        if active_policy.require_all_active and not all_active:
            reasons.append("inactive_event")
        if not all_quantified:
            reasons.append("missing_quantitative_value")
        elif len(events) >= 2 and not monotonic:
            reasons.append("non_monotonic_values")
        if active_policy.require_quantitative_in_ad and all_in_ad is not True:
            reasons.append("quantitative_outside_ad")

        results.append(
            CausalChainResult(
                aop_id=aop_id,
                events=events,
                values=tuple(None if value is None else float(value) for value in values),
                terminal_event=events[-1],
                terminal_type=None if terminal_type is None else str(terminal_type),
                all_active=all_active,
                all_quantified=all_quantified,
                monotonic=monotonic,
                all_quantitative_in_ad=all_in_ad,
                valid=not reasons,
                failure_reasons=tuple(reasons),
            )
        )
    return tuple(results)


def _validate_monotonicity(monotonicity: str) -> None:
    """Validate a supported monotonicity policy name.

    Args:
        monotonicity: Policy name to validate.

    Raises:
        ValueError: Raised when the policy name is unsupported.
    """
    if monotonicity not in {
        "strict_increasing",
        "non_decreasing",
        "strict_decreasing",
        "non_increasing",
    }:
        raise ValueError(f"Unsupported causal-chain monotonicity: {monotonicity}")


def _is_monotonic(values: tuple[float, ...], monotonicity: Monotonicity) -> bool:
    """Compare adjacent quantitative values in the given direction.

    Args:
        values: Quantitative sequence with at least two values.
        monotonicity: Monotonic direction and strictness.

    Returns:
        True when every adjacent pair satisfies the policy.
    """
    comparisons = {
        "strict_increasing": lambda left, right: left < right,
        "non_decreasing": lambda left, right: left <= right,
        "strict_decreasing": lambda left, right: left > right,
        "non_increasing": lambda left, right: left >= right,
    }
    compare = comparisons[monotonicity]
    return all(compare(left, right) for left, right in pairwise(values))
