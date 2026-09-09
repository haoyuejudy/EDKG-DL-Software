"""Optional FastAPI service layer for high-throughput callers."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from . import __version__
from .api import Predictor
from .exceptions import EdkgDlError


Smiles = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PredictionRequest(BaseModel):
    """Single-SMILES prediction request."""

    smiles: Smiles


class BatchPredictionRequest(BaseModel):
    """Bounded batch SMILES prediction request."""

    smiles: list[Smiles] = Field(min_length=1, max_length=100)
    max_workers: int = Field(default=1, ge=1, le=8)


def create_app(
    *,
    predictor: Predictor | None = None,
    asset_dir: str | Path | None = None,
    max_batch_size: int = 100,
) -> FastAPI:
    """Create a FastAPI application that reuses one predictor.

    Args:
        predictor: Predictor injected for tests or embedded deployments.
        asset_dir: External asset directory used when no predictor is injected.
        max_batch_size: Maximum batch size accepted by the service, capped
            at 100 by the request model.

    Returns:
        Application configured with health, readiness, model-info, and
        single/batch prediction endpoints.

    Raises:
        ValueError: Raised when the batch cap is not between 1 and 100.
        EdkgDlError: Raised when no predictor is injected and runtime assets
            are unavailable.
    """
    if not 1 <= max_batch_size <= 100:
        raise ValueError("max_batch_size must be between 1 and 100")
    active_predictor = predictor or Predictor.from_assets(asset_dir)
    application = FastAPI(
        title="EDKG-DL API",
        version=__version__,
        description="Serves qualitative, quantitative, sensitive-AO, and AOP causal-chain predictions.",
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Return liveness status that does not depend on model inference."""
        return {"status": "ok"}

    @application.get("/ready")
    def ready() -> dict[str, Any]:
        """Return configuration readiness and the cached model count."""
        registry = active_predictor.pipeline.model_registry
        return {
            "status": "ready",
            "model_version": active_predictor.pipeline.model_version,
            "cached_model_count": getattr(registry, "cached_model_count", None),
        }

    @application.get("/v1/model-info")
    def model_info() -> dict[str, Any]:
        """Return event scale and the current causal-chain policy."""
        pipeline = active_predictor.pipeline
        settings = pipeline.settings
        policy = pipeline.causal_chain_policy
        return {
            "model_version": pipeline.model_version,
            "event_count": len(settings.event_info),
            "ao_count": sum(
                metadata.get("Type") == "AO" for metadata in settings.event_info.values()
            ),
            "quantitative_event_count": len(settings.quantitative_indexes),
            "causal_chain_count": len(settings.aop_to_events),
            "causal_chain_policy": {
                "monotonicity": policy.monotonicity,
                "require_terminal_ao": policy.require_terminal_ao,
                "require_all_active": policy.require_all_active,
                "require_quantitative_in_ad": policy.require_quantitative_in_ad,
                "allow_single_event": policy.allow_single_event,
            },
        }

    @application.post("/v1/predictions")
    def predict(request: PredictionRequest) -> dict[str, Any]:
        """Run the full prediction for a single molecule."""
        try:
            return active_predictor.predict(request.smiles).to_dict()
        except EdkgDlError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.__class__.__name__, "message": str(exc)},
            ) from exc

    @application.post("/v1/predictions/batch")
    def predict_batch(request: BatchPredictionRequest) -> dict[str, Any]:
        """Run an order-preserving batch prediction with partial-failure tolerance."""
        if len(request.smiles) > max_batch_size:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "BatchTooLarge",
                    "message": f"batch size exceeds limit of {max_batch_size}",
                },
            )
        return active_predictor.predict_batch(
            request.smiles,
            max_items=max_batch_size,
            max_workers=request.max_workers,
        ).to_dict()

    return application


def run() -> None:
    """Start the Uvicorn dev/single-process service."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(
        prog="edkg-dl-api",
        description=f"EDKG-DL v{__version__}: serve prediction HTTP endpoints.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s (EDKG-DL) v{__version__}",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="bind port (default: 8000)",
    )
    arguments = parser.parse_args()
    uvicorn.run(
        "edkg_dl.http_api:create_app",
        factory=True,
        host=arguments.host,
        port=arguments.port,
    )
