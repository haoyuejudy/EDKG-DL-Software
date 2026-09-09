"""Applicability-domain computations preserving legacy semantics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApplicabilityDomain:
    """Euclidean-distance applicability domain for a single endpoint model."""

    feature_names: tuple[str, ...]
    center: tuple[float, ...]
    cutoff: float

    @classmethod
    def from_training_frame(cls, training: Any) -> ApplicabilityDomain:
        """Build an applicability domain from the training matrix.

        Args:
            training: DataFrame with endpoint-model features as columns.

        Returns:
            Applicability domain with the centroid and the maximum
            training-sample distance.
        """
        import numpy as np

        values = training.to_numpy(dtype=float, copy=False)
        center = values.mean(axis=0)
        distances = np.linalg.norm(values - center, axis=1)
        return cls(
            feature_names=tuple(str(column) for column in training.columns),
            center=tuple(float(value) for value in center),
            cutoff=float(distances.max()),
        )

    def contains(self, features: Any) -> bool:
        """Check whether a single feature row lies inside the domain.

        Args:
            features: DataFrame with exactly one molecule and all required
                feature columns.

        Returns:
            ``True`` when the sample distance does not exceed the cutoff.

        Raises:
            ValueError: Raised when the feature frame does not contain
                exactly one row.
            KeyError: Raised when a required feature column is missing.
        """
        import numpy as np

        selected = features.loc[:, list(self.feature_names)].to_numpy(dtype=float, copy=False)
        if selected.shape[0] != 1:
            raise ValueError("ApplicabilityDomain.contains expects exactly one sample")
        distance = float(np.linalg.norm(selected[0] - np.asarray(self.center)))
        return distance <= self.cutoff


def aggregate_applicability(values: Iterable[bool]) -> bool | None:
    """Aggregate per-endpoint applicability results with the legacy majority threshold.

    Args:
        values: Applicability verdicts from each endpoint.

    Returns:
        Majority vote result; ties count as inside the domain, and ``None``
        is returned when no endpoint model ran.
    """
    items = tuple(bool(value) for value in values)
    if not items:
        return None
    return sum(items) >= 0.5 * len(items)
