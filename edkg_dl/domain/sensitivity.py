"""Sensitive AO candidate selection."""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass

from ..schemas import AOCandidate, EventPrediction, SensitiveEvent


@dataclass(frozen=True)
class SensitivitySelection:
    """Sensitive AO selection result plus candidate status for all AOs."""

    selected: SensitiveEvent | None
    candidates: tuple[AOCandidate, ...]


def select_sensitive_ao(
    *,
    event_predictions: Mapping[str, EventPrediction],
    quantitative_event_ids: Set[str],
) -> SensitivitySelection:
    """Select the minimum value among activated AOs with quantitative results.

    Applicability-domain results are not used as a filter here; they are
    returned alongside the candidates to avoid silently discarding model
    predictions before the domain rules are confirmed.

    Args:
        event_predictions: Event predictions in stable event order.
        quantitative_event_ids: Set of event IDs with configured quantitative
            models.

    Returns:
        The selected sensitive AO, plus candidate status for every AO.
    """
    eligible: list[tuple[int, str, float]] = []
    statuses: list[tuple[str, EventPrediction, bool, str]] = []

    for order, (event_id, prediction) in enumerate(event_predictions.items()):
        if prediction.metadata.get("Type") != "AO":
            continue
        if event_id not in quantitative_event_ids:
            statuses.append((event_id, prediction, False, "no_quantitative_model"))
        elif prediction.qualitative_activity != 1:
            statuses.append((event_id, prediction, False, "inactive"))
        elif prediction.quantitative_activity is None:
            statuses.append((event_id, prediction, False, "missing_quantitative_result"))
        else:
            value = float(prediction.quantitative_activity)
            eligible.append((order, event_id, value))
            statuses.append((event_id, prediction, True, "eligible"))

    selected = None
    selected_id = None
    if eligible:
        _, selected_id, selected_value = min(eligible, key=lambda item: (item[2], item[0]))
        selected = SensitiveEvent(selected_id, selected_value)

    candidates = tuple(
        AOCandidate(
            event_id=event_id,
            value=None
            if prediction.quantitative_activity is None
            else float(prediction.quantitative_activity),
            qualitative_activity=prediction.qualitative_activity,
            quantitative_in_ad=prediction.quantitative_in_ad,
            has_quantitative_model=event_id in quantitative_event_ids,
            eligible=is_eligible,
            status="selected" if event_id == selected_id else status,
        )
        for event_id, prediction, is_eligible, status in statuses
    )
    return SensitivitySelection(selected=selected, candidates=candidates)
