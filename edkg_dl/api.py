"""Stable public Python API."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ProjectPaths
from .domain import CausalChainPolicy
from .exceptions import EdkgDlError
from .hub import download_assets
from .pipeline import PredictionPipeline
from .schemas import PredictionResult


@dataclass(frozen=True)
class BatchPredictionItem:
    """Success or error outcome for one input in a batch request."""

    index: int
    smiles: str
    result: PredictionResult | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize a single batch outcome.

        Returns:
            JSON-compatible batch outcome mapping.
        """
        return {
            "index": self.index,
            "smiles": self.smiles,
            "ok": self.result is not None,
            "result": None if self.result is None else self.result.to_dict(),
            "error": None
            if self.error_code is None
            else {"code": self.error_code, "message": self.error_message},
        }


@dataclass(frozen=True)
class BatchPredictionResult:
    """Batch prediction result that preserves input order and tolerates partial failures."""

    items: tuple[BatchPredictionItem, ...]

    @property
    def succeeded(self) -> int:
        """Return the number of successfully predicted inputs."""
        return sum(item.result is not None for item in self.items)

    @property
    def failed(self) -> int:
        """Return the number of failed inputs."""
        return len(self.items) - self.succeeded

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete batch result.

        Returns:
            JSON-compatible mapping with counts and per-item outcomes.
        """
        return {
            "total": len(self.items),
            "succeeded": self.succeeded,
            "failed": self.failed,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class Predictor:
    """Reusable prediction facade that caches loaded endpoint models."""

    pipeline: PredictionPipeline

    @classmethod
    def from_assets(
        cls,
        asset_dir: str | Path | None = None,
        *,
        max_paths: int = 1_000,
        max_path_length: int | None = None,
        causal_chain_policy: CausalChainPolicy | None = None,
    ) -> Predictor:
        """Create a reusable predictor from an external asset directory.

        When the resolved asset directory does not contain ``settings.json``,
        the assets are downloaded automatically from the Hugging Face Hub
        into that directory (the per-user cache directory by default).

        Args:
            asset_dir: Directory containing settings and model artifacts.
            max_paths: Maximum number of sensitive paths to return.
            max_path_length: Maximum number of edges allowed per path;
                unlimited when ``None``.
            causal_chain_policy: Causal-chain validity evaluation policy.

        Returns:
            Predictor with a reusable pipeline and cached models.

        Raises:
            EdkgDlError: Raised when configuration or required assets are invalid,
                or when a required automatic download fails.
        """
        paths = ProjectPaths.resolve(asset_dir)
        if not paths.settings.is_file():
            paths = ProjectPaths.resolve(download_assets(paths.asset_root))
        pipeline = PredictionPipeline.from_paths(
            paths,
            max_paths=max_paths,
            max_path_length=max_path_length,
            causal_chain_policy=causal_chain_policy,
        )
        return cls(pipeline)

    def predict(self, smiles: str) -> PredictionResult:
        """Predict a single molecule.

        Args:
            smiles: SMILES string describing a single molecule.

        Returns:
            Complete structured prediction result.
        """
        return self.pipeline.predict(smiles)

    def predict_many(self, smiles_values: Iterable[str]) -> list[PredictionResult]:
        """Predict multiple molecules while reusing loaded artifacts.

        Args:
            smiles_values: Iterable of SMILES strings.

        Returns:
            Prediction results in input order.
        """
        return [self.predict(smiles) for smiles in smiles_values]

    def predict_batch(
        self,
        smiles_values: Iterable[str],
        *,
        max_items: int = 100,
        max_workers: int = 1,
    ) -> BatchPredictionResult:
        """Run a bounded batch prediction with per-item failure isolation.

        Args:
            smiles_values: Iterable of SMILES strings.
            max_items: Maximum number of inputs allowed in one batch.
            max_workers: Number of in-process concurrent worker threads.

        Returns:
            Per-item success or failure outcomes in input order.

        Raises:
            ValueError: Raised when batch or concurrency bounds are invalid.
        """
        values = list(smiles_values)
        if max_items < 1:
            raise ValueError("max_items must be at least 1")
        if len(values) > max_items:
            raise ValueError(f"batch size exceeds limit of {max_items}")
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        if max_workers == 1:
            items = tuple(
                self._predict_batch_item(index, smiles) for index, smiles in enumerate(values)
            )
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                items = tuple(
                    executor.map(
                        lambda indexed: self._predict_batch_item(*indexed),
                        enumerate(values),
                    )
                )
        return BatchPredictionResult(items)

    def _predict_batch_item(self, index: int, smiles: str) -> BatchPredictionItem:
        """Catch prediction exceptions for one input and convert to a batch outcome.

        Args:
            index: Zero-based index of the input within the batch.
            smiles: SMILES to predict.

        Returns:
            Single success outcome or structured error.
        """
        try:
            return BatchPredictionItem(index=index, smiles=smiles, result=self.predict(smiles))
        except EdkgDlError as exc:
            return BatchPredictionItem(
                index=index,
                smiles=smiles,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
        except Exception:  # noqa: BLE001 - batch isolation is an API guarantee.
            return BatchPredictionItem(
                index=index,
                smiles=smiles,
                error_code="InternalPredictionError",
                error_message="unexpected prediction failure",
            )
