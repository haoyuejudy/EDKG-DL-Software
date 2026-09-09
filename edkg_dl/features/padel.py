"""Concurrency-safe PaDEL feature extraction."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import FeatureExtractionError, InvalidSmilesError
from ..java import ensure_java


@dataclass(frozen=True)
class PadelFeatureExtractor:
    """Extracts feature rows for single molecules in isolated temporary directories."""

    descriptor_path: Path
    timeout_seconds: int = 10

    def extract(self, smiles: str) -> Any:
        """Convert a single SMILES string into PaDEL descriptors and fingerprints.

        Args:
            smiles: SMILES string describing a single molecule.

        Returns:
            Single-row pandas DataFrame indexed by the PaDEL molecule name.

        Raises:
            InvalidSmilesError: Raised when the input is not a non-empty string.
            FeatureExtractionError: Raised when dependencies, descriptors, Java,
                or the PaDEL output are unavailable or invalid.
            AssetDownloadError: Raised when the Java runtime is missing and
                cannot be downloaded.
        """
        if not isinstance(smiles, str):
            raise InvalidSmilesError("SMILES must be a string")
        normalized = smiles.strip()
        if not normalized:
            raise InvalidSmilesError("SMILES must not be empty")
        if not self.descriptor_path.is_file():
            raise FeatureExtractionError(
                f"PaDEL descriptor configuration not found: {self.descriptor_path}"
            )

        try:
            import pandas as pd
            from padelpy import padeldescriptor
        except ImportError as exc:
            raise FeatureExtractionError("PaDEL dependencies are not installed") from exc

        ensure_java()

        try:
            with tempfile.TemporaryDirectory(prefix="edkg-dl-padel-") as temporary:
                temporary_path = Path(temporary)
                smiles_path = temporary_path / "input.smi"
                output_path = temporary_path / "features.csv"
                smiles_path.write_text(f"{normalized}\n", encoding="utf-8")
                padeldescriptor(
                    detectaromaticity=True,
                    removesalt=True,
                    standardizenitro=True,
                    log=True,
                    d_2d=True,
                    fingerprints=True,
                    descriptortypes=str(self.descriptor_path),
                    mol_dir=str(smiles_path),
                    d_file=str(output_path),
                    sp_timeout=self.timeout_seconds,
                )
                if not output_path.is_file() or output_path.stat().st_size == 0:
                    raise FeatureExtractionError("PaDEL did not create a feature file")
                features = pd.read_csv(output_path, index_col=0)
        except FeatureExtractionError:
            raise
        except Exception as exc:
            raise FeatureExtractionError(f"PaDEL feature extraction failed: {exc}") from exc

        if features.shape[0] != 1:
            raise FeatureExtractionError(
                f"Expected one PaDEL feature row, received {features.shape[0]}"
            )
        if features.empty:
            raise FeatureExtractionError("PaDEL returned an empty feature set")
        return features
