"""Stable, serializable prediction result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def to_json_value(value: Any) -> Any:
    """Convert NumPy-like scalars and containers to JSON-compatible values.

    Args:
        value: Any scalar or nested container.

    Returns:
        Recursively converted JSON-compatible value where possible.
    """
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if hasattr(value, "tolist") and callable(value.tolist):
        return to_json_value(value.tolist())
    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class EventPrediction:
    """Prediction and applicability-domain outcome for a single biological event."""

    event_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    qualitative_activity: int | None = None
    qualitative_in_ad: bool | None = None
    quantitative_activity: float | None = None
    quantitative_in_ad: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event prediction.

        Returns:
            JSON-compatible event mapping.
        """
        return {
            "event_id": self.event_id,
            "node_state": "active" if self.qualitative_activity == 1 else "inactive",
            "metadata": to_json_value(self.metadata),
            "qualitative": {
                "activity": to_json_value(self.qualitative_activity),
                "in_ad": self.qualitative_in_ad,
            },
            "quantitative": None
            if self.quantitative_activity is None
            else {
                "activity": to_json_value(self.quantitative_activity),
                "in_ad": self.quantitative_in_ad,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventPrediction:
        """Deserialize an event prediction.

        Args:
            data: Mapping produced by :meth:`to_dict`.

        Returns:
            Reconstructed event prediction.
        """
        qualitative = data.get("qualitative") or {}
        quantitative = data.get("quantitative")
        return cls(
            event_id=str(data["event_id"]),
            metadata=dict(data.get("metadata") or {}),
            qualitative_activity=qualitative.get("activity"),
            qualitative_in_ad=qualitative.get("in_ad"),
            quantitative_activity=None if quantitative is None else quantitative.get("activity"),
            quantitative_in_ad=None if quantitative is None else quantitative.get("in_ad"),
        )


@dataclass(frozen=True)
class SensitiveEvent:
    """The most sensitive activated quantitative endpoint and its decoded value."""

    event_id: str
    value: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize the sensitive event.

        Returns:
            JSON-compatible sensitive-event mapping.
        """
        return {"event_id": self.event_id, "value": to_json_value(self.value)}


@dataclass(frozen=True)
class AOCandidate:
    """Explains whether a single AO can take part in the sensitive-endpoint comparison."""

    event_id: str
    value: float | None
    qualitative_activity: int | None
    quantitative_in_ad: bool | None
    has_quantitative_model: bool
    eligible: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the AO candidate.

        Returns:
            JSON-compatible AO candidate mapping.
        """
        return {
            "event_id": self.event_id,
            "value": to_json_value(self.value),
            "qualitative_activity": to_json_value(self.qualitative_activity),
            "quantitative_in_ad": self.quantitative_in_ad,
            "has_quantitative_model": self.has_quantitative_model,
            "eligible": self.eligible,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AOCandidate:
        """Deserialize an AO candidate.

        Args:
            data: Mapping produced by :meth:`to_dict`.

        Returns:
            Reconstructed AO candidate.
        """
        value = data.get("value")
        return cls(
            event_id=str(data["event_id"]),
            value=None if value is None else float(value),
            qualitative_activity=data.get("qualitative_activity"),
            quantitative_in_ad=data.get("quantitative_in_ad"),
            has_quantitative_model=bool(data.get("has_quantitative_model", False)),
            eligible=bool(data.get("eligible", False)),
            status=str(data.get("status", "unknown")),
        )


@dataclass(frozen=True)
class CausalChainResult:
    """Structured evaluation outcome for one configured AOP causal chain."""

    aop_id: str
    events: tuple[str, ...]
    values: tuple[float | None, ...]
    terminal_event: str
    terminal_type: str | None
    all_active: bool
    all_quantified: bool
    monotonic: bool | None
    all_quantitative_in_ad: bool | None
    valid: bool
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the causal-chain evaluation.

        Returns:
            JSON-compatible causal-chain mapping.
        """
        return {
            "aop_id": self.aop_id,
            "events": list(self.events),
            "values": to_json_value(self.values),
            "terminal_event": self.terminal_event,
            "terminal_type": self.terminal_type,
            "all_active": self.all_active,
            "all_quantified": self.all_quantified,
            "monotonic": self.monotonic,
            "all_quantitative_in_ad": self.all_quantitative_in_ad,
            "valid": self.valid,
            "failure_reasons": list(self.failure_reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CausalChainResult:
        """Deserialize a causal-chain evaluation.

        Args:
            data: Mapping produced by :meth:`to_dict`.

        Returns:
            Reconstructed causal-chain evaluation.
        """
        return cls(
            aop_id=str(data["aop_id"]),
            events=tuple(str(value) for value in data.get("events", [])),
            values=tuple(
                None if value is None else float(value) for value in data.get("values", [])
            ),
            terminal_event=str(data["terminal_event"]),
            terminal_type=data.get("terminal_type"),
            all_active=bool(data.get("all_active", False)),
            all_quantified=bool(data.get("all_quantified", False)),
            monotonic=data.get("monotonic"),
            all_quantitative_in_ad=data.get("all_quantitative_in_ad"),
            valid=bool(data.get("valid", False)),
            failure_reasons=tuple(str(value) for value in data.get("failure_reasons", [])),
        )


@dataclass(frozen=True)
class AOPRelation:
    """Directed AOP relation with activation value and weight of evidence."""

    source: str
    target: str
    value: float | int
    weight_of_evidence: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the AOP relation.

        Returns:
            JSON-compatible relation mapping.
        """
        return {
            "source": self.source,
            "target": self.target,
            "value": to_json_value(self.value),
            "weight_of_evidence": self.weight_of_evidence,
        }


@dataclass(frozen=True)
class PredictionResult:
    """Complete output of a single EDC prediction request."""

    smiles: str
    events: dict[str, EventPrediction]
    tabular_edc_prediction: int
    graph_edc_prediction: int
    qualitative_in_ad: bool
    quantitative_in_ad: bool | None
    sensitive_event: SensitiveEvent | None
    sensitive_paths: tuple[tuple[str, ...], ...]
    aop_relations: tuple[AOPRelation, ...]
    ao_candidates: tuple[AOCandidate, ...] = ()
    causal_chains: tuple[CausalChainResult, ...] = ()
    sensitive_event_causally_validated: bool | None = None
    paths_truncated: bool = False
    model_version: str = "legacy-unversioned"
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    schema_version: int = 2

    @property
    def final_edc_prediction(self) -> int:
        """Combine both model tracks into the overall EDC verdict.

        Returns:
            1 when either the Original (graph) or Extended (tabular)
            track predicts EDC, otherwise 0.
        """
        return int(self.tabular_edc_prediction == 1 or self.graph_edc_prediction == 1)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full result with a stable structure.

        Returns:
            JSON-compatible prediction result mapping.
        """
        return {
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "smiles": self.smiles,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "tabular_edc_prediction": int(self.tabular_edc_prediction),
            "graph_edc_prediction": int(self.graph_edc_prediction),
            "final_edc_prediction": int(self.final_edc_prediction),
            "qualitative_in_ad": self.qualitative_in_ad,
            "quantitative_in_ad": self.quantitative_in_ad,
            "sensitive_event": None
            if self.sensitive_event is None
            else self.sensitive_event.to_dict(),
            "sensitive_paths": [list(path) for path in self.sensitive_paths],
            "ao_candidates": [candidate.to_dict() for candidate in self.ao_candidates],
            "causal_chains": [chain.to_dict() for chain in self.causal_chains],
            "sensitive_event_causally_validated": self.sensitive_event_causally_validated,
            "paths_truncated": self.paths_truncated,
            "events": {key: value.to_dict() for key, value in self.events.items()},
            "aop_relations": [relation.to_dict() for relation in self.aop_relations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictionResult:
        """Deserialize a complete stable-structure result.

        Args:
            data: Mapping produced by :meth:`to_dict`.

        Returns:
            Reconstructed prediction result.
        """
        sensitive_data = data.get("sensitive_event")
        sensitive = None
        if sensitive_data is not None:
            sensitive = SensitiveEvent(
                event_id=str(sensitive_data["event_id"]),
                value=float(sensitive_data["value"]),
            )
        events = {
            event_id: EventPrediction.from_dict(event_data)
            for event_id, event_data in (data.get("events") or {}).items()
        }
        relations = tuple(
            AOPRelation(
                source=str(item["source"]),
                target=str(item["target"]),
                value=item["value"],
                weight_of_evidence=str(item["weight_of_evidence"]),
            )
            for item in data.get("aop_relations", [])
        )
        candidates = tuple(AOCandidate.from_dict(item) for item in data.get("ao_candidates", []))
        causal_chains = tuple(
            CausalChainResult.from_dict(item) for item in data.get("causal_chains", [])
        )
        return cls(
            smiles=str(data["smiles"]),
            events=events,
            tabular_edc_prediction=int(data["tabular_edc_prediction"]),
            graph_edc_prediction=int(data["graph_edc_prediction"]),
            qualitative_in_ad=bool(data["qualitative_in_ad"]),
            quantitative_in_ad=data.get("quantitative_in_ad"),
            sensitive_event=sensitive,
            sensitive_paths=tuple(tuple(path) for path in data.get("sensitive_paths", [])),
            aop_relations=relations,
            ao_candidates=candidates,
            causal_chains=causal_chains,
            sensitive_event_causally_validated=data.get("sensitive_event_causally_validated"),
            paths_truncated=bool(data.get("paths_truncated", False)),
            model_version=str(data.get("model_version", "legacy-unversioned")),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_seconds=data.get("duration_seconds"),
            schema_version=int(data.get("schema_version", 1)),
        )

    def legacy_info(self) -> dict[str, dict[str, Any]]:
        """Convert event outcomes to the historical nested mapping.

        Returns:
            Event metadata with legacy activity and applicability-domain keys.
        """
        info: dict[str, dict[str, Any]] = {}
        for event_id, prediction in self.events.items():
            event = dict(prediction.metadata)
            event["qualitativeActivity"] = prediction.qualitative_activity
            event["qualitativeAD"] = prediction.qualitative_in_ad
            if prediction.quantitative_activity is not None:
                event["quantitativeActivity"] = prediction.quantitative_activity
                event["quantitativeAD"] = prediction.quantitative_in_ad
            info[event_id] = event
        return info

    def to_legacy_tuple(self) -> tuple[Any, ...]:
        """Convert the stable result to the historical nine-item tuple.

        Returns:
            Legacy event info, classifications, relations, applicability
            verdicts, sensitive endpoint value, and paths in original order.
        """
        sensitive_id = None if self.sensitive_event is None else self.sensitive_event.event_id
        sensitive_value = None if self.sensitive_event is None else self.sensitive_event.value
        relations = [
            {
                "source": relation.source,
                "target": relation.target,
                "value": relation.value,
                "WOE": relation.weight_of_evidence,
            }
            for relation in self.aop_relations
        ]
        return (
            self.legacy_info(),
            self.tabular_edc_prediction,
            self.graph_edc_prediction,
            relations,
            self.qualitative_in_ad,
            self.quantitative_in_ad,
            sensitive_id,
            sensitive_value,
            [list(path) for path in self.sensitive_paths],
        )
