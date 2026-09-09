"""Dynamic Excel output generated without an external template workbook."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .. import __version__
from ..schemas import PredictionResult, to_json_value
from ._files import publish_temporary, validate_destination


def write_excel_report(
    result: PredictionResult,
    output: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a dynamic multi-sheet Excel prediction report.

    Args:
        result: Prediction result to serialize.
        output: Target workbook path.
        overwrite: Whether replacing an existing workbook is allowed.

    Returns:
        Absolute path of the published workbook.

    Raises:
        OutputExistsError: Raised when the output exists and overwrite
            is disabled.
        RuntimeError: Raised when XlsxWriter is not installed.
        OSError: Raised when the workbook cannot be written or published.
    """
    destination = validate_destination(output, overwrite=overwrite)
    try:
        import xlsxwriter
    except ImportError as exc:
        raise RuntimeError("Excel output requires the 'xlsxwriter' dependency") from exc

    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".xlsx",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
    try:
        workbook = xlsxwriter.Workbook(temporary)
        header = workbook.add_format(
            {"bold": True, "bg_color": "#D9EAF7", "border": 1, "align": "center", "valign": "center"}
        )
        wrap = workbook.add_format(
            {"text_wrap": True, "valign": "top", "align": "left"}
        )

        _write_rows(
            workbook,
            "Summary",
            ("information", "value"),
            [
                ("smiles", result.smiles),
                ("model version", f"EDKG-DL framework v{__version__}"),
                ("EDKG-DL framework", _edc_label(result.final_edc_prediction)),
                ("qualitative in AD", _yes_no(result.qualitative_in_ad)),
                ("quantitative in AD", _yes_no(result.quantitative_in_ad)),
                ("Sensitive AO (NOAEL)", _sensitive_ao_label(result)),
                ("sensitive paths", _sensitive_paths_label(result)),
                ("duration seconds", result.duration_seconds),
            ],
            header,
            wrap,
        )

        event_headers = (
            "event id",
            "name",
            "node type",
            "MOA",
            "type",
            "node state",
            "qualitative activity",
            "qualitative in AD",
            "quantitative activity",
            "quantitative in AD",
        )
        event_rows = [
            (
                event.event_id,
                event.metadata.get("Name"),
                event.metadata.get("Node-type"),
                event.metadata.get("MOA"),
                event.metadata.get("Type"),
                "active" if event.qualitative_activity == 1 else "inactive",
                event.qualitative_activity,
                _yes_no(event.qualitative_in_ad),
                event.quantitative_activity,
                _yes_no(event.quantitative_in_ad),
            )
            for event in result.events.values()
        ]
        _write_rows(workbook, "Events", event_headers, event_rows, header, wrap)

        candidate_rows = [
            (
                candidate.event_id,
                _event_name(result, candidate.event_id),
                candidate.qualitative_activity,
                _yes_no(candidate.has_quantitative_model),
                candidate.value,
                _yes_no(candidate.quantitative_in_ad),
                candidate.eligible,
                candidate.status,
            )
            for candidate in result.ao_candidates
        ]
        _write_rows(
            workbook,
            "AO Predicted Results",
            (
                "event id",
                "name",
                "qualitative activity",
                "has quantitative model",
                "NOAEL (mg/kg bw/day)",
                "quantitative in AD",
                "eligible",
                "status",
            ),
            candidate_rows,
            header,
            wrap,
        )

        causal_rows = [
            (
                chain.aop_id,
                " -> ".join(chain.events),
                " -> ".join("-" if value is None else str(value) for value in chain.values),
                chain.terminal_event,
                chain.terminal_type,
                _yes_no(chain.all_active),
                _yes_no(chain.all_quantified),
                _yes_no(chain.monotonic),
                _yes_no(chain.all_quantitative_in_ad),
                chain.valid,
                "; ".join(chain.failure_reasons),
            )
            for chain in result.causal_chains
        ]
        _write_rows(
            workbook,
            "Causal Chains",
            (
                "aop id",
                "aop information",
                "NOAEL",
                "terminal event",
                "terminal type",
                "all events active",
                "all events quantified",
                "monotonic",
                "all quantitative in AD",
                "valid",
                "failure reasons",
            ),
            causal_rows,
            header,
            wrap,
        )
        workbook.close()
        publish_temporary(temporary, destination, overwrite=overwrite)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _edc_label(prediction: int) -> str:
    """Format a binary EDC prediction as a human-readable label.

    Args:
        prediction: Binary EDC prediction (1 for EDC, 0 for no EDC).

    Returns:
        ``EDC`` or ``no-EDC``.
    """
    return "EDC" if int(prediction) == 1 else "no-EDC"


