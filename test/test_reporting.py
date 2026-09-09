"""Tests for atomic report writers and shared output helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edkg_dl.exceptions import OutputExistsError
from edkg_dl.reporting import write_excel_report, write_json_report
from edkg_dl.reporting._files import publish_temporary, validate_destination
from edkg_dl.schemas import PredictionResult


class TestValidateDestination:
    """Destination resolution and overwrite policy."""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Missing parent directories are created."""
        target = tmp_path / "nested" / "report.json"
        assert validate_destination(target, overwrite=False) == target
        assert target.parent.is_dir()

    def test_existing_destination_rejected_without_overwrite(self, tmp_path: Path) -> None:
        """An existing destination raises OutputExistsError."""
        target = tmp_path / "report.json"
        target.write_text("old", encoding="utf-8")
        with pytest.raises(OutputExistsError):
            validate_destination(target, overwrite=False)

    def test_existing_destination_allowed_with_overwrite(self, tmp_path: Path) -> None:
        """Overwrite mode accepts an existing destination."""
        target = tmp_path / "report.json"
        target.write_text("old", encoding="utf-8")
        assert validate_destination(target, overwrite=True) == target


class TestPublishTemporary:
    """Atomic temporary-file publication."""

    def test_links_without_overwrite(self, tmp_path: Path) -> None:
        """A fresh destination receives the temporary content."""
        temporary = tmp_path / "work.tmp"
        temporary.write_text("data", encoding="utf-8")
        destination = tmp_path / "final.json"
        publish_temporary(temporary, destination, overwrite=False)
        assert destination.read_text(encoding="utf-8") == "data"
        assert not temporary.exists()

    def test_existing_destination_rejected(self, tmp_path: Path) -> None:
        """Publication onto an existing destination fails atomically."""
        temporary = tmp_path / "work.tmp"
        temporary.write_text("new", encoding="utf-8")
        destination = tmp_path / "final.json"
        destination.write_text("old", encoding="utf-8")
        with pytest.raises(OutputExistsError):
            publish_temporary(temporary, destination, overwrite=False)
        assert destination.read_text(encoding="utf-8") == "old"
        assert not temporary.exists()

    def test_overwrite_replaces_destination(self, tmp_path: Path) -> None:
        """Overwrite mode replaces the destination content."""
        temporary = tmp_path / "work.tmp"
        temporary.write_text("new", encoding="utf-8")
        destination = tmp_path / "final.json"
        destination.write_text("old", encoding="utf-8")
        publish_temporary(temporary, destination, overwrite=True)
        assert destination.read_text(encoding="utf-8") == "new"
        assert not temporary.exists()


class TestJsonReport:
    """JSON report writer."""

    def test_round_trip_and_overwrite_protection(
        self, tmp_path: Path, result: PredictionResult
    ) -> None:
        """Reports serialize the full result and resist double writes."""
        target = tmp_path / "prediction.json"
        written = write_json_report(result, target)
        assert written == target
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["smiles"] == result.smiles
        assert payload["final_edc_prediction"] == 1
        assert payload["events"]["E2"]["node_state"] == "active"
        with pytest.raises(OutputExistsError):
            write_json_report(result, target)
        write_json_report(result, target, overwrite=True)


class TestExcelReport:
    """Excel report writer."""

    def test_creates_valid_workbook(self, tmp_path: Path, result: PredictionResult) -> None:
        """The writer produces a real xlsx zip container."""
        target = tmp_path / "prediction.xlsx"
        written = write_excel_report(result, target)
        assert written == target
        assert target.read_bytes()[:2] == b"PK"

    def test_overwrite_protection(self, tmp_path: Path, result: PredictionResult) -> None:
        """Existing workbooks resist double writes without overwrite."""
        target = tmp_path / "prediction.xlsx"
        write_excel_report(result, target)
        with pytest.raises(OutputExistsError):
            write_excel_report(result, target)
