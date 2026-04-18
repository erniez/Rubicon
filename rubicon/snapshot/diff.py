"""Compare two snapshots and produce a structured diff."""

from dataclasses import dataclass, field
from typing import Any

from rubicon.snapshot.models import Snapshot


@dataclass
class SnapshotDiff:
    """Structured difference between two snapshots."""

    added_edges: list[dict[str, Any]] = field(default_factory=list)
    removed_edges: list[dict[str, Any]] = field(default_factory=list)
    added_nodes: list[str] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    new_violations: list[dict[str, Any]] = field(default_factory=list)
    resolved_violations: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


def diff_snapshots(
    previous: Snapshot | None,
    current: Snapshot,
) -> SnapshotDiff:
    """Compare two snapshots and return the differences.

    If previous is None (first run), everything in current is "added".
    """
    if previous is None:
        return _diff_from_nothing(current)

    diff = SnapshotDiff()

    # Node diff
    prev_node_ids = {n["id"] for n in previous.nodes}
    curr_node_ids = {n["id"] for n in current.nodes}
    diff.added_nodes = sorted(curr_node_ids - prev_node_ids)
    diff.removed_nodes = sorted(prev_node_ids - curr_node_ids)

    # Edge diff — keyed by (source, target, relationship_type) tuples
    prev_edge_keys = _edge_keys(previous.edges)
    curr_edge_keys = _edge_keys(current.edges)

    added_keys = curr_edge_keys - prev_edge_keys
    removed_keys = prev_edge_keys - curr_edge_keys

    curr_edge_lookup = _edge_lookup(current.edges)
    prev_edge_lookup = _edge_lookup(previous.edges)

    for key in sorted(added_keys):
        diff.added_edges.append(curr_edge_lookup[key])

    for key in sorted(removed_keys):
        diff.removed_edges.append(prev_edge_lookup[key])

    # Violation diff — keyed by (rule, source_node_id, target_node_id)
    prev_viol_keys = _violation_keys(previous.violations)
    curr_viol_keys = _violation_keys(current.violations)

    new_viol_keys = curr_viol_keys - prev_viol_keys
    resolved_viol_keys = prev_viol_keys - curr_viol_keys

    curr_viol_lookup = _violation_lookup(current.violations)
    prev_viol_lookup = _violation_lookup(previous.violations)

    for viol_key in sorted(new_viol_keys, key=lambda k: (k[0], k[1], k[2] or "")):
        diff.new_violations.append(curr_viol_lookup[viol_key])

    for viol_key in sorted(resolved_viol_keys, key=lambda k: (k[0], k[1], k[2] or "")):
        diff.resolved_violations.append(prev_viol_lookup[viol_key])

    diff.summary = _build_summary(diff)
    return diff


def _diff_from_nothing(current: Snapshot) -> SnapshotDiff:
    """Treat everything in the current snapshot as new."""
    diff = SnapshotDiff()
    diff.added_nodes = sorted(n["id"] for n in current.nodes)
    diff.added_edges = list(current.edges)
    diff.new_violations = list(current.violations)
    diff.summary = _build_summary(diff)
    return diff


def _edge_key(source: str, target: str, rel_type: str) -> tuple[str, str, str]:
    return (source, target, rel_type)


def _edge_keys(edges: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    """Extract unique edge keys from a list of serialized edges."""
    keys: set[tuple[str, str, str]] = set()
    for edge in edges:
        for rel in edge.get("relationships", []):
            keys.add(_edge_key(edge["source"], edge["target"], rel["type"]))
    # Also track edges with no relationships (bare edges)
    for edge in edges:
        if not edge.get("relationships"):
            keys.add(_edge_key(edge["source"], edge["target"], ""))
    return keys


def _edge_lookup(edges: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Build a lookup from edge key to the full edge dict."""
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        for rel in edge.get("relationships", []):
            key = _edge_key(edge["source"], edge["target"], rel["type"])
            lookup[key] = edge
        if not edge.get("relationships"):
            key = _edge_key(edge["source"], edge["target"], "")
            lookup[key] = edge
    return lookup


def _violation_key(v: dict[str, Any]) -> tuple[str, str, str | None]:
    return (v["rule"], v["source_node_id"], v.get("target_node_id"))


def _violation_keys(violations: list[dict[str, Any]]) -> set[tuple[str, str, str | None]]:
    return {_violation_key(v) for v in violations}


def _violation_lookup(
    violations: list[dict[str, Any]],
) -> dict[tuple[str, str, str | None], dict[str, Any]]:
    return {_violation_key(v): v for v in violations}


def _build_summary(diff: SnapshotDiff) -> str:
    """Build a human-readable summary string."""
    parts: list[str] = []

    if diff.added_edges:
        n = len(diff.added_edges)
        parts.append(f"+{n} connection{'s' if n != 1 else ''}")
    if diff.removed_edges:
        n = len(diff.removed_edges)
        parts.append(f"-{n} connection{'s' if n != 1 else ''}")
    if diff.added_nodes:
        n = len(diff.added_nodes)
        parts.append(f"+{n} file{'s' if n != 1 else ''}")
    if diff.removed_nodes:
        n = len(diff.removed_nodes)
        parts.append(f"-{n} file{'s' if n != 1 else ''}")
    if diff.new_violations:
        n = len(diff.new_violations)
        parts.append(f"{n} new violation{'s' if n != 1 else ''}")
    if diff.resolved_violations:
        n = len(diff.resolved_violations)
        parts.append(f"{n} resolved violation{'s' if n != 1 else ''}")

    if not parts:
        return "No changes"

    return ", ".join(parts)