def _yes_no(value: bool | None) -> str | None:
    """Format an optional boolean as lowercase yes/no.

    Args:
        value: Boolean flag, or ``None`` when unavailable.

    Returns:
        ``yes``, ``no``, or ``None`` for missing values.
    """
    if value is None:
        return None
    return "yes" if value else "no"


def _event_name(result: PredictionResult, event_id: str) -> str | None:
    """Look up the display name of an event from the result metadata.

    Args:
        result: Prediction result containing event metadata.
        event_id: Identifier of the event.

    Returns:
        The event name, or ``None`` when unknown.
    """
    event = result.events.get(event_id)
    return None if event is None else event.metadata.get("Name")


def _sensitive_ao_label(result: PredictionResult) -> str:
    """Format the sensitive AO endpoint summary line.

    Args:
        result: Prediction result with the sensitive event.

    Returns:
        ``event_id (name) = value (mg/kg bw/day)``, or an empty string
        when no sensitive endpoint exists.
    """
    sensitive = result.sensitive_event
    if sensitive is None:
        return ""
    name = _event_name(result, sensitive.event_id)
    endpoint_name = "-" if name is None else name
    return f"{sensitive.event_id} ({endpoint_name}) = {sensitive.value:.4f} (mg/kg bw/day)"


def _sensitive_paths_label(result: PredictionResult) -> str:
    """Format the sensitive paths summary line with causal validation.

    Args:
        result: Prediction result with sensitive paths.

    Returns:
        Semicolon-joined event paths with an optional causal-validation
        verdict, or ``NO`` when no sensitive path exists.
    """
    if not result.sensitive_paths:
        return "NO"
    paths = " ; ".join(" -> ".join(path) for path in result.sensitive_paths)
    if result.sensitive_event_causally_validated is None:
        return paths
    verdict = "yes" if result.sensitive_event_causally_validated else "no"
    return f"{paths} (causally validated: {verdict})"


def _write_rows(
    workbook: Any,
    name: str,
    headers: tuple[str, ...],
    rows: list[tuple[Any, ...]],
    header_format: Any,
    cell_format: Any,
) -> None:
    """Write a single worksheet from header and row tuples.

    Args:
        workbook: Open XlsxWriter workbook.
        name: Worksheet name.
        headers: Column header labels.
        rows: Row data in display order.
        header_format: XlsxWriter format used for headers.
        cell_format: XlsxWriter format used for data cells.
    """
    worksheet = workbook.add_worksheet(name)
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(len(rows), 1), max(len(headers) - 1, 0))
    for column, value in enumerate(headers):
        worksheet.write(0, column, value, header_format)
    for row_index, row in enumerate(rows, start=1):
        for column, value in enumerate(row):
            worksheet.write(row_index, column, _excel_value(value), cell_format)
    for column in range(len(headers)):
        values = [str(headers[column])]
        values.extend(
            str(_excel_value(row[column]))
            for row in rows
            if column < len(row) and row[column] is not None
        )
        worksheet.set_column(column, column, min(max(map(len, values)) + 2, 60))


def _excel_value(value: Any) -> Any:
    """Convert a value to a type XlsxWriter accepts.

    Args:
        value: Any prediction or metadata value.

    Returns:
        Scalar value, or a JSON string for nested containers.
    """
    normalized = to_json_value(value)
    if normalized is None:
        return ""
    if isinstance(normalized, (dict, list)):
        return json.dumps(normalized, ensure_ascii=False)
    return normalized
