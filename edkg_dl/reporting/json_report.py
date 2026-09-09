"""Atomic JSON report output."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..schemas import PredictionResult
from ._files import publish_temporary, validate_destination


def write_json_report(
    result: PredictionResult,
    output: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write a structured prediction result as UTF-8 JSON.

    Args:
        result: Prediction result to serialize.
        output: Target JSON file.
        overwrite: Whether replacing an existing file is allowed.

    Returns:
        Absolute path of the published JSON report.

    Raises:
        OutputExistsError: Raised when the output exists and overwrite
            is disabled.
        OSError: Raised when the report cannot be written or published.
    """
    destination = validate_destination(output, overwrite=overwrite)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(result.to_dict(), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        publish_temporary(temporary, destination, overwrite=overwrite)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return destination
