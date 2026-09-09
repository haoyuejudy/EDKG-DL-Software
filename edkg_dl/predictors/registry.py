"""In-process lazy cache for legacy endpoint artifacts."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..config import ProjectPaths
from ..domain.applicability import ApplicabilityDomain
from ..exceptions import ArtifactMissingError, PredictionError


ModelKind = Literal["qualitative", "quantitative", "edc"]


@dataclass(frozen=True)
class EndpointBundle:
    """Cached training metadata, scaler, predictor, and applicability domain."""

    kind: ModelKind
    event_id: str
    training_path: Path
    model_path: Path
    feature_names: tuple[str, ...]
    scaler: Any
    predictor: Any
    applicability: ApplicabilityDomain

    def evaluate(self, features: Any) -> tuple[Any, bool]:
        """Evaluate a single endpoint model together with its applicability domain.

        Args:
            features: Single-row DataFrame containing PaDEL features.

        Returns:
            Two-tuple of the raw model prediction and the applicability verdict.

        Raises:
            PredictionError: Raised when a required feature is missing or
                inference fails.
        """
        try:
            selected = features.loc[:, list(self.feature_names)]
        except KeyError as exc:
            missing = sorted(set(self.feature_names) - set(features.columns))
            raise PredictionError(
                f"PaDEL output is missing {len(missing)} features for {self.event_id}: "
                f"{missing[:8]}"
            ) from exc
        try:
            import pandas as pd

            scaled = self.scaler.transform(selected)
            # Legacy estimators were trained with named columns. Recreate the
            # DataFrame after scaling so feature-name validation still works.
            scaled_frame = pd.DataFrame(
                scaled,
                columns=list(self.feature_names),
                index=selected.index,
            )
            prediction = self.predictor.predict(scaled_frame)[0]
            in_domain = self.applicability.contains(features)
        except Exception as exc:
            raise PredictionError(f"{self.kind} model failed for {self.event_id}: {exc}") from exc
        return prediction, in_domain


class ModelRegistry:
    """Loads each CSV, scaler, and model once and reuses them across predictions."""

    def __init__(self, paths: ProjectPaths) -> None:
        """Initialize an empty thread-safe artifact cache.

        Args:
            paths: Resolved external asset paths.
        """
        self.paths = paths
        self._cache: dict[tuple[ModelKind, str], EndpointBundle] = {}
        self._lock = threading.RLock()

    @property
    def cached_model_count(self) -> int:
        """Return the number of endpoint bundles loaded in this process."""
        return len(self._cache)

    def get(self, kind: ModelKind, event_id: str) -> EndpointBundle:
        """Return a cached endpoint bundle, loading it from disk on first access.

        Args:
            kind: Qualitative, quantitative, or tabular EDC model kind.
            event_id: Biological event identifier, or ``edc``.

        Returns:
            Reusable endpoint bundle.

        Raises:
            ArtifactMissingError: Raised when endpoint files are missing.
            PredictionError: Raised when an endpoint file cannot be loaded.
        """
        key = (kind, event_id)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            bundle = self._load(kind, event_id)
            self._cache[key] = bundle
            return bundle

    def predict(self, kind: ModelKind, event_id: str, features: Any) -> tuple[Any, bool]:
        """Evaluate a single endpoint through the cached registry.

        Args:
            kind: Qualitative, quantitative, or tabular EDC model kind.
            event_id: Biological event identifier, or ``edc``.
            features: Single-row DataFrame containing PaDEL features.

        Returns:
            Two-tuple of the raw prediction and the applicability verdict.
        """
        return self.get(kind, event_id).evaluate(features)

    def _load(self, kind: ModelKind, event_id: str) -> EndpointBundle:
        """Load and prepare a single endpoint bundle from disk.

        Args:
            kind: Model kind to load.
            event_id: Biological event identifier, or ``edc``.

        Returns:
            Prepared endpoint bundle.

        Raises:
            ArtifactMissingError: Raised when the training or model file is missing.
            PredictionError: Raised when deserialization or preprocessing fails.
        """
        training_path, model_path = self._paths_for(kind, event_id)
        missing = [path for path in (training_path, model_path) if not path.is_file()]
        if missing:
            raise ArtifactMissingError(
                "Missing endpoint artifacts: " + ", ".join(str(path) for path in missing)
            )
        try:
            import joblib
            import pandas as pd
            from sklearn.preprocessing import StandardScaler

            training = pd.read_csv(training_path, index_col=0)
            if training.empty:
                raise ValueError("training matrix is empty")
            scaler = StandardScaler().fit(training)
            predictor = joblib.load(model_path)
            applicability = ApplicabilityDomain.from_training_frame(training)
        except Exception as exc:
            raise PredictionError(f"Failed to load {kind} artifacts for {event_id}: {exc}") from exc
        return EndpointBundle(
            kind=kind,
            event_id=event_id,
            training_path=training_path,
            model_path=model_path,
            feature_names=tuple(str(column) for column in training.columns),
            scaler=scaler,
            predictor=predictor,
            applicability=applicability,
        )

    def _paths_for(self, kind: ModelKind, event_id: str) -> tuple[Path, Path]:
        """Resolve the training and model files for an endpoint.

        Args:
            kind: Model kind to resolve.
            event_id: Biological event identifier, or ``edc``.

        Returns:
            Two-tuple of the training CSV and serialized model paths.

        Raises:
            ValueError: Raised when the model kind is unsupported.
        """
        if kind == "qualitative":
            directory = self.paths.qualitative_models
            return directory / f"{event_id}.csv", directory / f"{event_id}.pkl"
        if kind == "quantitative":
            directory = self.paths.quantitative_models
            return directory / f"{event_id}.csv", directory / f"{event_id}.pkl"
        if kind == "edc":
            return self.paths.edc_training, self.paths.edc_model
        raise ValueError(f"Unsupported model kind: {kind}")
