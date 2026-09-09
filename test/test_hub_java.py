"""Tests for asset-hub and Java-runtime provisioning helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from edkg_dl import hub, java
from edkg_dl.exceptions import AssetDownloadError


def test_default_cache_dir_is_platform_path() -> None:
    """The cache directory nests under the per-user edkg-dl cache."""
    default = hub.default_cache_dir()
    assert default.is_absolute()
    assert default.name == "models"


def test_download_assets_offline_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A download without network or cached snapshot raises AssetDownloadError."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    with pytest.raises(AssetDownloadError, match="Failed to download"):
        hub.download_assets(tmp_path, repo_id="edkg-dl-tests/nonexistent")


class TestAdoptiumPlatform:
    """Machine to Adoptium release mapping."""

    def _map(
        self, monkeypatch: pytest.MonkeyPatch, system: str, machine: str
    ) -> tuple[str, str, str]:
        """Map a fake machine through _adoptium_platform."""
        monkeypatch.setattr(java.platform, "system", lambda: system)
        monkeypatch.setattr(java.platform, "machine", lambda: machine)
        return java._adoptium_platform()

    @pytest.mark.parametrize(
        ("system", "machine", "expected"),
        [
            ("Linux", "amd64", ("linux", "x64", "linux-x64")),
            ("Linux", "aarch64", ("linux", "aarch64", "linux-aarch64")),
            ("Darwin", "arm64", ("mac", "aarch64", "mac-aarch64")),
            ("Windows", "AMD64", ("windows", "x64", "windows-x64")),
        ],
    )
    def test_supported_platforms(
        self,
        monkeypatch: pytest.MonkeyPatch,
        system: str,
        machine: str,
        expected: tuple[str, str, str],
    ) -> None:
        """Known platforms map onto Adoptium identifiers."""
        assert self._map(monkeypatch, system, machine) == expected

    def test_unsupported_platform_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown systems raise AssetDownloadError."""
        with pytest.raises(AssetDownloadError, match="No Temurin JRE"):
            self._map(monkeypatch, "SunOS", "amd64")

    def test_unsupported_architecture_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown architectures raise AssetDownloadError."""
        with pytest.raises(AssetDownloadError, match="No Temurin JRE"):
            self._map(monkeypatch, "Linux", "i686")


def test_java_binary_detection(tmp_path: Path) -> None:
    """The java executable is detected per platform naming rules."""
    binary_name = "java.exe" if java.os.name == "nt" else "java"
    assert java._java_binary(tmp_path) is None
    binary = tmp_path / "bin" / binary_name
    binary.parent.mkdir()
    binary.write_text("", encoding="utf-8")
    assert java._java_binary(tmp_path) == binary


class TestPrependToPath:
    """PATH mutation for the provisioned runtime."""

    def test_prepends_to_empty_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """An empty PATH receives the bin directory alone."""
        monkeypatch.setenv("PATH", "")
        java._prepend_to_path(tmp_path)
        assert java.os.environ["PATH"] == str(tmp_path)

    def test_prepends_without_duplicating(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The bin directory is prepended once."""
        monkeypatch.setenv("PATH", "existing")
        java._prepend_to_path(tmp_path)
        expected = f"{tmp_path}{java.os.pathsep}existing"
        assert java.os.environ["PATH"] == expected
        java._prepend_to_path(tmp_path)
        assert java.os.environ["PATH"] == expected


def test_ensure_java_reuses_system_java(monkeypatch: pytest.MonkeyPatch) -> None:
    """A java already on PATH short-circuits provisioning."""
    monkeypatch.setattr(java.shutil, "which", lambda name: "/fake/java")
    assert java.ensure_java() is None
