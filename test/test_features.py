"""Tests for PaDEL feature-extraction input validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from edkg_dl.exceptions import FeatureExtractionError, InvalidSmilesError
from edkg_dl.features import PadelFeatureExtractor


def test_rejects_non_string_smiles(tmp_path: Path) -> None:
    """Non-string SMILES values are rejected."""
    extractor = PadelFeatureExtractor(tmp_path / "descriptors.xml")
    with pytest.raises(InvalidSmilesError, match="must be a string"):
        extractor.extract(123)


def test_rejects_blank_smiles(tmp_path: Path) -> None:
    """Blank SMILES strings are rejected."""
    extractor = PadelFeatureExtractor(tmp_path / "descriptors.xml")
    with pytest.raises(InvalidSmilesError, match="must not be empty"):
        extractor.extract("   ")


def test_missing_descriptor_configuration(tmp_path: Path) -> None:
    """A missing descriptor configuration fails before any tooling runs."""
    extractor = PadelFeatureExtractor(tmp_path / "missing.xml")
    with pytest.raises(FeatureExtractionError, match="descriptor configuration"):
        extractor.extract("CCO")
