"""Tests for snapshot data model and serialization."""

import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from rubicon.classifier.config import RubiconConfig
from rubicon.graph.models import (
    Relationship,
    RelationshipType,
    Severity,
    Violation,
)
from rubicon.snapshot.models import (
    Snapshot,
    dict_to_snapshot,
    graph_to_snapshot,
    snapshot_to_dict,
)


def _make_graph() -> nx.DiGraph:
    """Build a small test graph with known nodes and edges."""
    graph = nx.DiGraph()
    graph.add_node(
        "app/ui/screen.py",
        file_path=Path("app/ui/screen.py"),
        language="python",
        symbols=["Screen"],
        layer="presentation",
    )
    graph.add_node(
        "app/models/user.py",
        file_path=Path("app/models/user.py"),
        language="python",
        symbols=["User"],
        layer="domain",
    )
    graph.add_node(
        "app/db/repo.py",
        file_path=Path("app/db/repo.py"),
        language="python",
        symbols=["UserRepo"],
        layer="data",
    )
    rel = Relationship(
        source="Screen",
        target="User",
        type=RelationshipType.IMPORT,
        source_file=Path("app/ui/screen.py"),
        line_number=3,
    )
    graph.add_edge(
        "app/ui/screen.py",
        "app/models/user.py",
        relationships=[rel],
    )
    return graph


def _make_violations() -> list[Violation]:
    return [
        Violation(
            rule="no_upward_dependency",
            severity=Severity.WARNING,
            source_node_id="app/db/repo.py",
            target_node_id="app/ui/screen.py",
            message="data layer imports from presentation layer",
            relationship=Relationship(
                source="UserRepo",
                target="Screen",
                type=RelationshipType.IMPORT,
                source_file=Path("app/db/repo.py"),
                line_number=5,
            ),
        ),
    ]


def _make_config() -> RubiconConfig:
    return RubiconConfig(
        layer_order=["presentation", "domain", "data"],
    )


class TestGraphToSnapshot:
    def test_creates_snapshot_with_all_fields(self) -> None:
        graph = _make_graph()
        violations = _make_violations()
        config = _make_config()

        snapshot = graph_to_snapshot(graph, violations, config, commit_hash="abc123")

        assert snapshot.commit_hash == "abc123"
        assert snapshot.timestamp.tzinfo is not None
        assert len(snapshot.nodes) == 3
        assert len(snapshot.edges) == 1
        assert len(snapshot.violations) == 1

    def test_nodes_serialized_correctly(self) -> None:
        graph = _make_graph()
        snapshot = graph_to_snapshot(graph, [], _make_config())

        node_ids = {n["id"] for n in snapshot.nodes}
        assert node_ids == {
            "app/ui/screen.py",
            "app/models/user.py",
            "app/db/repo.py",
        }

        screen = next(n for n in snapshot.nodes if n["id"] == "app/ui/screen.py")
        assert screen["language"] == "python"
        assert screen["layer"] == "presentation"
        assert screen["symbols"] == ["Screen"]
        assert screen["file_path"] == "app/ui/screen.py"

    def test_edges_serialized_correctly(self) -> None:
        graph = _make_graph()
        snapshot = graph_to_snapshot(graph, [], _make_config())

        assert len(snapshot.edges) == 1
        edge = snapshot.edges[0]
        assert edge["source"] == "app/ui/screen.py"
        assert edge["target"] == "app/models/user.py"
        assert len(edge["relationships"]) == 1
        rel = edge["relationships"][0]
        assert rel["type"] == "import"
        assert rel["source_file"] == "app/ui/screen.py"
        assert rel["line_number"] == 3

    def test_violations_serialized_correctly(self) -> None:
        graph = _make_graph()
        violations = _make_violations()
        snapshot = graph_to_snapshot(graph, violations, _make_config())

        v = snapshot.violations[0]
        assert v["rule"] == "no_upward_dependency"
        assert v["severity"] == "warning"
        assert v["source_node_id"] == "app/db/repo.py"
        assert v["target_node_id"] == "app/ui/screen.py"
        assert v["relationship"] is not None
        assert v["relationship"]["type"] == "import"

    def test_layer_map_populated(self) -> None:
        graph = _make_graph()
        snapshot = graph_to_snapshot(graph, [], _make_config())

        assert snapshot.layer_map["app/ui/screen.py"] == "presentation"
        assert snapshot.layer_map["app/models/user.py"] == "domain"
        assert snapshot.layer_map["app/db/repo.py"] == "data"

    def test_commit_hash_none(self) -> None:
        graph = _make_graph()
        snapshot = graph_to_snapshot(graph, [], _make_config(), commit_hash=None)

        assert snapshot.commit_hash is None

    def test_empty_graph(self) -> None:
        graph = nx.DiGraph()
        snapshot = graph_to_snapshot(graph, [], _make_config())

        assert snapshot.nodes == []
        assert snapshot.edges == []
        assert snapshot.violations == []
        assert snapshot.layer_map == {}

    def test_violation_without_relationship(self) -> None:
        graph = _make_graph()
        violations = [
            Violation(
                rule="orphan_detection",
                severity=Severity.INFO,
                source_node_id="app/db/repo.py",
                target_node_id=None,
                message="app/db/repo.py has no connections",
            ),
        ]
        snapshot = graph_to_snapshot(graph, violations, _make_config())

        v = snapshot.violations[0]
        assert v["target_node_id"] is None
        assert v["relationship"] is None


class TestRoundTrip:
    def test_snapshot_to_dict_and_back(self) -> None:
        graph = _make_graph()
        violations = _make_violations()
        original = graph_to_snapshot(graph, violations, _make_config(), commit_hash="abc123")

        data = snapshot_to_dict(original)
        restored = dict_to_snapshot(data)

        assert restored.commit_hash == original.commit_hash
        assert restored.timestamp == original.timestamp
        assert restored.nodes == original.nodes
        assert restored.edges == original.edges
        assert restored.violations == original.violations
        assert restored.layer_map == original.layer_map

    def test_json_serializable(self) -> None:
        graph = _make_graph()
        violations = _make_violations()
        snapshot = graph_to_snapshot(graph, violations, _make_config(), commit_hash="abc123")

        data = snapshot_to_dict(snapshot)
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        restored = dict_to_snapshot(parsed)

        assert restored.nodes == snapshot.nodes
        assert restored.edges == snapshot.edges
        assert restored.violations == snapshot.violations

    def test_round_trip_empty_snapshot(self) -> None:
        original = Snapshot(
            timestamp=datetime.now(timezone.utc),
            commit_hash=None,
            nodes=[],
            edges=[],
            violations=[],
            layer_map={},
        )
        data = snapshot_to_dict(original)
        restored = dict_to_snapshot(data)

        assert restored.commit_hash is None
        assert restored.nodes == []
        assert restored.edges == []

    def test_round_trip_preserves_timestamp_timezone(self) -> None:
        graph = _make_graph()
        original = graph_to_snapshot(graph, [], _make_config())

        data = snapshot_to_dict(original)
        restored = dict_to_snapshot(data)

        assert restored.timestamp.tzinfo is not None
        assert restored.timestamp == original.timestamp
