"""Model asset distribution through the Hugging Face Hub."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir

from .exceptions import AssetDownloadError


DEFAULT_REPO_ID = "HaoyueTan/edkg-dl-models"
REPO_TYPE = "model"
REVISION = "04a4c0a165b1606ea0bf07a50ed70e572ad333d0"


def default_cache_dir() -> Path:
    """Return the per-user cache directory used to store model assets.

    Returns:
        Platform-appropriate cache path such as
        ``~/.cache/edkg-dl/models`` on Linux.
    """
    return Path(user_cache_dir("edkg-dl")) / "models"


def download_assets(
    asset_root: str | Path | None = None,
    *,
    repo_id: str = DEFAULT_REPO_ID,
) -> Path:
    """Download model assets from the Hugging Face Hub into ``asset_root``.

    The transfer is resumable and integrity-checked by ``huggingface_hub``;
    files that already match the remote revision are skipped. Set
    ``HF_HUB_OFFLINE=1`` to reuse a previously downloaded snapshot without
    network access.

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
    return Path(downloaded).resolve()
