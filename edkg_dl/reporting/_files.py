"""Shared atomic-output helpers for report writers."""

from __future__ import annotations

import os
from pathlib import Path

from ..exceptions import OutputExistsError


def validate_destination(path: str | Path, *, overwrite: bool) -> Path:
    """Resolve an output path and enforce the overwrite policy.

    Args:
        path: Requested output file path.
        overwrite: Whether replacing an existing file is allowed.

    Returns:
        Absolute destination path with its parent directory created.

    Raises:
        OutputExistsError: Raised when the destination exists and overwrite
            is disabled.
    """
    destination = Path(path).expanduser().resolve()
    if destination.exists() and not overwrite:
        raise OutputExistsError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def publish_temporary(temporary: Path, destination: Path, *, overwrite: bool) -> None:
    """Atomically publish a complete temporary file within the same filesystem.

    Args:
        temporary: Fully written temporary file.
        destination: Final output file path.
        overwrite: Whether replacing an existing destination is allowed.

    Raises:
        OutputExistsError: Raised when a competing output exists and
            overwrite is disabled.
        OSError: Raised when the filesystem cannot create a link or
            replace a file.
    """
    try:
        if overwrite:
            temporary.replace(destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise OutputExistsError(f"Output already exists: {destination}") from exc
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
