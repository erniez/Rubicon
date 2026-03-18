"""Tests for rubicon.viz.api — pure JSON serialization functions."""

from pathlib import Path

import networkx as nx
import pytest

from rubicon.models import LayerConfig, Relationship, RelationshipType, RubiconConfig, Severity, Violation
from rubicon.snapshot.diff import SnapshotDiff
from rubicon.viz.api import diff_overlay, file_level_view, layer_summary, ratsnest_view


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_config() -> RubiconConfig:
    """A three-layer config matching the test graph."""
    return RubiconConfig(
        layers={
            "presentation": LayerConfig(directories=["app/ui/"], color="#4A90D9"),
            "domain": LayerConfig(directories=["app/models/"], color="#50C878"),
            "data": LayerConfig(directories=["app/db/"], color="#E8A838"),
        },
        layer_order=["presentation", "domain", "data"],
    )


def _make_graph() -> nx.DiGraph:
    """A small multi-layer graph with known relationships.

    Presentation:
        app/ui/screen.py  -> app/models/user.py  (import)
        app/ui/widget.py  -> app/models/user.py  (ownership)

    Domain:
        app/models/user.py  -> app/models/order.py  (import)
        app/models/order.py -> app/db/repo.py        (import)

    Data:
        app/db/repo.py      -> app/models/user.py    (inheritance)
        app/db/store.py      (orphan, no edges)
    """
    g = nx.DiGraph()

    nodes = [
        ("app/ui/screen.py", "python", "presentation", ["Screen"]),
        ("app/ui/widget.py", "python", "presentation", ["Widget"]),
        ("app/models/user.py", "python", "domain", ["User"]),
        ("app/models/order.py", "python", "domain", ["Order"]),
        ("app/db/repo.py", "python", "data", ["Repo"]),
        ("app/db/store.py", "python", "data", ["Store"]),
    ]
    for node_id, lang, layer, symbols in nodes:
        g.add_node(
            node_id,
            file_path=Path(node_id),
            language=lang,
            layer=layer,
            symbols=symbols,
        )

    edges = [
        ("app/ui/screen.py", "app/models/user.py", [
            Relationship("Screen", "User", RelationshipType.IMPORT, Path("app/ui/screen.py"), 1),
        ]),
        ("app/ui/widget.py", "app/models/user.py", [
            Relationship("Widget", "User", RelationshipType.OWNERSHIP, Path("app/ui/widget.py"), 5),
        ]),
        ("app/models/user.py", "app/models/order.py", [
            Relationship("User", "Order", RelationshipType.IMPORT, Path("app/models/user.py"), 2),
        ]),
        ("app/models/order.py", "app/db/repo.py", [
            Relationship("Order", "Repo", RelationshipType.IMPORT, Path("app/models/order.py"), 1),
        ]),
        ("app/db/repo.py", "app/models/user.py", [
            Relationship("Repo", "User", RelationshipType.INHERITANCE, Path("app/db/repo.py"), 3),
        ]),
    ]
    for src, tgt, rels in edges:
        g.add_edge(src, tgt, relationships=rels)

    return g


def _make_violations(graph: nx.DiGraph) -> list[Violation]:
    """Known violations matching the test graph."""
    return [
        Violation(
            rule="no_upward_dependency",
            severity=Severity.WARNING,
            source_node_id="app/db/repo.py",
            target_node_id="app/models/user.py",
            message="data imports from domain",
            relationship=Relationship(
                "Repo", "User", RelationshipType.INHERITANCE, Path("app/db/repo.py"), 3,
            ),
        ),
        Violation(
            rule="orphan_detection",
            severity=Severity.INFO,
            source_node_id="app/db/store.py",
            target_node_id=None,
            message="app/db/store.py has no connections",
        ),
    ]


# ---------------------------------------------------------------------------
# Test: layer_summary
# ---------------------------------------------------------------------------

