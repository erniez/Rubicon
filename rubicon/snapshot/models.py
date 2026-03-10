"""Snapshot data model and serialization helpers."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from rubicon.classifier.config import RubiconConfig
from rubicon.graph.models import RelationshipType, Severity, Violation


@dataclass
class Snapshot:
    """Full graph state captured at a point in time."""

    timestamp: datetime
    commit_hash: str | None
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    layer_map: dict[str, str] = field(default_factory=dict)


def graph_to_snapshot(
    graph: nx.DiGraph,
    violations: list[Violation],
    config: RubiconConfig,
    commit_hash: str | None = None,
) -> Snapshot:
    """Create a snapshot from the current graph state."""
    nodes: list[dict] = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "file_path": str(attrs.get("file_path", node_id)),
            "language": attrs.get("language", ""),
            "layer": attrs.get("layer", "unclassified"),
            "symbols": list(attrs.get("symbols", [])),
        })

    edges: list[dict] = []
    for source_id, target_id, data in graph.edges(data=True):
        rels = []
        for rel in data.get("relationships", []):
            rels.append(_serialize_relationship(rel))
        edges.append({
            "source": source_id,
            "target": target_id,
            "relationships": rels,
        })

    serialized_violations = [_serialize_violation(v) for v in violations]

    layer_map: dict[str, str] = {}
    for node_id in graph.nodes:
        layer_map[node_id] = graph.nodes[node_id].get("layer", "unclassified")

    return Snapshot(
        timestamp=datetime.now(timezone.utc),
        commit_hash=commit_hash,
        nodes=nodes,
        edges=edges,
        violations=serialized_violations,
        layer_map=layer_map,
    )


def snapshot_to_dict(snapshot: Snapshot) -> dict:
    """Serialize a Snapshot to a JSON-safe dict."""
    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "commit_hash": snapshot.commit_hash,
        "nodes": snapshot.nodes,
        "edges": snapshot.edges,
        "violations": snapshot.violations,
        "layer_map": snapshot.layer_map,
    }


def dict_to_snapshot(data: dict) -> Snapshot:
    """Deserialize a dict back into a Snapshot."""
    return Snapshot(
        timestamp=datetime.fromisoformat(data["timestamp"]),
        commit_hash=data.get("commit_hash"),
        nodes=data.get("nodes", []),
        edges=data.get("edges", []),
        violations=data.get("violations", []),
        layer_map=data.get("layer_map", {}),
    )


def _serialize_relationship(rel) -> dict:
    """Serialize a Relationship to a JSON-safe dict."""
    return {
        "source": rel.source,
        "target": rel.target,
        "type": rel.type.value,
        "source_file": str(rel.source_file),
        "line_number": rel.line_number,
    }


def _serialize_violation(v: Violation) -> dict:
    """Serialize a Violation to a JSON-safe dict."""
    result: dict = {
        "rule": v.rule,
        "severity": v.severity.value,
        "source_node_id": v.source_node_id,
        "target_node_id": v.target_node_id,
        "message": v.message,
    }
    if v.relationship is not None:
        result["relationship"] = _serialize_relationship(v.relationship)
    else:
        result["relationship"] = None
    return result
