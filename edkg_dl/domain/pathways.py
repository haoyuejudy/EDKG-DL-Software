"""AOP path discovery with cardinality bounds."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import islice


@dataclass(frozen=True)
class PathSearchResult:
    """Bounded path-search result with a truncation flag."""

    paths: tuple[tuple[str, ...], ...]
    truncated: bool


def find_sensitive_paths(
    *,
    index_to_event: dict[int, str],
    edges: tuple[tuple[int, int], ...],
    active_events: set[str],
    sensitive_event: str | None,
    max_paths: int = 1_000,
    max_length: int | None = None,
) -> PathSearchResult:
    """Find activated upstream paths ending at the sensitive event.

    The configured graph direction is reversed during the search to preserve
    the path order returned by the legacy implementation.

    Args:
        index_to_event: Mapping of graph node index to event ID.
        edges: Configured directed graph edges.
        active_events: Set of event IDs predicted as active.
        sensitive_event: Quantitative event chosen as the most sensitive endpoint.
        max_paths: Maximum number of paths to return.
        max_length: Maximum number of edges allowed in one simple path;
            unlimited when ``None``.

    Returns:
        Discovered paths and a flag indicating whether more paths remain.

    Raises:
        ValueError: Raised when ``max_paths`` is less than 1.
    """
    if sensitive_event is None:
        return PathSearchResult(paths=(), truncated=False)
    if max_paths < 1:
        raise ValueError("max_paths must be at least 1")

    import networkx as nx

    event_to_index = {event: index for index, event in index_to_event.items()}
    sensitive_index = event_to_index.get(sensitive_event)
    graph = nx.DiGraph()
    for source, target in edges:
        source_event = index_to_event[source]
        target_event = index_to_event[target]
        if source_event in active_events and target_event in active_events:
            graph.add_edge(target, source)
    if sensitive_index not in graph:
        return PathSearchResult(paths=(), truncated=False)

    def iter_paths() -> Iterator[tuple[str, ...]]:
        """Yield event paths in legacy orientation and deterministic graph order."""
        for node in graph.nodes:
            if node == sensitive_index:
                continue
            for path in nx.all_simple_paths(
                graph,
                source=node,
                target=sensitive_index,
                cutoff=max_length,
            ):
                yield tuple(index_to_event[index] for index in reversed(path))

    selected = list(islice(iter_paths(), max_paths + 1))
    return PathSearchResult(
        paths=tuple(selected[:max_paths]),
        truncated=len(selected) > max_paths,
    )
