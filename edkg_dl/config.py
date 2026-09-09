"""Configuration validation and external asset path resolution."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import ArtifactIntegrityError, ArtifactMissingError, ConfigurationError
from .hub import default_cache_dir


@dataclass(frozen=True)
class ProjectPaths:
    """Filesystem layout of externally distributed runtime assets."""

    asset_root: Path

    @classmethod
    def resolve(cls, asset_root: str | Path | None = None) -> ProjectPaths:
        """Resolve the external asset root from an explicit argument and fallbacks.

        Resolution order: the explicit argument, the ``EDKG_DL_ASSET_DIR``
        environment variable, and finally the per-user cache directory
        (which triggers an automatic download when the assets are missing).

        Args:
            asset_root: Explicitly specified asset directory; falls back to the
                environment variable or the cache directory when empty.

        Returns:
            Absolute path set for the chosen asset directory.
        """
        if asset_root is None:
            configured = os.environ.get("EDKG_DL_ASSET_DIR")
            asset_root = configured if configured else default_cache_dir()
        return cls(Path(asset_root).expanduser().resolve())

    @property
    def settings(self) -> Path:
        """Return the path to the event settings JSON."""
        return self.asset_root / "settings.json"

    @property
    def qualitative_models(self) -> Path:
        """Return the qualitative endpoint artifact directory."""
        return self.asset_root / "qualitative_models"

    @property
    def quantitative_models(self) -> Path:
        """Return the quantitative endpoint artifact directory."""
        return self.asset_root / "quantitative_models"

    @property
    def edc_training(self) -> Path:
        """Return the tabular EDC training matrix path."""
        return self.asset_root / "edc_models" / "903-EDCs-2.csv"

    @property
    def edc_model(self) -> Path:
        """Return the tabular EDC classifier path."""
        return self.asset_root / "edc_models" / "model_11.pkl"

    @property
    def gcn_model(self) -> Path:
        """Return the graph neural network state-dict path."""
        return self.asset_root / "gnn_models" / "model_state.pt"

    @property
    def padel_descriptors(self) -> Path:
        """Return the PaDEL descriptor configuration path."""
        return self.asset_root / "padel_runs_cache" / "descriptors.xml"

    @property
    def manifest(self) -> Path:
        """Return the required asset manifest path."""
        return self.asset_root / "manifest.json"

    def validate_runtime_assets(self) -> None:
        """Validate the fixed runtime files and directories.

        Raises:
            ArtifactMissingError: Raised when one or more required assets are missing.
        """
        required = (
            self.settings,
            self.qualitative_models,
            self.quantitative_models,
            self.edc_training,
            self.edc_model,
            self.gcn_model,
            self.padel_descriptors,
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            joined = "\n- ".join(missing)
            raise ArtifactMissingError(f"Missing runtime assets:\n- {joined}")

    def validate_endpoint_assets(self, settings: Settings) -> None:
        """Ensure every configured endpoint has its CSV and model files.

        Args:
            settings: Validated event settings.

        Raises:
            ArtifactMissingError: Raised when a configured CSV or model file is missing.
        """
        required: list[Path] = []
        for event_id in settings.index_to_event.values():
            required.extend(
                (
                    self.qualitative_models / f"{event_id}.csv",
                    self.qualitative_models / f"{event_id}.pkl",
                )
            )
        for index in settings.quantitative_indexes:
            event_id = settings.index_to_event[index]
            required.extend(
                (
                    self.quantitative_models / f"{event_id}.csv",
                    self.quantitative_models / f"{event_id}.pkl",
                )
            )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            joined = "\n- ".join(missing)
            raise ArtifactMissingError(f"Missing endpoint assets:\n- {joined}")

    def verify_manifest(self) -> str:
        """Verify all files declared in the asset manifest.

        Returns:
            Model version declared in the manifest.

        Raises:
            ArtifactMissingError: Raised when the manifest or a listed file is missing.
            ArtifactIntegrityError: Raised when a file digest does not match.
            ConfigurationError: Raised when the manifest structure or a path is invalid.
        """
        if not self.manifest.exists():
            raise ArtifactMissingError(f"Asset manifest not found: {self.manifest}")
        data = _load_json(self.manifest)
        if int(data.get("schema_version", 0)) != 1:
            raise ConfigurationError("Unsupported asset manifest schema_version")
        files = data.get("files")
        if not isinstance(files, dict) or not files:
            raise ConfigurationError("Asset manifest must contain a non-empty files mapping")
        for relative, expected in files.items():
            target = (self.asset_root / relative).resolve()
            if self.asset_root not in target.parents:
                raise ConfigurationError(f"Manifest path escapes asset root: {relative}")
            if not target.is_file():
                raise ArtifactMissingError(f"Manifest asset not found: {target}")
            actual = _sha256(target)
            if actual.lower() != str(expected).lower():
                raise ArtifactIntegrityError(f"Checksum mismatch for {relative}")
        return str(data.get("model_version", "unversioned"))


@dataclass(frozen=True)
class Settings:
    """Validated event, edge, weight-of-evidence, and metadata settings."""

    index_to_event: dict[int, str]
    edges: tuple[tuple[int, int], ...]
    edge_confidences: tuple[int, ...]
    single_event_indexes: tuple[int, ...]
    single_event_woe: tuple[str, ...]
    quantitative_indexes: frozenset[int]
    event_info: dict[str, dict[str, Any]]
    aop_to_events: dict[str, list[str]]

    @classmethod
    def load(cls, path: Path) -> Settings:
        """Load and validate settings from a JSON file.

        Args:
            path: Path to the ``settings.json`` file.

        Returns:
            Parsed and validated settings object.

        Raises:
            ConfigurationError: Raised when the file structure or values are invalid.
        """
        data = _load_json(path)
        try:
            sources, targets = data["edgeIndex"]
            raw_event_info = data["eventInfo"]
            if not isinstance(raw_event_info, dict) or not all(
                isinstance(value, dict) for value in raw_event_info.values()
            ):
                raise TypeError("eventInfo values must be objects")
            settings = cls(
                index_to_event={int(key): str(value) for key, value in data["index2Event"].items()},
                edges=tuple(
                    (int(source), int(target))
                    for source, target in zip(sources, targets, strict=True)
                ),
                edge_confidences=tuple(int(value) for value in data["edgeConfidence"]),
                single_event_indexes=tuple(
                    int(value) for value in data["qualitativeAOPSingleEventsIndexes"]
                ),
                single_event_woe=tuple(
                    str(value) for value in data["qualitativeAOPSingleEventsWOE"]
                ),
                quantitative_indexes=frozenset(
                    int(value) for value in data["quantitative_indexes"]
                ),
                event_info={str(key): dict(value) for key, value in raw_event_info.items()},
                aop_to_events={
                    str(key): list(value) for key, value in data.get("AOP2Event", {}).items()
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid settings file: {path}") from exc
        settings.validate()
        return settings

    def validate(self) -> None:
        """Validate cross-field event and graph-structure invariants.

        Raises:
            ConfigurationError: Raised when any settings invariant is violated.
        """
        if len(self.edges) != len(self.edge_confidences):
            raise ConfigurationError("edgeIndex and edgeConfidence lengths differ")
        if len(self.single_event_indexes) != len(self.single_event_woe):
            raise ConfigurationError("Single-event indexes and WOE lengths differ")
        known_indexes = set(self.index_to_event)
        if known_indexes != set(range(len(known_indexes))):
            raise ConfigurationError("index2Event indexes must be contiguous from zero")
        unknown_edge_indexes = {
            index for edge in self.edges for index in edge if index not in known_indexes
        }
        if unknown_edge_indexes:
            raise ConfigurationError(f"Edges reference unknown indexes: {unknown_edge_indexes}")
        if not self.quantitative_indexes <= known_indexes:
            raise ConfigurationError("quantitative_indexes contains unknown events")
        if not set(self.single_event_indexes) <= known_indexes:
            raise ConfigurationError("Single-event AOP indexes contain unknown events")
        event_ids = set(self.index_to_event.values())
        if set(self.event_info) != event_ids:
            raise ConfigurationError("eventInfo and index2Event contain different event IDs")
        invalid_event_types = {
            event_id: metadata.get("Type")
            for event_id, metadata in self.event_info.items()
            if metadata.get("Type") not in {"MIE", "KE", "AO"}
        }
        if invalid_event_types:
            raise ConfigurationError(f"Unsupported or missing event types: {invalid_event_types}")
        invalid_confidence = set(self.edge_confidences) - {1, 3, 5}
        if invalid_confidence:
            raise ConfigurationError(f"Unsupported edge confidence: {invalid_confidence}")
        quantitative_events = {self.index_to_event[index] for index in self.quantitative_indexes}
        event_edges = {
            (self.index_to_event[source], self.index_to_event[target])
            for source, target in self.edges
        }
        for aop_id, chain in self.aop_to_events.items():
            if not chain:
                raise ConfigurationError(f"AOP chain is empty: {aop_id}")
            unknown_events = set(chain) - event_ids
            if unknown_events:
                raise ConfigurationError(
                    f"AOP chain {aop_id} references unknown events: {unknown_events}"
                )
            if len(set(chain)) != len(chain):
                raise ConfigurationError(f"AOP chain contains repeated events: {aop_id}")
            non_quantitative = set(chain) - quantitative_events
            if non_quantitative:
                raise ConfigurationError(
                    f"AOP chain {aop_id} contains events without quantitative models: "
                    f"{non_quantitative}"
                )
            missing_edges = {
                (source, target)
                for source, target in zip(chain, chain[1:], strict=False)
                if (source, target) not in event_edges
            }
            if missing_edges:
                raise ConfigurationError(
                    f"AOP chain {aop_id} contains relationships absent from edgeIndex: "
                    f"{missing_edges}"
                )


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk.

    Args:
        path: JSON file to read.

    Returns:
        Decoded top-level mapping.

    Raises:
        ArtifactMissingError: Raised when the file does not exist.
        ConfigurationError: Raised when the file is invalid or its top level
            is not an object.
    """
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError as exc:
        raise ArtifactMissingError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Expected a JSON object: {path}")
    return data


def _sha256(path: Path) -> str:
    """Compute the SHA-256 digest of a file.

    Args:
        path: File to digest.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