class TestLayerSummary:
    def test_returns_correct_layers(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = layer_summary(graph, config, violations)

        layer_names = [l["name"] for l in result["layers"]]
        assert layer_names == ["presentation", "domain", "data"]

    def test_file_counts(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = layer_summary(graph, config, violations)

        counts = {l["name"]: l["file_count"] for l in result["layers"]}
        assert counts["presentation"] == 2
        assert counts["domain"] == 2
        assert counts["data"] == 2

    def test_layer_colors(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = layer_summary(graph, config, [])

        colors = {l["name"]: l["color"] for l in result["layers"]}
        assert colors["presentation"] == "#4A90D9"
        assert colors["domain"] == "#50C878"
        assert colors["data"] == "#E8A838"

    def test_inter_layer_edge_counts(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = layer_summary(graph, config, [])

        edge_lookup = {(e["source"], e["target"]): e for e in result["edges"]}

        # presentation -> domain: 2 edges (screen->user import, widget->user ownership)
        pres_to_domain = edge_lookup.get(("presentation", "domain"))
        assert pres_to_domain is not None
        assert pres_to_domain["count"] == 2

        # domain -> data: 1 edge (order->repo import)
        domain_to_data = edge_lookup.get(("domain", "data"))
        assert domain_to_data is not None
        assert domain_to_data["count"] == 1

        # data -> domain: 1 edge (repo->user inheritance)
        data_to_domain = edge_lookup.get(("data", "domain"))
        assert data_to_domain is not None
        assert data_to_domain["count"] == 1

    def test_relationship_breakdowns(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = layer_summary(graph, config, [])

        edge_lookup = {(e["source"], e["target"]): e for e in result["edges"]}

        pres_to_domain = edge_lookup[("presentation", "domain")]
        assert pres_to_domain["relationships"]["import"] == 1
        assert pres_to_domain["relationships"]["ownership"] == 1

    def test_violation_counts_on_edges(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = layer_summary(graph, config, violations)

        edge_lookup = {(e["source"], e["target"]): e for e in result["edges"]}

        data_to_domain = edge_lookup[("data", "domain")]
        assert data_to_domain["violations"] == 1

        pres_to_domain = edge_lookup[("presentation", "domain")]
        assert pres_to_domain["violations"] == 0

    def test_total_violation_count(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = layer_summary(graph, config, violations)
        assert result["violations"] == 2

    def test_empty_graph(self) -> None:
        graph = nx.DiGraph()
        config = _make_config()

        result = layer_summary(graph, config, [])

        assert result["layers"] == []
        assert result["edges"] == []
        assert result["violations"] == 0

    def test_no_inter_layer_edges(self) -> None:
        """Graph with nodes in one layer only."""
        g = nx.DiGraph()
        g.add_node("a.py", file_path=Path("a.py"), language="python", layer="domain", symbols=[])
        g.add_node("b.py", file_path=Path("b.py"), language="python", layer="domain", symbols=[])
        g.add_edge("a.py", "b.py", relationships=[
            Relationship("A", "B", RelationshipType.IMPORT, Path("a.py"), 1),
        ])

        config = RubiconConfig(
            layers={"domain": LayerConfig(directories=[""], color="#50C878")},
            layer_order=["domain"],
        )

        result = layer_summary(g, config, [])
        assert len(result["edges"]) == 0  # intra-layer edges are excluded


# ---------------------------------------------------------------------------
# Test: file_level_view
# ---------------------------------------------------------------------------

class TestFileLevelView:
    def test_single_layer_returns_correct_nodes(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(graph, config, [], layer="domain")

        node_ids = {n["id"] for n in result["nodes"]}
        assert node_ids == {"app/models/user.py", "app/models/order.py"}

    def test_single_layer_includes_intra_layer_edges(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(graph, config, [], layer="domain")

        edge_pairs = {(e["source"], e["target"]) for e in result["edges"]}
        assert ("app/models/user.py", "app/models/order.py") in edge_pairs

    def test_cross_layer_returns_both_layers_files(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(
            graph, config, [],
            source_layer="presentation",
            target_layer="domain",
        )

        node_ids = {n["id"] for n in result["nodes"]}
        assert "app/ui/screen.py" in node_ids
        assert "app/ui/widget.py" in node_ids
        assert "app/models/user.py" in node_ids
        assert "app/models/order.py" in node_ids

    def test_cross_layer_only_cross_layer_edges(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(
            graph, config, [],
            source_layer="presentation",
            target_layer="domain",
        )

        edge_pairs = {(e["source"], e["target"]) for e in result["edges"]}
        # Cross-layer edges present
        assert ("app/ui/screen.py", "app/models/user.py") in edge_pairs
        assert ("app/ui/widget.py", "app/models/user.py") in edge_pairs
        # Intra-layer edge excluded
        assert ("app/models/user.py", "app/models/order.py") not in edge_pairs

    def test_node_attributes(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(graph, config, [], layer="presentation")

        screen = next(n for n in result["nodes"] if n["id"] == "app/ui/screen.py")
        assert screen["language"] == "python"
        assert screen["layer"] == "presentation"
        assert screen["symbols"] == ["Screen"]

    def test_edge_relationships_serialized(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(graph, config, [], layer="domain")

        edge = next(
            e for e in result["edges"]
            if e["source"] == "app/models/user.py" and e["target"] == "app/models/order.py"
        )
        assert len(edge["relationships"]) == 1
        assert edge["relationships"][0]["type"] == "import"
        assert edge["relationships"][0]["source_symbol"] == "User"
        assert edge["relationships"][0]["target_symbol"] == "Order"

    def test_violations_filtered_to_layer(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = file_level_view(graph, config, violations, layer="data")

        rules = [v["rule"] for v in result["violations"]]
        assert "orphan_detection" in rules
        assert "no_upward_dependency" in rules  # involves data node

    def test_nonexistent_layer_returns_empty(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = file_level_view(graph, config, [], layer="nonexistent")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["violations"] == []


# ---------------------------------------------------------------------------
# Test: ratsnest_view
# ---------------------------------------------------------------------------

class TestRatsnestView:
    def test_returns_focus_node(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "app/models/user.py")

        assert result is not None
        assert result["focus"]["id"] == "app/models/user.py"
        assert result["focus"]["layer"] == "domain"
        assert result["focus"]["symbols"] == ["User"]

    def test_returns_all_neighbors(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "app/models/user.py")

        neighbor_ids = {n["id"] for n in result["neighbors"]}
        # Outbound: user.py -> order.py
        assert "app/models/order.py" in neighbor_ids
        # Inbound: screen.py -> user.py, widget.py -> user.py, repo.py -> user.py
        assert "app/ui/screen.py" in neighbor_ids
        assert "app/ui/widget.py" in neighbor_ids
        assert "app/db/repo.py" in neighbor_ids

    def test_edge_directions(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "app/models/user.py")

        outbound_edges = [e for e in result["edges"] if e["direction"] == "outbound"]
        inbound_edges = [e for e in result["edges"] if e["direction"] == "inbound"]

        assert len(outbound_edges) == 1  # user -> order
        assert outbound_edges[0]["target"] == "app/models/order.py"

        assert len(inbound_edges) == 3  # screen, widget, repo -> user

    def test_neighbor_direction_attribute(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "app/models/user.py")

        direction_map = {n["id"]: n["direction"] for n in result["neighbors"]}
        assert direction_map["app/models/order.py"] == "outbound"
        assert direction_map["app/ui/screen.py"] == "inbound"

    def test_nonexistent_file_returns_none(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "nonexistent.py")

        assert result is None

    def test_orphan_node_returns_empty_neighbors(self) -> None:
        graph = _make_graph()
        config = _make_config()

        result = ratsnest_view(graph, config, [], "app/db/store.py")

        assert result is not None
        assert result["focus"]["id"] == "app/db/store.py"
        assert result["neighbors"] == []
        assert result["edges"] == []

    def test_violations_filtered_to_focus(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = ratsnest_view(graph, config, violations, "app/db/repo.py")

        rules = [v["rule"] for v in result["violations"]]
        assert "no_upward_dependency" in rules

    def test_unrelated_violations_excluded(self) -> None:
        graph = _make_graph()
        config = _make_config()
        violations = _make_violations(graph)

        result = ratsnest_view(graph, config, violations, "app/ui/screen.py")

        rules = [v["rule"] for v in result["violations"]]
        # orphan_detection for store.py should not appear
        assert "orphan_detection" not in rules
        # no_upward_dependency is for repo -> user, not involving screen
        assert "no_upward_dependency" not in rules

    def test_bidirectional_neighbor(self) -> None:
        """If A -> B and B -> A, the neighbor direction should be 'both'."""
        g = nx.DiGraph()
        g.add_node("a.py", file_path=Path("a.py"), language="python", layer="domain", symbols=[])
        g.add_node("b.py", file_path=Path("b.py"), language="python", layer="domain", symbols=[])
        g.add_edge("a.py", "b.py", relationships=[
            Relationship("A", "B", RelationshipType.IMPORT, Path("a.py"), 1),
        ])
        g.add_edge("b.py", "a.py", relationships=[
            Relationship("B", "A", RelationshipType.IMPORT, Path("b.py"), 1),
        ])

        config = RubiconConfig()
        result = ratsnest_view(g, config, [], "a.py")

        neighbor = result["neighbors"][0]
        assert neighbor["id"] == "b.py"
        assert neighbor["direction"] == "both"


# ---------------------------------------------------------------------------
# Test: diff_overlay
# ---------------------------------------------------------------------------

class TestDiffOverlay:
    def test_none_returns_disabled(self) -> None:
        result = diff_overlay(None)

        assert result["enabled"] is False
        assert result["added_edges"] == []
        assert result["removed_edges"] == []
        assert result["summary"] == ""

    def test_with_diff_returns_enabled(self) -> None:
        diff = SnapshotDiff(
            added_edges=[{"source": "a.py", "target": "b.py", "relationships": []}],
            removed_edges=[{"source": "c.py", "target": "d.py", "relationships": []}],
            added_nodes=["e.py"],
            removed_nodes=["f.py"],
            new_violations=[{"rule": "r1", "source_node_id": "a.py", "target_node_id": "b.py", "message": "m"}],
            resolved_violations=[{"rule": "r2", "source_node_id": "c.py", "target_node_id": "d.py", "message": "m"}],
            summary="+1 connection, -1 connection, 1 new violation, 1 resolved violation",
        )

        result = diff_overlay(diff)

        assert result["enabled"] is True
        assert len(result["added_edges"]) == 1
        assert len(result["removed_edges"]) == 1
        assert len(result["added_nodes"]) == 1
        assert len(result["removed_nodes"]) == 1
        assert len(result["new_violations"]) == 1
        assert len(result["resolved_violations"]) == 1
        assert "connection" in result["summary"]

    def test_empty_diff_returns_enabled_with_empty_lists(self) -> None:
        diff = SnapshotDiff(summary="No changes")

        result = diff_overlay(diff)

        assert result["enabled"] is True
        assert result["added_edges"] == []
        assert result["summary"] == "No changes"
