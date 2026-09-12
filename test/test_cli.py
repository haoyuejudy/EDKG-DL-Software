"""Tests for the command-line interface that avoid network and model assets."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from edkg_dl import cli, hub


def _empty_asset_root(tmp_path: Path) -> Path:
    """Create an asset root marked as cached at the current revision."""
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "settings.json").write_text("{}", encoding="utf-8")
    (asset_dir / hub.REVISION_MARKER).write_text(f"{hub.REVISION}\n", encoding="utf-8")
    return asset_dir


class TestReadSmilesFile:
    """SMILES input parsing."""

    def test_filters_blank_lines_and_comments(self, tmp_path: Path) -> None:
        """Blank lines and ``#`` comments are dropped, others stripped."""
        path = tmp_path / "input.txt"
        path.write_text("CCO\n\n   # a note\n   CCC   \n", encoding="utf-8")
        assert cli.read_smiles_file(path) == ["CCO", "CCC"]


class TestParserValidation:
    """Argument validation that exits before any asset access."""

    def test_missing_smiles_positional(self) -> None:
        """The SMILES positional argument is required."""
        with pytest.raises(SystemExit) as excinfo:
            cli.main([])
        assert excinfo.value.code == 2

    def test_ad_plots_requires_output(self) -> None:
        """--ad-plots without --output is rejected."""
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--ad-plots", "CCO"])
        assert excinfo.value.code == 2

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_max_paths_must_be_positive(self, value: str) -> None:
        """--max-paths below one is rejected."""
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--max-paths", value, "CCO"])
        assert excinfo.value.code == 2

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_max_path_length_must_be_positive(self, value: str) -> None:
        """--max-path-length below one is rejected."""
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--max-path-length", value, "CCO"])
        assert excinfo.value.code == 2

    def test_batch_max_workers_bounds(self, tmp_path: Path) -> None:
        """Batch concurrency is bounded to 1-8."""
        path = tmp_path / "input.txt"
        path.write_text("CCO\n", encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["batch", "--max-workers", "0", str(path)])
        assert excinfo.value.code == 2
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["batch", "--max-workers", "9", str(path)])
        assert excinfo.value.code == 2

    def test_batch_max_paths_must_be_positive(self, tmp_path: Path) -> None:
        """Batch --max-paths below one is rejected."""
        path = tmp_path / "input.txt"
        path.write_text("CCO\n", encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["batch", "--max-paths", "0", str(path)])
        assert excinfo.value.code == 2


class TestMainErrorPaths:
    """Handled error paths that return exit code 2."""

    def test_single_prediction_missing_assets(
        self, tmp_path: Path, monkeypatch: Any, capsys: Any
    ) -> None:
        """Missing runtime assets produce a handled error."""
        monkeypatch.delenv("EDKG_DL_ASSET_DIR", raising=False)
        asset_dir = _empty_asset_root(tmp_path)
        code = cli.main(["--asset-dir", str(asset_dir), "CCO"])
        assert code == 2
        assert "Missing runtime assets" in capsys.readouterr().err

    def test_batch_missing_input_file(self, tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
        """A missing batch input file produces a handled error."""
        monkeypatch.delenv("EDKG_DL_ASSET_DIR", raising=False)
        code = cli.main(["batch", str(tmp_path / "missing.txt")])
        assert code == 2
        assert capsys.readouterr().err.startswith("error:")

    def test_batch_without_smiles_entries(self, tmp_path: Path, capsys: Any) -> None:
        """An input file without SMILES entries is rejected."""
        path = tmp_path / "empty.txt"
        path.write_text("# only a comment\n\n", encoding="utf-8")
        code = cli.main(["batch", str(path)])
        assert code == 2
        assert "No SMILES found" in capsys.readouterr().err

    def test_batch_missing_assets(self, tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
        """Batch prediction reports missing runtime assets."""
        monkeypatch.delenv("EDKG_DL_ASSET_DIR", raising=False)
        asset_dir = _empty_asset_root(tmp_path)
        path = tmp_path / "input.txt"
        path.write_text("CCO\n", encoding="utf-8")
        code = cli.main(["batch", "--asset-dir", str(asset_dir), str(path)])
        assert code == 2
        assert "Missing runtime assets" in capsys.readouterr().err

    def test_download_offline_failure(self, tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
        """A download without network access produces a handled error."""
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        code = cli.main(
            [
                "download",
                "--asset-dir",
                str(tmp_path / "downloaded"),
                "--repo-id",
                "edkg-dl-tests/nonexistent",
            ]
        )
        assert code == 2
        assert "error:" in capsys.readouterr().err


class TestBatchReports:
    """Per-molecule report export for the batch command."""

    @staticmethod
    def _install_stub_predictor(monkeypatch: Any, make_result: Any) -> None:
        """Replace the CLI predictor with one failing on the SMILES ``BAD``."""
        from edkg_dl.api import BatchPredictionItem, BatchPredictionResult

        class StubPredictor:
            @classmethod
            def from_assets(cls, *_args: Any, **_kwargs: Any) -> StubPredictor:
                return cls()

            def predict_batch(self, smiles_values: list[str], **_kwargs: Any) -> Any:
                items = tuple(
                    BatchPredictionItem(index=index, smiles=smiles, result=make_result(smiles))
                    if smiles != "BAD"
                    else BatchPredictionItem(
                        index=index,
                        smiles=smiles,
                        error_code="InvalidSmilesError",
                        error_message="bad",
                    )
                    for index, smiles in enumerate(smiles_values)
                )
                return BatchPredictionResult(items)

        monkeypatch.setattr(cli, "Predictor", StubPredictor)

    def test_batch_writes_per_molecule_reports(
        self, tmp_path: Path, monkeypatch: Any, make_result: Any
    ) -> None:
        """--format both writes one JSON and one Excel per succeeded item."""
        self._install_stub_predictor(monkeypatch, make_result)
        source = tmp_path / "input.txt"
        source.write_text("CCO\nBAD\nCCN\n", encoding="utf-8")
        out = tmp_path / "batch_out"
        code = cli.main(["batch", str(source), "--format", "both", "--output", str(out)])
        assert code == 0
        assert (out / "batch_prediction.json").is_file()
        assert (out / "prediction_0000.json").is_file()
        assert (out / "prediction_0000.xlsx").read_bytes()[:2] == b"PK"
        assert (out / "prediction_0002.json").is_file()
        assert (out / "prediction_0002.xlsx").is_file()
        assert not (out / "prediction_0001.json").exists()
        assert not (out / "prediction_0001.xlsx").exists()

    def test_batch_resists_rerun_without_overwrite(
        self, tmp_path: Path, monkeypatch: Any, make_result: Any, capsys: Any
    ) -> None:
        """Existing per-molecule reports block a rerun unless --overwrite is given."""
        self._install_stub_predictor(monkeypatch, make_result)
        source = tmp_path / "input.txt"
        source.write_text("CCO\n", encoding="utf-8")
        argv = ["batch", str(source), "--format", "json", "--output", str(tmp_path / "out")]
        assert cli.main(argv) == 0
        assert cli.main(argv) == 2
        assert "Output already exists" in capsys.readouterr().err
        assert cli.main([*argv, "--overwrite"]) == 0


def test_module_entry_point_help() -> None:
    """``python -m edkg_dl --help`` exits successfully."""
    completed = subprocess.run(
        [sys.executable, "-m", "edkg_dl", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0
    assert "edkg-dl-predict" in completed.stdout
