"""Application-layer orchestration for a single prediction request."""

from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any

from .config import ProjectPaths, Settings
from .domain import (
    CausalChainPolicy,
    aggregate_applicability,
    evaluate_causal_chains,
    find_sensitive_paths,
    select_sensitive_ao,
)
from .features import PadelFeatureExtractor
from .predictors.registry import ModelRegistry
from .schemas import EventPrediction, PredictionResult


class PredictionPipeline:
    """Coordinates feature extraction, endpoint inference, and path analysis."""

    def __init__(
        self,
        *,
        settings: Settings,
        feature_extractor: Any,
        model_registry: Any,
        graph_predictor: Any,
        model_version: str = "legacy-unversioned",
        max_paths: int = 1_000,
        max_path_length: int | None = None,
        causal_chain_policy: CausalChainPolicy | None = None,
    ) -> None:
        """Initialize the prediction pipeline with injectable components.

        Args:
            settings: Validated event and graph settings.
            feature_extractor: Component converting SMILES to feature rows.
            model_registry: Endpoint model cache and inference adapter.
            graph_predictor: Graph neural network inference adapter.
            model_version: Version label written to prediction results.
            max_paths: Maximum number of sensitive paths to return.
            max_path_length: Maximum number of edges allowed per path;
                unlimited when ``None``.
            causal_chain_policy: Causal-chain validity policy; defaults to
                the strict-increasing rule when ``None``.
        """
        self.settings = settings
        self.feature_extractor = feature_extractor
        self.model_registry = model_registry
        self.graph_predictor = graph_predictor
        self.model_version = model_version
        self.max_paths = max_paths
        self.max_path_length = max_path_length
        self.causal_chain_policy = causal_chain_policy or CausalChainPolicy()

    @classmethod
    def from_paths(
        cls,
        paths: ProjectPaths,
        *,
        max_paths: int = 1_000,
        max_path_length: int | None = None,
        causal_chain_policy: CausalChainPolicy | None = None,
    ) -> PredictionPipeline:
        """Build the production prediction pipeline from the asset layout.

        Args:
            paths: Resolved external asset paths.
            max_paths: Maximum number of sensitive paths to return.
            max_path_length: Maximum number of edges allowed per path;
                unlimited when ``None``.
            causal_chain_policy: Causal-chain validity policy; defaults to
                the strict-increasing rule when ``None``.

        Returns:
            Fully configured prediction pipeline.

        Raises:
            EdkgDlError: Raised when configuration or required artifacts are invalid.
        """
        paths.validate_runtime_assets()
        model_version = paths.verify_manifest()
        settings = Settings.load(paths.settings)
        paths.validate_endpoint_assets(settings)
        from .predictors.gcn import GCNPredictor

        return cls(
            settings=settings,
            feature_extractor=PadelFeatureExtractor(paths.padel_descriptors),
            model_registry=ModelRegistry(paths),
            graph_predictor=GCNPredictor(settings, paths.gcn_model),
            model_version=model_version,
            max_paths=max_paths,
            max_path_length=max_path_length,
            causal_chain_policy=causal_chain_policy,
        )

    def predict(self, smiles: str) -> PredictionResult:
        """Extract features and predict a single molecule.

        Args:
            smiles: SMILES string describing a single molecule.

        Returns:
            Complete structured prediction result.
        """
        result, _ = self.predict_with_features(smiles)
        return result

    def predict_with_features(self, smiles: str) -> tuple[PredictionResult, Any]:
        """Predict a single molecule and also return its feature row.

        Args:
            smiles: SMILES string describing a single molecule.

        Returns:
            Two-tuple of prediction result and feature DataFrame.
        """
        started = datetime.now(timezone.utc)
        start_clock = time.perf_counter()
        features = self.feature_extractor.extract(smiles)
        result = self._predict_features(
            smiles,
            features,
            started=started,
            start_clock=start_clock,
        )
        return result, features

    def predict_features(self, smiles: str, features: Any) -> PredictionResult:
        """Run prediction from a precomputed single-row feature frame.

        Args:
            smiles: SMILES label written to the result.
            features: Single-row DataFrame containing PaDEL features.

        Returns:
            Complete structured prediction result.
        """
        return self._predict_features(
            smiles,
            features,
            started=datetime.now(timezone.utc),
            start_clock=time.perf_counter(),
        )

    def _predict_features(
        self,
        smiles: str,
        features: Any,
        *,
        started: datetime,
        start_clock: float,
    ) -> PredictionResult:
        """Run model inference on an extracted feature row.

        Args:
            smiles: SMILES label written to the result.
            features: Single-row DataFrame containing PaDEL features.
            started: UTC start time of the full request.
            start_clock: Monotonic clock origin used for duration.

        Returns:
            Complete structured prediction result.
        """
        event_predictions: dict[str, EventPrediction] = {}
        qualitative_results: dict[str, int] = {}
        qualitative_ad_values: list[bool] = []
        quantitative_ad_values: list[bool] = []

        for index in sorted(self.settings.index_to_event):
            event_id = self.settings.index_to_event[index]
            qualitative_raw, qualitative_in_ad = self.model_registry.predict(
                "qualitative", event_id, features
            )
            qualitative_activity = int(qualitative_raw)
            qualitative_results[event_id] = qualitative_activity
            qualitative_ad_values.append(bool(qualitative_in_ad))

            quantitative_activity: float | None = None
            quantitative_in_ad: bool | None = None
            if qualitative_activity == 1 and index in self.settings.quantitative_indexes:
                quantitative_raw, quantitative_in_ad = self.model_registry.predict(
                    "quantitative", event_id, features
                )
                quantitative_activity = 10 ** float(quantitative_raw)
                quantitative_ad_values.append(bool(quantitative_in_ad))

            event_predictions[event_id] = EventPrediction(
                event_id=event_id,
                metadata=copy.deepcopy(self.settings.event_info[event_id]),
                qualitative_activity=qualitative_activity,
                qualitative_in_ad=bool(qualitative_in_ad),
                quantitative_activity=quantitative_activity,
                quantitative_in_ad=quantitative_in_ad,
            )

        quantitative_event_ids = {
            self.settings.index_to_event[index] for index in self.settings.quantitative_indexes
        }
        sensitivity = select_sensitive_ao(
            event_predictions=event_predictions,
            quantitative_event_ids=quantitative_event_ids,
        )
        sensitive = sensitivity.selected
        causal_chains = evaluate_causal_chains(
            aop_to_events=self.settings.aop_to_events,
            event_predictions=event_predictions,
            policy=self.causal_chain_policy,
        )
        causally_validated = (
            None
            if sensitive is None
            else any(
                chain.valid and chain.terminal_event == sensitive.event_id
                for chain in causal_chains
            )
        )

        tabular_raw, _ = self.model_registry.predict("edc", "edc", features)
        graph_prediction, relations = self.graph_predictor.predict(qualitative_results)
        active_events = {event_id for event_id, value in qualitative_results.items() if value == 1}
        path_result = find_sensitive_paths(
            index_to_event=self.settings.index_to_event,
            edges=self.settings.edges,
            active_events=active_events,
            sensitive_event=None if sensitive is None else sensitive.event_id,
            max_paths=self.max_paths,
            max_length=self.max_path_length,
        )
        finished = datetime.now(timezone.utc)
        return PredictionResult(
            smiles=smiles.strip(),
            events=event_predictions,
            tabular_edc_prediction=int(tabular_raw),
            graph_edc_prediction=int(graph_prediction),
            qualitative_in_ad=bool(aggregate_applicability(qualitative_ad_values)),
            quantitative_in_ad=aggregate_applicability(quantitative_ad_values),
            sensitive_event=sensitive,
            sensitive_paths=path_result.paths,
            aop_relations=relations,
            ao_candidates=sensitivity.candidates,
            causal_chains=causal_chains,
            sensitive_event_causally_validated=causally_validated,
            paths_truncated=path_result.truncated,
            model_version=self.model_version,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=time.perf_counter() - start_clock,
        )
