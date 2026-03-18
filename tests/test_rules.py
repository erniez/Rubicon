"""Tests for the rule engine and all 6 built-in rules."""

from pathlib import Path

import networkx as nx

from rubicon.models import LayerConfig, Relationship, RelationshipType, RubiconConfig, Severity
from rubicon.rules.builtin import (
    dependency_inversion,
    inheritance_flows_downward,
    no_circular_imports,
    no_circular_ownership,
    no_layer_skipping,
    no_upward_dependency,
    orphan_detection,
    single_responsibility,
)
from rubicon.rules.engine import run_rules


def _make_config(
    layer_order: list[str] | None = None,
    rules: list[str] | None = None,
) -> RubiconConfig:
    return RubiconConfig(
        layers={},
        layer_order=layer_order or ["presentation", "domain", "data", "networking"],
        rules=rules or [
            "no_upward_dependency",
            "no_layer_skipping",
            "inheritance_flows_downward",
            "no_circular_ownership",
            "single_responsibility",
            "orphan_detection",
        ],
    )


def _make_graph(
    nodes: dict[str, str],
    edges: list[tuple[str, str, list[Relationship]]],
) -> nx.DiGraph:
    """Build a test graph.

    Args:
        nodes: Mapping of node_id → layer name.
        edges: List of (source_id, target_id, relationships).
    """
    g = nx.DiGraph()
    for node_id, layer in nodes.items():
        g.add_node(node_id, file_path=Path(node_id), language="python", symbols=[], layer=layer)
    for source, target, rels in edges:
        g.add_edge(source, target, relationships=rels)
    return g


def _rel(
    rtype: RelationshipType,
    source_file: str = "a.py",
    line: int = 1,
    source: str = "a",
    target: str = "b",
) -> Relationship:
    return Relationship(
        source=source,
        target=target,
        type=rtype,
        source_file=Path(source_file),
        line_number=line,
    )


# ── no_upward_dependency ──────────────────────────────────────────


