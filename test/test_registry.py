"""Functional tests for the endpoint model registry with real sklearn artifacts."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import StandardScaler

from edkg_dl.config import ProjectPaths
from edkg_dl.exceptions import ArtifactMissingError, PredictionError
from edkg_dl.predictors import ModelRegistry


def _install_endpoint(root: Path, event_id: str = "E1") -> None:
    """Create a real endpoint bundle (training CSV plus joblib model)."""
    directory = root / "qualitative_models"
    directory.mkdir(parents=True, exist_ok=True)
    training = pd.DataFrame(
        {"f1": [0.0, 2.0, 0.0, 2.0], "f2": [0.0, 0.0, 2.0, 2.0]},
        index=["s0", "s1", "s2", "s3"],
    )
    training.to_csv(directory / f"{event_id}.csv")
    scaler = StandardScaler().fit(training)
    model = DummyClassifier(strategy="constant", constant=1).fit(
        scaler.transform(training), [1, 1, 1, 1]
    )
    joblib.dump(model, directory / f"{event_id}.pkl")


def test_loads_and_evaluates_endpoint(tmp_path: Path) -> None:
    """A real bundle loads, predicts, and reports applicability."""
    _install_endpoint(tmp_path)
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    features = pd.DataFrame({"f1": [1.0], "f2": [1.0]}, index=["molecule"])
    prediction, in_ad = registry.predict("qualitative", "E1", features)
    assert int(prediction) == 1
    assert in_ad is True


def test_endpoint_bundle_is_cached(tmp_path: Path) -> None:
    """Repeated access reuses the loaded bundle."""
    _install_endpoint(tmp_path)
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    features = pd.DataFrame({"f1": [1.0], "f2": [1.0]}, index=["molecule"])
    registry.predict("qualitative", "E1", features)
    assert registry.cached_model_count == 1
    registry.predict("qualitative", "E1", features)
    assert registry.cached_model_count == 1


def test_missing_artifacts_raise(tmp_path: Path) -> None:
    """Absent endpoint files raise ArtifactMissingError."""
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    with pytest.raises(ArtifactMissingError, match="Missing endpoint artifacts"):
        registry.get("edc", "edc")


def test_unsupported_kind_raises(tmp_path: Path) -> None:
    """Unknown model kinds are rejected."""
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    with pytest.raises(ValueError, match="Unsupported model kind"):
        registry.get("bogus", "E1")


def test_missing_feature_column_raises(tmp_path: Path) -> None:
    """Feature frames missing model columns raise PredictionError."""
    _install_endpoint(tmp_path)
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    features = pd.DataFrame({"f1": [1.0]}, index=["molecule"])
    with pytest.raises(PredictionError, match="missing 1 features"):
        registry.predict("qualitative", "E1", features)


def test_empty_training_matrix_raises(tmp_path: Path) -> None:
    """An empty training CSV fails to load."""
    directory = tmp_path / "qualitative_models"
    directory.mkdir(parents=True)
    pd.DataFrame(index=["s0"]).to_csv(directory / "E1.csv")
    joblib.dump(DummyClassifier(), directory / "E1.pkl")
    registry = ModelRegistry(ProjectPaths.resolve(tmp_path))
    with pytest.raises(PredictionError, match="training matrix is empty"):
        registry.get("qualitative", "E1")
