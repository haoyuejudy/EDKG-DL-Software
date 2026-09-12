"""Model asset distribution through the Hugging Face Hub."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir

from .exceptions import AssetDownloadError


DEFAULT_REPO_ID = "HaoyueTan/edkg-dl-models"
REPO_TYPE = "model"
REVISION = "f415bd42214867d2543a068e38ad6d0fa2c92d8c"
REVISION_MARKER = ".revision"


def default_cache_dir() -> Path:
    """Return the per-user cache directory used to store model assets.

    Returns:
        Platform-appropriate cache path such as
        ``~/.cache/edkg-dl/models`` on Linux.
    """
    return Path(user_cache_dir("edkg-dl")) / "models"


def cached_revision(asset_root: str | Path | None = None) -> str | None:
    """Return the revision recorded in ``asset_root``, or ``None`` when absent.

    Args:
        asset_root: Directory previously populated by ``download_assets``;
            defaults to the per-user cache dir.

    Returns:
        Recorded revision string without surrounding whitespace, or
        ``None`` when the marker file is missing or unreadable.
    """
    target = default_cache_dir() if asset_root is None else Path(asset_root).expanduser()
    try:
        return (target / REVISION_MARKER).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _offline_mode() -> bool:
    """Report whether ``HF_HUB_OFFLINE`` disables network synchronization."""
    return os.environ.get("HF_HUB_OFFLINE", "").strip().upper() in {"1", "ON", "YES", "TRUE"}


def download_assets(
    asset_root: str | Path | None = None,
    *,
    repo_id: str = DEFAULT_REPO_ID,
) -> Path:
    """Download model assets from the Hugging Face Hub into ``asset_root``.

    The transfer is resumable and integrity-checked by ``huggingface_hub``;
    files that already match the remote revision are skipped. Set
    ``HF_HUB_OFFLINE=1`` to reuse a previously downloaded snapshot without
    network access (in that case the local revision marker is left untouched
    so a later online run still re-synchronizes outdated files).

    Args:
        asset_root: Target directory; defaults to the per-user cache dir.
        repo_id: Public model repository that distributes the assets.

    Returns:
        Absolute path of the populated asset directory.

    Raises:
        AssetDownloadError: Raised when the Hub transfer fails.
    """
    from huggingface_hub import snapshot_download

    target = default_cache_dir() if asset_root is None else Path(asset_root).expanduser()
    try:
        downloaded = snapshot_download(
            repo_id=repo_id,
            repo_type=REPO_TYPE,
            revision=REVISION,
            local_dir=str(target),
        )
    except Exception as exc:
        raise AssetDownloadError(
            f"Failed to download model assets from {repo_id!r}: {exc}"
        ) from exc
    root = Path(downloaded).resolve()
    if not _offline_mode():
        (root / REVISION_MARKER).write_text(f"{REVISION}\n", encoding="utf-8")
    return root
