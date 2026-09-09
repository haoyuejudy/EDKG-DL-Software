"""Optional applicability-domain plots loaded only on request."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..config import ProjectPaths
from ..schemas import PredictionResult
from ._files import publish_temporary, validate_destination


def write_ad_plots(
    result: PredictionResult,
    features: Any,
    paths: ProjectPaths,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    """Create PCA views for the models that actually took part in the prediction.

    Args:
        result: Completed prediction result.
        features: Single-row DataFrame containing PaDEL features.
        paths: Resolved training asset paths.
        output_dir: Root output directory for qualitative and quantitative plots.
        overwrite: Whether replacing existing images is allowed.

    Returns:
        Absolute paths of all generated images.

    Raises:
        OutputExistsError: Raised when an image exists and overwrite is disabled.
        ImportError: Raised when the optional plotting dependency is unavailable.
        OSError: Raised when an image cannot be published.
    """
    requests: list[tuple[Path, Path, bool]] = []
    root = Path(output_dir).expanduser().resolve()
    for event in result.events.values():
        requests.append(
            (
                paths.qualitative_models / f"{event.event_id}.csv",
                root / "qualitative" / f"{event.event_id}.png",
                bool(event.qualitative_in_ad),
            )
        )
        if event.quantitative_activity is not None:
            requests.append(
                (
                    paths.quantitative_models / f"{event.event_id}.csv",
                    root / "quantitative" / f"{event.event_id}.png",
                    bool(event.quantitative_in_ad),
                )
            )

    destinations = [
        validate_destination(destination, overwrite=overwrite) for _, destination, _ in requests
    ]
    written: list[Path] = []
    for (training_path, _destination, in_domain), checked in zip(
        requests, destinations, strict=True
    ):
        _write_plot(
            features,
            training_path,
            checked,
            in_domain=in_domain,
            overwrite=overwrite,
        )
        written.append(checked)
    return tuple(written)


def _write_plot(
    features: Any,
    training_path: Path,
    destination: Path,
    *,
    in_domain: bool,
    overwrite: bool,
) -> None:
    """Plot the training distribution and the predicted molecule for one endpoint.

    Args:
        features: Single-row DataFrame containing PaDEL features.
        training_path: Path to the endpoint training matrix CSV.
        destination: Output PNG path.
        in_domain: Whether the predicted molecule lies inside the applicability
            domain.
        overwrite: Whether replacing an existing image is allowed.
    """
    import matplotlib.pyplot as plt
    import pandas as pd
    from sklearn.decomposition import PCA

    training = pd.read_csv(training_path, index_col=0)
    selected = features.loc[:, training.columns]
    pca = PCA(n_components=2).fit(training)
    training_2d = pca.transform(training)
    sample_2d = pca.transform(selected)

    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".png",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
    figure, axis = plt.subplots(figsize=(6, 5))
    try:
        axis.scatter(
            training_2d[:, 0],
            training_2d[:, 1],
            s=8,
            alpha=0.25,
            label="training samples",
        )
        axis.scatter(
            sample_2d[:, 0],
            sample_2d[:, 1],
            s=70,
            marker="x",
            label="predicted molecule",
        )
        axis.set_title("In applicability domain" if in_domain else "Outside applicability domain")
        axis.set_xlabel("PCA 1")
        axis.set_ylabel("PCA 2")
        axis.legend()
        figure.tight_layout()
        figure.savefig(temporary, dpi=150, format="png")
        publish_temporary(temporary, destination, overwrite=overwrite)
    finally:
        plt.close(figure)
        temporary.unlink(missing_ok=True)