class TestNoUpwardDependency:
    def test_clean_downward_import(self) -> None:
        graph = _make_graph(
            {"ui/screen.py": "presentation", "domain/model.py": "domain"},
            [("ui/screen.py", "domain/model.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_upward_dependency(graph, _make_config())
        assert len(violations) == 0

    def test_violation_upward_import(self) -> None:
        graph = _make_graph(
            {"data/store.py": "data", "ui/screen.py": "presentation"},
            [("data/store.py", "ui/screen.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_upward_dependency(graph, _make_config())
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert violations[0].rule == "no_upward_dependency"

    def test_same_layer_no_violation(self) -> None:
        graph = _make_graph(
            {"domain/a.py": "domain", "domain/b.py": "domain"},
            [("domain/a.py", "domain/b.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_upward_dependency(graph, _make_config())
        assert len(violations) == 0

    def test_ignores_non_import_relationships(self) -> None:
        graph = _make_graph(
            {"data/store.py": "data", "ui/screen.py": "presentation"},
            [("data/store.py", "ui/screen.py", [_rel(RelationshipType.OWNERSHIP)])],
        )
        violations = no_upward_dependency(graph, _make_config())
        assert len(violations) == 0

    def test_ignores_unclassified_layers(self) -> None:
        graph = _make_graph(
            {"a.py": "unclassified", "ui/screen.py": "presentation"},
            [("a.py", "ui/screen.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_upward_dependency(graph, _make_config())
        assert len(violations) == 0


# ── no_layer_skipping ─────────────────────────────────────────────


class TestNoLayerSkipping:
    def test_clean_adjacent_layers(self) -> None:
        graph = _make_graph(
            {"ui/screen.py": "presentation", "domain/model.py": "domain"},
            [("ui/screen.py", "domain/model.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_layer_skipping(graph, _make_config())
        assert len(violations) == 0

    def test_violation_skipping_layer(self) -> None:
        graph = _make_graph(
            {"ui/screen.py": "presentation", "data/store.py": "data"},
            [("ui/screen.py", "data/store.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_layer_skipping(graph, _make_config())
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "skipping" in violations[0].message

    def test_same_layer_no_violation(self) -> None:
        graph = _make_graph(
            {"domain/a.py": "domain", "domain/b.py": "domain"},
            [("domain/a.py", "domain/b.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_layer_skipping(graph, _make_config())
        assert len(violations) == 0

    def test_skipping_in_reverse_direction(self) -> None:
        # networking → presentation skips data and domain
        graph = _make_graph(
            {"net/api.py": "networking", "ui/screen.py": "presentation"},
            [("net/api.py", "ui/screen.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = no_layer_skipping(graph, _make_config())
        assert len(violations) == 1


# ── inheritance_flows_downward ────────────────────────────────────


class TestInheritanceFlowsDownward:
    def test_clean_downward_inheritance(self) -> None:
        # data(2) inherits from domain(1) — A is below B, OK
        graph = _make_graph(
            {"data/repo.py": "data", "domain/base.py": "domain"},
            [("data/repo.py", "domain/base.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = inheritance_flows_downward(graph, _make_config())
        assert len(violations) == 0

    def test_clean_same_layer_inheritance(self) -> None:
        graph = _make_graph(
            {"domain/a.py": "domain", "domain/b.py": "domain"},
            [("domain/a.py", "domain/b.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = inheritance_flows_downward(graph, _make_config())
        assert len(violations) == 0

    def test_violation_upward_inheritance(self) -> None:
        # presentation(0) inherits from data(2) — A is above B, violation
        graph = _make_graph(
            {"ui/view.py": "presentation", "data/repo.py": "data"},
            [("ui/view.py", "data/repo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = inheritance_flows_downward(graph, _make_config())
        assert len(violations) == 1
        assert violations[0].severity == Severity.ERROR
        assert violations[0].rule == "inheritance_flows_downward"

    def test_ignores_non_inheritance(self) -> None:
        graph = _make_graph(
            {"ui/view.py": "presentation", "data/repo.py": "data"},
            [("ui/view.py", "data/repo.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = inheritance_flows_downward(graph, _make_config())
        assert len(violations) == 0


# ── no_circular_ownership ────────────────────────────────────────


class TestNoCircularOwnership:
    def test_clean_no_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain", "c.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.OWNERSHIP)]),
                ("b.py", "c.py", [_rel(RelationshipType.OWNERSHIP)]),
            ],
        )
        violations = no_circular_ownership(graph, _make_config())
        assert len(violations) == 0

    def test_violation_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain", "c.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.OWNERSHIP)]),
                ("b.py", "c.py", [_rel(RelationshipType.OWNERSHIP)]),
                ("c.py", "a.py", [_rel(RelationshipType.OWNERSHIP)]),
            ],
        )
        violations = no_circular_ownership(graph, _make_config())
        assert len(violations) >= 1
        assert violations[0].severity == Severity.ERROR
        assert "Circular ownership" in violations[0].message

    def test_self_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain"},
            [("a.py", "a.py", [_rel(RelationshipType.OWNERSHIP)])],
        )
        violations = no_circular_ownership(graph, _make_config())
        assert len(violations) >= 1

    def test_ignores_import_cycles(self) -> None:
        # Import cycles are fine — only ownership cycles matter
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("b.py", "a.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = no_circular_ownership(graph, _make_config())
        assert len(violations) == 0


# ── no_circular_imports ───────────────────────────────────────────


class TestNoCircularImports:
    def test_clean_no_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain", "c.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("b.py", "c.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = no_circular_imports(graph, _make_config())
        assert len(violations) == 0

    def test_violation_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain", "c.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("b.py", "c.py", [_rel(RelationshipType.IMPORT)]),
                ("c.py", "a.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = no_circular_imports(graph, _make_config())
        assert len(violations) >= 1
        assert violations[0].severity == Severity.WARNING
        assert "Circular import" in violations[0].message

    def test_two_node_cycle(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("b.py", "a.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = no_circular_imports(graph, _make_config())
        assert len(violations) >= 1

    def test_ignores_ownership_cycles(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain"},
            [
                ("a.py", "b.py", [_rel(RelationshipType.OWNERSHIP)]),
                ("b.py", "a.py", [_rel(RelationshipType.OWNERSHIP)]),
            ],
        )
        violations = no_circular_imports(graph, _make_config())
        assert len(violations) == 0


# ── dependency_inversion ──────────────────────────────────────────


class TestDependencyInversion:
    def test_clean_inherits_from_abstraction(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/base_repo.py": "data"},
            [("domain/service.py", "data/base_repo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        # "base_repo" contains "base" — looks like an abstraction
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_clean_abstract_prefix(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/AbstractRepo.py": "data"},
            [("domain/service.py", "data/AbstractRepo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_clean_protocol_in_name(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/RepoProtocol.py": "data"},
            [("domain/service.py", "data/RepoProtocol.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_clean_interface_prefix(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/IRepository.py": "data"},
            [("domain/service.py", "data/IRepository.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_violation_concrete_cross_layer(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/user_repo.py": "data"},
            [("domain/service.py", "data/user_repo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 1
        assert violations[0].severity == Severity.INFO
        assert "abstraction" in violations[0].message

    def test_same_layer_no_violation(self) -> None:
        # Concrete-to-concrete within the same layer is fine
        graph = _make_graph(
            {"domain/a.py": "domain", "domain/b.py": "domain"},
            [("domain/a.py", "domain/b.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_ignores_non_inheritance(self) -> None:
        graph = _make_graph(
            {"domain/service.py": "domain", "data/user_repo.py": "data"},
            [("domain/service.py", "data/user_repo.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_ignores_unclassified(self) -> None:
        graph = _make_graph(
            {"a.py": "unclassified", "data/repo.py": "data"},
            [("a.py", "data/repo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0

    def test_clean_symbol_is_abstraction(self) -> None:
        # The file name is concrete but the symbol list indicates an abstraction
        graph = _make_graph(
            {"domain/service.py": "domain", "data/repo.py": "data"},
            [("domain/service.py", "data/repo.py", [_rel(RelationshipType.INHERITANCE)])],
        )
        graph.nodes["data/repo.py"]["symbols"] = ["BaseRepository"]
        violations = dependency_inversion(graph, _make_config())
        assert len(violations) == 0


# ── single_responsibility ────────────────────────────────────────


class TestSingleResponsibility:
    def test_clean_few_layers(self) -> None:
        graph = _make_graph(
            {"hub.py": "domain", "a.py": "presentation", "b.py": "data"},
            [
                ("hub.py", "a.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "b.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = single_responsibility(graph, _make_config())
        assert len(violations) == 0

    def test_violation_many_layers(self) -> None:
        graph = _make_graph(
            {
                "hub.py": "domain",
                "a.py": "presentation",
                "b.py": "data",
                "c.py": "networking",
                "d.py": "domain",
            },
            [
                ("hub.py", "a.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "c.py", [_rel(RelationshipType.IMPORT)]),
                ("d.py", "hub.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = single_responsibility(graph, _make_config())
        hub_violations = [v for v in violations if v.source_node_id == "hub.py"]
        assert len(hub_violations) == 1
        assert hub_violations[0].severity == Severity.INFO

    def test_ignores_unclassified_connections(self) -> None:
        graph = _make_graph(
            {"hub.py": "domain", "a.py": "unclassified", "b.py": "unclassified", "c.py": "unclassified", "d.py": "unclassified"},
            [
                ("hub.py", "a.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "b.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "c.py", [_rel(RelationshipType.IMPORT)]),
                ("hub.py", "d.py", [_rel(RelationshipType.IMPORT)]),
            ],
        )
        violations = single_responsibility(graph, _make_config())
        assert len(violations) == 0


# ── orphan_detection ─────────────────────────────────────────────


class TestOrphanDetection:
    def test_clean_connected_file(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain"},
            [("a.py", "b.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = orphan_detection(graph, _make_config())
        assert len(violations) == 0

    def test_violation_orphan(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain", "orphan.py": "domain"},
            [("a.py", "b.py", [_rel(RelationshipType.IMPORT)])],
        )
        violations = orphan_detection(graph, _make_config())
        assert len(violations) == 1
        assert violations[0].source_node_id == "orphan.py"
        assert violations[0].severity == Severity.INFO

    def test_incoming_edge_prevents_orphan(self) -> None:
        graph = _make_graph(
            {"a.py": "domain", "b.py": "domain"},
            [("a.py", "b.py", [_rel(RelationshipType.IMPORT)])],
        )
        # b.py has an incoming edge, so not an orphan
        violations = orphan_detection(graph, _make_config())
        orphan_ids = {v.source_node_id for v in violations}
        assert "b.py" not in orphan_ids


# ── Engine ───────────────────────────────────────────────────────


class TestEngine:
    def test_runs_only_enabled_rules(self) -> None:
        graph = _make_graph(
            {"orphan.py": "domain"},
            [],
        )
        # Only enable orphan_detection
        config = _make_config(rules=["orphan_detection"])
        violations = run_rules(graph, config)
        assert len(violations) == 1
        assert violations[0].rule == "orphan_detection"

    def test_skips_unknown_rules(self) -> None:
        graph = _make_graph({"a.py": "domain"}, [])
        config = _make_config(rules=["nonexistent_rule"])
        violations = run_rules(graph, config)
        assert len(violations) == 0

    def test_collects_from_multiple_rules(self) -> None:
        # An orphan in data layer importing from presentation — hits multiple rules
        graph = _make_graph(
            {
                "data/store.py": "data",
                "ui/screen.py": "presentation",
                "orphan.py": "domain",
            },
            [("data/store.py", "ui/screen.py", [_rel(RelationshipType.IMPORT)])],
        )
        config = _make_config(rules=[
            "no_upward_dependency",
            "orphan_detection",
        ])
        violations = run_rules(graph, config)
        rules_hit = {v.rule for v in violations}
        assert "no_upward_dependency" in rules_hit
        assert "orphan_detection" in rules_hit
