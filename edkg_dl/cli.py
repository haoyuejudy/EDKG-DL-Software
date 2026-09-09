"""Command-line interface for single and batch EDC prediction and asset download."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .api import Predictor
from .exceptions import EdkgDlError, OutputExistsError
from .hub import DEFAULT_REPO_ID, default_cache_dir, download_assets
from .reporting import write_ad_plots, write_excel_report, write_json_report


def _add_prediction_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared by the single and batch prediction commands."""
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s (EDKG-DL) v{__version__}",
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        help=(
            "runtime asset directory (default: EDKG_DL_ASSET_DIR, else the user "
            "cache directory, downloading automatically when missing)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="report directory; without it, JSON is printed to stdout",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace report files that already exist",
    )
    parser.add_argument("--max-paths", type=int, default=1_000)
    parser.add_argument("--max-path-length", type=int)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        Parser configured for single EDC prediction arguments.
    """
    parser = argparse.ArgumentParser(
        prog="edkg-dl-predict",
        description=(
            f"EDKG-DL v{__version__}: predict endocrine-disrupting activity "
            "and sensitive AOP paths."
        ),
        epilog="Run 'edkg-dl-predict download' to fetch model assets into the user cache.",
    )
    _add_prediction_arguments(parser)
    parser.add_argument("smiles", help="SMILES string to predict")
    parser.add_argument(
        "--format",
        choices=("json", "xlsx", "both"),
        default="json",
        help="report format when --output is provided (default: json)",
    )
    parser.add_argument(
        "--ad-plots",
        action="store_true",
        help="write optional PCA applicability-domain plots (requires --output)",
    )
    return parser


def build_download_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the asset download subcommand.

    Returns:
        Parser configured for ``edkg-dl-predict download`` arguments.
    """
    parser = argparse.ArgumentParser(
        prog="edkg-dl-predict download",
        description=(
            f"EDKG-DL v{__version__}: download model assets from the Hugging Face Hub."
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s (EDKG-DL) v{__version__}",
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        help=f"target directory (default: {default_cache_dir()})",
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help="Hugging Face model repository to download from",
    )
    return parser


def run_download(argv: list[str]) -> int:
    """Download model assets and report the populated directory.

    Args:
        argv: Arguments for the download subcommand.

    Returns:
        Process-style exit code: 0 on success, 2 for handled errors.
    """
    arguments = build_download_parser().parse_args(argv)
    try:
        asset_dir = download_assets(arguments.asset_dir, repo_id=arguments.repo_id)
    except (EdkgDlError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(asset_dir)
    return 0


def build_batch_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the batch prediction subcommand.

    Returns:
        Parser configured for batch prediction from a SMILES text file.
    """
    parser = argparse.ArgumentParser(
        prog="edkg-dl-predict batch",
        description=(
            f"EDKG-DL v{__version__}: predict multiple molecules from a text "
            "file (one SMILES per line)."
        ),
    )
    _add_prediction_arguments(parser)
    parser.add_argument(
        "file",
        type=Path,
        help="input text file with one SMILES per line (blank lines and # comments ignored)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="concurrent prediction workers, 1-8 (default: 1)",
    )
    return parser


def read_smiles_file(path: Path) -> list[str]:
    """Read SMILES strings from a text file.

    Args:
        path: Text file with one SMILES per line.

    Returns:
        SMILES strings in file order, without blank lines and ``#`` comments.
    """
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.append(stripped)
    return entries


def run_batch(argv: list[str]) -> int:
    """Run batch prediction over SMILES read from a text file.

    Args:
        argv: Arguments for the batch subcommand.

    Returns:
        Process-style exit code: 0 on success, 2 for handled errors.
    """
    parser = build_batch_parser()
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.max_workers <= 8:
        parser.error("--max-workers must be between 1 and 8")
    if arguments.max_paths < 1:
        parser.error("--max-paths must be at least 1")
    if arguments.max_path_length is not None and arguments.max_path_length < 1:
        parser.error("--max-path-length must be at least 1")

    try:
        input_path = arguments.file.expanduser().resolve()
        smiles_values = read_smiles_file(input_path)
        if not smiles_values:
            raise ValueError(f"No SMILES found in {input_path}")
        predictor = Predictor.from_assets(
            arguments.asset_dir,
            max_paths=arguments.max_paths,
            max_path_length=arguments.max_path_length,
        )
        batch = predictor.predict_batch(
            smiles_values,
            max_items=len(smiles_values),
            max_workers=arguments.max_workers,
        )
        payload = json.dumps(batch.to_dict(), ensure_ascii=False, indent=2)
        if arguments.output is None:
            print(payload)
            return 0

        output_dir = arguments.output.expanduser().resolve()
        if output_dir.exists() and not output_dir.is_dir():
            raise NotADirectoryError(f"Output is not a directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "batch_prediction.json"
        if report_path.exists() and not arguments.overwrite:
            raise OutputExistsError(f"Output already exists: {report_path}")
        report_path.write_text(payload + "\n", encoding="utf-8")
        print(output_dir)
        return 0
    except (EdkgDlError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    """Run the command-line single/batch prediction or download flow.

    Args:
        argv: Optional argument list; defaults to ``sys.argv``.

    Returns:
        Process-style exit code: 0 on success, 2 for handled errors.
    """
    tokens = sys.argv[1:] if argv is None else list(argv)
    if tokens and tokens[0] == "batch":
        return run_batch(tokens[1:])
    if tokens and tokens[0] == "download":
        return run_download(tokens[1:])

    parser = build_parser()
    arguments = parser.parse_args(tokens)
    if arguments.ad_plots and arguments.output is None:
        parser.error("--ad-plots requires --output")
    if arguments.max_paths < 1:
        parser.error("--max-paths must be at least 1")
    if arguments.max_path_length is not None and arguments.max_path_length < 1:
        parser.error("--max-path-length must be at least 1")

    try:
        predictor = Predictor.from_assets(
            arguments.asset_dir,
            max_paths=arguments.max_paths,
            max_path_length=arguments.max_path_length,
        )
        features = None
        if arguments.ad_plots:
            result, features = predictor.pipeline.predict_with_features(arguments.smiles)
        else:
            result = predictor.predict(arguments.smiles)

        if arguments.output is None:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return 0

        output_dir = arguments.output.expanduser().resolve()
        if output_dir.exists() and not output_dir.is_dir():
            raise NotADirectoryError(f"Output is not a directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_paths: list[Path] = []
        if arguments.format in {"json", "both"}:
            report_paths.append(output_dir / "prediction.json")
        if arguments.format in {"xlsx", "both"}:
            report_paths.append(output_dir / "prediction.xlsx")
        existing = [path for path in report_paths if path.exists()]
        if existing and not arguments.overwrite:
            raise OutputExistsError(
                "Output already exists: " + ", ".join(str(path) for path in existing)
            )

        if arguments.ad_plots and features is not None:
            write_ad_plots(
                result,
                features,
                predictor.pipeline.model_registry.paths,
                output_dir / "AD",
                overwrite=arguments.overwrite,
            )
        if arguments.format in {"json", "both"}:
            write_json_report(
                result,
                output_dir / "prediction.json",
                overwrite=arguments.overwrite,
            )
        if arguments.format in {"xlsx", "both"}:
            write_excel_report(
                result,
                output_dir / "prediction.xlsx",
                overwrite=arguments.overwrite,
            )
        print(output_dir)
        return 0
    except (EdkgDlError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
