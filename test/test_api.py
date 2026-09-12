"""Tests for the stable public Python API with a stubbed pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import StubPipeline

from edkg_dl import BatchPredictionItem, BatchPredictionResult, Predictor, api, hub
from edkg_dl.exceptions import EdkgDlError, InvalidSmilesError
from edkg_dl.schemas import PredictionResult


class TestBatchContracts:
    """Batch result serialization contracts."""

    def test_item_success_dict(self, result: PredictionResult) -> None:
        """A successful item reports ``ok`` with its result."""
        item = BatchPredictionItem(index=1, smiles="CCO", result=result)
        payload = item.to_dict()
        assert payload["index"] == 1
        assert payload["ok"] is True
        assert payload["error"] is None
        assert payload["result"]["smiles"] == "CCO"

    def test_item_error_dict(self) -> None:
        """A failed item reports a structured error."""
        item = BatchPredictionItem(
            index=0, smiles="", error_code="InvalidSmilesError", error_message="bad"
        )
        payload = item.to_dict()
        assert payload["ok"] is False
        assert payload["result"] is None
        assert payload["error"] == {"code": "InvalidSmilesError", "message": "bad"}

    def test_result_counts_and_dict(self, result: PredictionResult) -> None:
        """Counts summarize per-item outcomes in input order."""
        failed = BatchPredictionItem(index=1, smiles="x", error_code="Boom", error_message="bad")
        batch = BatchPredictionResult(
            (BatchPredictionItem(index=0, smiles="CCO", result=result), failed)
        )
        assert batch.succeeded == 1
        assert batch.failed == 1
        payload = batch.to_dict()
        assert payload["total"] == 2
        assert payload["succeeded"] == 1
        assert payload["failed"] == 1
        assert [item["index"] for item in payload["items"]] == [0, 1]


class TestPredictBatchBounds:
    """Batch and concurrency bound validation."""

    def test_max_items_must_be_positive(self, stub_pipeline: StubPipeline) -> None:
        """A non-positive batch cap is rejected."""
        with pytest.raises(ValueError, match="max_items"):
            Predictor(pipeline=stub_pipeline).predict_batch([], max_items=0)

    def test_batch_size_exceeds_limit(self, stub_pipeline: StubPipeline) -> None:
        """Inputs beyond the cap are rejected."""
        with pytest.raises(ValueError, match="exceeds limit"):
            Predictor(pipeline=stub_pipeline).predict_batch(["A", "B"], max_items=1)

    def test_max_workers_must_be_positive(self, stub_pipeline: StubPipeline) -> None:
        """A non-positive worker count is rejected."""
        with pytest.raises(ValueError, match="max_workers"):
            Predictor(pipeline=stub_pipeline).predict_batch(["A"], max_workers=0)


class TestPredictBatchExecution:
    """Batch execution semantics with the stub pipeline."""

    def test_failure_isolation(self) -> None:
        """Handled and unexpected errors become per-item outcomes."""
        errors: dict[str, Exception] = {
            "bad": InvalidSmilesError("empty SMILES"),
            "boom": RuntimeError("kaboom"),
        }
        predictor = Predictor(pipeline=StubPipeline(errors=errors))
        batch = predictor.predict_batch(["ok", "bad", "boom"], max_items=3)
        assert [item.smiles for item in batch.items] == ["ok", "bad", "boom"]
        assert batch.succeeded == 1
        assert batch.failed == 2
        assert [item.error_code for item in batch.items] == [
            None,
            "InvalidSmilesError",
            "InternalPredictionError",
        ]
        payload = batch.to_dict()
        assert payload["items"][1]["error"]["code"] == "InvalidSmilesError"

    def test_threaded_execution_preserves_order(self, stub_pipeline: StubPipeline) -> None:
        """Multithreaded batches keep input order and succeed."""
        predictor = Predictor(pipeline=stub_pipeline)
        batch = predictor.predict_batch(["A", "B", "C"], max_items=3, max_workers=2)
        assert [item.smiles for item in batch.items] == ["A", "B", "C"]
        assert batch.succeeded == 3

    def test_empty_batch(self, stub_pipeline: StubPipeline) -> None:
        """An empty batch produces an empty result."""
        batch = Predictor(pipeline=stub_pipeline).predict_batch([])
        assert batch.items == ()
        assert batch.succeeded == 0


class TestPredictorDelegation:
    """Single and multi prediction pass-through."""

    def test_predict_returns_stub_result(self, stub_pipeline: StubPipeline) -> None:
        """Predict forwards to the pipeline."""
        result = Predictor(pipeline=stub_pipeline).predict("X")
        assert result.smiles == "X"

    def test_predict_many_preserves_order(self, stub_pipeline: StubPipeline) -> None:
        """predict_many keeps input order."""
        results = Predictor(pipeline=stub_pipeline).predict_many(["X", "Y"])
        assert [result.smiles for result in results] == ["X", "Y"]


class TestFromAssetsRevisionGuard:
    """Automatic re-download when the cached revision no longer matches."""

    def _prepare(self, tmp_path: Path, revision: str | None) -> Path:
        """Create an asset root with a settings file and optional marker."""
        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        if revision is not None:
            (tmp_path / hub.REVISION_MARKER).write_text(f"{revision}\n", encoding="utf-8")
        return tmp_path

    def test_matching_revision_skips_download(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cache recorded at the pinned revision never triggers a download."""
        asset_dir = self._prepare(tmp_path, hub.REVISION)

        def _forbidden(*_args: object, **_kwargs: object) -> Path:
            raise AssertionError("download_assets must not be called")

        monkeypatch.setattr(api, "download_assets", _forbidden)
        with pytest.raises(EdkgDlError, match="Missing runtime assets"):
            Predictor.from_assets(asset_dir)

    @pytest.mark.parametrize("revision", [None, "outdated-revision"])
    def test_stale_revision_triggers_download(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revision: str | None
    ) -> None:
        """A missing or outdated marker re-downloads before loading assets."""
        asset_dir = self._prepare(tmp_path, revision)
        calls: list[Path] = []
        monkeypatch.setattr(api, "download_assets", lambda root: calls.append(Path(root)) or root)
        with pytest.raises(EdkgDlError, match="Missing runtime assets"):
            Predictor.from_assets(asset_dir)
        assert calls == [asset_dir]
