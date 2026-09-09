"""Tests for configuration validation and asset-manifest verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from edkg_dl.config import ProjectPaths, Settings
from edkg_dl.exceptions import (
    ArtifactIntegrityError,
    ArtifactMissingError,
    ConfigurationError,
)


def _write_json(path: Path, payload: Any) -> Path:
    """Write a JSON payload to the given path."""
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestProjectPathsResolve:
    """Asset-root resolution precedence."""

    def test_explicit_argument_wins(self, tmp_path: Path, monkeypatch: Any) -> None:
        """An explicit argument overrides the environment variable."""
        monkeypatch.setenv("EDKG_DL_ASSET_DIR", str(tmp_path / "from-env"))
        resolved = ProjectPaths.resolve(tmp_path / "explicit")
        assert resolved.asset_root == (tmp_path / "explicit").resolve()

    def test_environment_variable_used_when_no_argument(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """The environment variable fills in a missing argument."""
        configured = tmp_path / "from-env"
        monkeypatch.setenv("EDKG_DL_ASSET_DIR", str(configured))
        assert ProjectPaths.resolve(None).asset_root == configured.resolve()

    def test_layout_properties(self, tmp_path: Path) -> None:
        """Fixed layout properties derive from the asset root."""
        paths = ProjectPaths.resolve(tmp_path)
        assert paths.settings == paths.asset_root / "settings.json"
        assert paths.qualitative_models == paths.asset_root / "qualitative_models"
        assert paths.quantitative_models == paths.asset_root / "quantitative_models"
        assert paths.edc_training == paths.asset_root / "edc_models" / "903-EDCs-2.csv"
        assert paths.edc_model == paths.asset_root / "edc_models" / "model_11.pkl"
        assert paths.gcn_model == paths.asset_root / "gnn_models" / "model_state.pt"
        assert paths.padel_descriptors == paths.asset_root / "padel_runs_cache" / "descriptors.xml"
        assert paths.manifest == paths.asset_root / "manifest.json"


class TestValidateRuntimeAssets:
    """Fixed runtime asset validation."""

    def test_empty_root_lists_every_missing_asset(self, tmp_path: Path) -> None:
        """All required assets are reported when the root is empty."""
        paths = ProjectPaths.resolve(tmp_path)
        with pytest.raises(ArtifactMissingError, match="Missing runtime assets"):
            paths.validate_runtime_assets()

    def test_complete_root_passes(self, tmp_path: Path) -> None:
        """A fully populated root passes validation."""
        for relative in (
            "settings.json",
            "qualitative_models",
            "quantitative_models",
            "edc_models/903-EDCs-2.csv",
            "edc_models/model_11.pkl",
            "gnn_models/model_state.pt",
            "padel_runs_cache/descriptors.xml",
        ):
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix:
                target.write_bytes(b"data")
            else:
                target.mkdir()
        ProjectPaths.resolve(tmp_path).validate_runtime_assets()

    def test_endpoint_assets_missing(self, tmp_path: Path, settings_payload: Any) -> None:
        """Missing endpoint CSV or model files are reported per event."""
        settings_file = _write_json(tmp_path / "settings.json", settings_payload)
        settings = Settings.load(settings_file)
        with pytest.raises(ArtifactMissingError, match="Missing endpoint assets"):
            ProjectPaths.resolve(tmp_path).validate_endpoint_assets(settings)


class TestVerifyManifest:
    """Asset manifest integrity verification."""

    def _write_manifest(
        self, root: Path, files: dict[str, str], *, schema_version: int = 1
    ) -> None:
        """Write a manifest with the given file digest mapping."""
        payload = {
            "schema_version": schema_version,
            "files": files,
            "model_version": "test-1",
        }
        _write_json(root / "manifest.json", payload)

    def _asset_root(self, tmp_path: Path) -> Path:
        """Create and return an empty asset root."""
        root = tmp_path / "assets"
        root.mkdir()
        return root

    def test_valid_manifest_returns_model_version(self, tmp_path: Path) -> None:
        """A matching manifest returns its declared model version."""
        root = self._asset_root(tmp_path)
        (root / "model.bin").write_bytes(b"payload")
        digest = hashlib.sha256(b"payload").hexdigest()
        self._write_manifest(root, {"model.bin": digest})
        assert ProjectPaths.resolve(root).verify_manifest() == "test-1"

    def test_missing_manifest(self, tmp_path: Path) -> None:
        """A missing manifest file is reported."""
        root = self._asset_root(tmp_path)
        with pytest.raises(ArtifactMissingError, match="manifest"):
            ProjectPaths.resolve(root).verify_manifest()

    def test_unsupported_schema_version(self, tmp_path: Path) -> None:
        """Unsupported schema versions are rejected."""
        root = self._asset_root(tmp_path)
        self._write_manifest(root, {}, schema_version=2)
        with pytest.raises(ConfigurationError, match="schema_version"):
            ProjectPaths.resolve(root).verify_manifest()

    def test_empty_files_mapping(self, tmp_path: Path) -> None:
        """An empty files mapping is rejected."""
        root = self._asset_root(tmp_path)
        (root / "model.bin").write_bytes(b"payload")
        self._write_manifest(root, {})
        with pytest.raises(ConfigurationError, match="files mapping"):
            ProjectPaths.resolve(root).verify_manifest()

    def test_path_escaping_asset_root(self, tmp_path: Path) -> None:
        """Manifest paths must stay inside the asset root."""
        root = self._asset_root(tmp_path)
        self._write_manifest(root, {"../escape.txt": "0" * 64})
        with pytest.raises(ConfigurationError, match="escapes asset root"):
            ProjectPaths.resolve(root).verify_manifest()

    def test_declared_file_missing(self, tmp_path: Path) -> None:
        """A manifest entry without its file is reported."""
        root = self._asset_root(tmp_path)
        self._write_manifest(root, {"gone.bin": "0" * 64})
        with pytest.raises(ArtifactMissingError, match="gone.bin"):
            ProjectPaths.resolve(root).verify_manifest()

    def test_checksum_mismatch(self, tmp_path: Path) -> None:
        """A wrong digest fails integrity verification."""
        root = self._asset_root(tmp_path)
        (root / "model.bin").write_bytes(b"payload")
        self._write_manifest(root, {"model.bin": "f" * 64})
        with pytest.raises(ArtifactIntegrityError, match="Checksum mismatch"):
            ProjectPaths.resolve(root).verify_manifest()


class TestSettingsLoad:
    """Settings parsing and cross-field validation."""

    def _load(self, tmp_path: Path, payload: Any) -> Settings:
        """Load settings from a temporary file holding the payload."""
        return Settings.load(_write_json(tmp_path / "settings.json", payload))

    def test_valid_payload_loads(self, tmp_path: Path, settings_payload: Any) -> None:
        """The canonical valid payload loads with parsed structure."""
        settings = self._load(tmp_path, settings_payload)
        assert settings.index_to_event[0] == "E0"
        assert settings.edges == ((2, 1), (1, 0), (0, 4))
        assert settings.quantitative_indexes == frozenset({0, 1, 2, 3})
        assert settings.aop_to_events == {"AOP-1": ["E2", "E1", "E0"]}

    def test_missing_file(self, tmp_path: Path) -> None:
        """A missing settings file raises ArtifactMissingError."""
        with pytest.raises(ArtifactMissingError, match="not found"):
            Settings.load(tmp_path / "missing.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Malformed JSON raises ConfigurationError."""
        path = tmp_path / "settings.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            Settings.load(path)

    def test_non_object_top_level(self, tmp_path: Path) -> None:
        """A non-object JSON document is rejected."""
        with pytest.raises(ConfigurationError, match="Expected a JSON object"):
            Settings.load(_write_json(tmp_path / "settings.json", [1, 2]))

    def test_missing_required_key(self, tmp_path: Path, settings_payload: Any) -> None:
        """A missing required key wraps into ConfigurationError."""
        del settings_payload["edgeIndex"]
        with pytest.raises(ConfigurationError, match="Invalid settings file"):
            self._load(tmp_path, settings_payload)

    def test_event_info_values_must_be_objects(self, tmp_path: Path, settings_payload: Any) -> None:
        """Non-object eventInfo values are rejected."""
        settings_payload["eventInfo"] = {"E0": "not-an-object"}
        with pytest.raises(ConfigurationError):
            self._load(tmp_path, settings_payload)

    def test_edge_confidence_length_mismatch(self, tmp_path: Path, settings_payload: Any) -> None:
        """EdgeIndex and edgeConfidence lengths must agree."""
        settings_payload["edgeConfidence"] = [3]
        with pytest.raises(ConfigurationError, match="edgeConfidence lengths differ"):
            self._load(tmp_path, settings_payload)

    def test_single_event_length_mismatch(self, tmp_path: Path, settings_payload: Any) -> None:
        """Single-event indexes and WOE lengths must agree."""
        settings_payload["qualitativeAOPSingleEventsIndexes"] = [1, 2]
        with pytest.raises(ConfigurationError, match="WOE lengths differ"):
            self._load(tmp_path, settings_payload)

    def test_non_contiguous_indexes(self, tmp_path: Path, settings_payload: Any) -> None:
        """index2Event indexes must be contiguous from zero."""
        settings_payload["index2Event"] = {"0": "E0", "2": "E2"}
        with pytest.raises(ConfigurationError, match="contiguous"):
            self._load(tmp_path, settings_payload)

    def test_edges_reference_unknown_index(self, tmp_path: Path, settings_payload: Any) -> None:
        """Edges may only reference known indexes."""
        settings_payload["edgeIndex"] = [[2, 1, 1], [1, 0, 99]]
        with pytest.raises(ConfigurationError, match="unknown indexes"):
            self._load(tmp_path, settings_payload)

    def test_quantitative_indexes_unknown(self, tmp_path: Path, settings_payload: Any) -> None:
        """quantitative_indexes may only reference known events."""
        settings_payload["quantitative_indexes"] = [0, 42]
        with pytest.raises(ConfigurationError, match="quantitative_indexes"):
            self._load(tmp_path, settings_payload)

    def test_single_event_indexes_unknown(self, tmp_path: Path, settings_payload: Any) -> None:
        """Single-event indexes may only reference known events."""
        settings_payload["qualitativeAOPSingleEventsIndexes"] = [77]
        with pytest.raises(ConfigurationError, match="Single-event"):
            self._load(tmp_path, settings_payload)

    def test_event_info_mismatch(self, tmp_path: Path, settings_payload: Any) -> None:
        """EventInfo keys must match index2Event values."""
        del settings_payload["eventInfo"]["E4"]
        with pytest.raises(ConfigurationError, match="different event IDs"):
            self._load(tmp_path, settings_payload)

    def test_unsupported_event_type(self, tmp_path: Path, settings_payload: Any) -> None:
        """Event types are restricted to MIE, KE, and AO."""
        settings_payload["eventInfo"]["E0"]["Type"] = "Something"
        with pytest.raises(ConfigurationError, match="event types"):
            self._load(tmp_path, settings_payload)

    def test_unsupported_edge_confidence(self, tmp_path: Path, settings_payload: Any) -> None:
        """Edge confidences are restricted to 1, 3, and 5."""
        settings_payload["edgeConfidence"] = [3, 5, 2]
        with pytest.raises(ConfigurationError, match="edge confidence"):
            self._load(tmp_path, settings_payload)

    def test_aop_chain_empty(self, tmp_path: Path, settings_payload: Any) -> None:
        """AOP chains must not be empty."""
        settings_payload["AOP2Event"] = {"AOP-1": []}
        with pytest.raises(ConfigurationError, match="chain is empty"):
            self._load(tmp_path, settings_payload)

    def test_aop_chain_unknown_event(self, tmp_path: Path, settings_payload: Any) -> None:
        """AOP chains may only reference known events."""
        settings_payload["AOP2Event"] = {"AOP-1": ["E2", "E1", "missing"]}
        with pytest.raises(ConfigurationError, match="unknown events"):
            self._load(tmp_path, settings_payload)

    def test_aop_chain_repeated_event(self, tmp_path: Path, settings_payload: Any) -> None:
        """AOP chains must not repeat events."""
        settings_payload["AOP2Event"] = {"AOP-1": ["E2", "E2", "E0"]}
        with pytest.raises(ConfigurationError, match="repeated events"):
            self._load(tmp_path, settings_payload)

    def test_aop_chain_without_quantitative_models(
        self, tmp_path: Path, settings_payload: Any
    ) -> None:
        """Every AOP chain member needs a quantitative model."""
        settings_payload["quantitative_indexes"] = [0, 1]
        with pytest.raises(ConfigurationError, match="without quantitative models"):
            self._load(tmp_path, settings_payload)

    def test_aop_chain_edge_missing(self, tmp_path: Path, settings_payload: Any) -> None:
        """Adjacent chain members must be connected by configured edges."""
        settings_payload["AOP2Event"] = {"AOP-1": ["E2", "E0", "E1"]}
        with pytest.raises(ConfigurationError, match="absent from edgeIndex"):
            self._load(tmp_path, settings_payload)
