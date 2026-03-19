"""Tests for Mermaid output with diff annotations."""

from pathlib import Path

import networkx as nx

from rubicon.mermaid import generate_mermaid
from rubicon.models import (
    LayerConfig,
    Relationship,
    RelationshipType,
    RubiconConfig,
    Severity,
    Violation,
)
from rubicon.snapshot.diff import SnapshotDiff


def _make_config() -> RubiconConfig:
    return RubiconConfig(
        layers={
            "ui": LayerConfig(directories=["app/ui/"], color="#4A90D9"),
            "domain": LayerConfig(directories=["app/models/"], color="#50C878"),
        },
        layer_order=["ui", "domain"],
    )


def _make_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node("app/ui/screen.py", file_path=Path("app/ui/screen.py"),
               language="python", layer="ui", symbols=[])
    g.add_node("app/models/user.py", file_path=Path("app/models/user.py"),
               language="python", layer="domain", symbols=[])
    g.add_edge("app/ui/screen.py", "app/models/user.py", relationships=[
        Relationship("Screen", "User", RelationshipType.IMPORT,
                     Path("app/ui/screen.py"), 1),
    ])
    return g


class TestMermaidWithoutDiff:
    def test_no_diff_unchanged(self) -> None:
        """Output should be identical to Phase 1 when diff is None."""
        graph = _make_graph()
        config = _make_config()
        output = generate_mermaid(graph, config, [])

        assert "graph TD" in output
        assert "%% Diff" not in output
        assert "NEW" not in output
        assert "REMOVED" not in output


class TestMermaidWithEmptyDiff:
    def test_empty_diff_shows_no_changes(self) -> None:
        graph = _make_graph()
        config = _make_config()
        diff = SnapshotDiff(summary="No changes")
        output = generate_mermaid(graph, config, [], diff=diff)

        assert "%% Diff: No changes" in output
        assert "NEW" not in output
        assert "REMOVED" not in output


class TestMermaidWithAddedEdges:
    def test_new_edge_annotated(self) -> None:
        graph = _make_graph()
        config = _make_config()
        diff = SnapshotDiff(
            added_edges=[{
                "source": "app/ui/screen.py",
                "target": "app/models/user.py",
                "relationships": [{"type": "import", "source": "Screen",
                                   "target": "User", "source_file": "app/ui/screen.py",
                                   "line_number": 1}],
            }],
            summary="+1 connection",
        )
        output = generate_mermaid(graph, config, [], diff=diff)

        assert "%% Diff: +1 connection" in output
        assert "+1 NEW" in output


class TestMermaidWithRemovedEdges:
    def test_removed_edge_annotated(self) -> None:
        graph = _make_graph()
        config = _make_config()
        diff = SnapshotDiff(
            removed_edges=[{
                "source": "app/ui/screen.py",
                "target": "app/models/user.py",
                "relationships": [],
            }],
            summary="-1 connection",
        )
        output = generate_mermaid(graph, config, [], diff=diff)

        assert "%% Diff: -1 connection" in output
        assert "-1 REMOVED" in output


class TestMermaidWithNewViolations:
    def test_diff_summary_includes_violations(self) -> None:
        graph = _make_graph()
        config = _make_config()
        diff = SnapshotDiff(
            new_violations=[{
                "rule": "no_upward_dependency",
                "source_node_id": "app/models/user.py",
                "target_node_id": "app/ui/screen.py",
                "message": "domain imports from ui",
            }],
            summary="1 new violation",
        )
        output = generate_mermaid(graph, config, [], diff=diff)

        assert "%% Diff: 1 new violation" in output
