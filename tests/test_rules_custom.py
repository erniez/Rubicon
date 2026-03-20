"""Tests for custom user-defined architecture rules."""

from pathlib import Path

import networkx as nx

from rubicon.models import (
    CustomRuleConfig,
    Relationship,
    RelationshipType,
    RubiconConfig,
    Severity,
)
from rubicon.rules.custom import run_custom_rules
from rubicon.rules.engine import run_rules


def _make_config(
    custom_rules: list[CustomRuleConfig] | None = None,
) -> RubiconConfig:
    return RubiconConfig(
        layers={},
        layer_order=["presentation", "domain", "data"],
        rules=[],
        custom_rules=custom_rules or [],
    )


def _make_graph(
    nodes: dict[str, str],
    edges: list[tuple[str, str, list[Relationship]]] | None = None,
) -> nx.DiGraph:
    g = nx.DiGraph()
    for node_id, layer in nodes.items():
        g.add_node(node_id, file_path=Path(node_id), language="python", symbols=[], layer=layer)
    for source, target, rels in (edges or []):
        g.add_edge(source, target, relationships=rels)
    return g


def _rel(
    source: str = "a",
    target: str = "b",
    source_file: str = "a.py",
) -> Relationship:
    return Relationship(
        source=source,
        target=target,
        type=RelationshipType.IMPORT,
        source_file=Path(source_file),
        line_number=1,
    )


# ── File-layer constraints ───────────────────────────────────────


class TestFileLayerRule:
    def test_violation_wrong_layer(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
        )
        graph = _make_graph({"ui/HomeViewModel.py": "domain"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 1
        assert violations[0].rule == "viewmodels_in_presentation"
        assert violations[0].source_node_id == "ui/HomeViewModel.py"

    def test_clean_correct_layer(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
        )
        graph = _make_graph({"ui/HomeViewModel.py": "presentation"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 0

    def test_non_matching_files_ignored(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
        )
        graph = _make_graph({"data/UserRepo.py": "data"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 0

    def test_unclassified_files_ignored(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
        )
        graph = _make_graph({"HomeViewModel.py": "unclassified"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 0

    def test_custom_message(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
            message="ViewModels must live in the presentation layer",
        )
        graph = _make_graph({"HomeViewModel.py": "data"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert violations[0].message == "ViewModels must live in the presentation layer"

    def test_custom_severity(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
            severity="error",
        )
        graph = _make_graph({"HomeViewModel.py": "data"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert violations[0].severity == Severity.ERROR

    def test_default_severity_is_warning(self) -> None:
        rule = CustomRuleConfig(
            name="viewmodels_in_presentation",
            pattern="*ViewModel*",
            layer="presentation",
        )
        graph = _make_graph({"HomeViewModel.py": "data"})
        violations = run_custom_rules(graph, _make_config([rule]))
        assert violations[0].severity == Severity.WARNING


# ── Forbidden imports ────────────────────────────────────────────


class TestForbiddenImportsRule:
    def test_violation_forbidden_import(self) -> None:
        rule = CustomRuleConfig(
            name="no_database_in_domain",
            source_layer="domain",
            forbidden_imports=["sqlalchemy"],
        )
        graph = _make_graph(
            {"domain/service.py": "domain", "data/db.py": "data"},
            [("domain/service.py", "data/db.py", [_rel(
                source="domain/service.py", target="sqlalchemy.orm",
            )])],
        )
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 1
        assert violations[0].rule == "no_database_in_domain"

    def test_clean_no_forbidden_import(self) -> None:
        rule = CustomRuleConfig(
            name="no_database_in_domain",
            source_layer="domain",
            forbidden_imports=["sqlalchemy"],
        )
        graph = _make_graph(
            {"domain/service.py": "domain", "domain/model.py": "domain"},
            [("domain/service.py", "domain/model.py", [_rel(
                source="domain/service.py", target="domain.model",
            )])],
        )
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 0

    def test_other_layer_not_checked(self) -> None:
        rule = CustomRuleConfig(
            name="no_database_in_domain",
            source_layer="domain",
            forbidden_imports=["sqlalchemy"],
        )
        graph = _make_graph(
            {"data/repo.py": "data", "data/db.py": "data"},
            [("data/repo.py", "data/db.py", [_rel(
                source="data/repo.py", target="sqlalchemy.orm",
            )])],
        )
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 0

    def test_multiple_forbidden_patterns(self) -> None:
        rule = CustomRuleConfig(
            name="no_database_in_domain",
            source_layer="domain",
            forbidden_imports=["sqlalchemy", "django.db"],
        )
        graph = _make_graph(
            {"domain/a.py": "domain", "data/b.py": "data"},
            [("domain/a.py", "data/b.py", [_rel(
                source="domain/a.py", target="django.db.models",
            )])],
        )
        violations = run_custom_rules(graph, _make_config([rule]))
        assert len(violations) == 1

    def test_forbidden_import_includes_relationship(self) -> None:
        rule = CustomRuleConfig(
            name="no_database_in_domain",
            source_layer="domain",
            forbidden_imports=["sqlalchemy"],
        )
        graph = _make_graph(
            {"domain/service.py": "domain", "data/db.py": "data"},
            [("domain/service.py", "data/db.py", [_rel(
                source="domain/service.py", target="sqlalchemy.orm",
            )])],
        )
        violations = run_custom_rules(graph, _make_config([rule]))
        assert violations[0].relationship is not None


# ── Multiple rules ───────────────────────────────────────────────


class TestMultipleCustomRules:
    def test_runs_all_custom_rules(self) -> None:
        rules = [
            CustomRuleConfig(
                name="viewmodels_in_presentation",
                pattern="*ViewModel*",
                layer="presentation",
            ),
            CustomRuleConfig(
                name="no_database_in_domain",
                source_layer="domain",
                forbidden_imports=["sqlalchemy"],
            ),
        ]
        graph = _make_graph(
            {"HomeViewModel.py": "data", "domain/svc.py": "domain", "data/db.py": "data"},
            [("domain/svc.py", "data/db.py", [_rel(
                source="domain/svc.py", target="sqlalchemy.orm",
            )])],
        )
        violations = run_custom_rules(graph, _make_config(rules))
        rule_names = {v.rule for v in violations}
        assert "viewmodels_in_presentation" in rule_names
        assert "no_database_in_domain" in rule_names


# ── Engine integration ───────────────────────────────────────────


class TestEngineIntegration:
    def test_custom_rules_run_via_engine(self) -> None:
        config = RubiconConfig(
            layers={},
            layer_order=["presentation", "domain", "data"],
            rules=["orphan_detection"],
            custom_rules=[
                CustomRuleConfig(
                    name="viewmodels_in_presentation",
                    pattern="*ViewModel*",
                    layer="presentation",
                ),
            ],
        )
        graph = _make_graph({"HomeViewModel.py": "data"})
        violations = run_rules(graph, config)
        rule_names = {v.rule for v in violations}
        assert "orphan_detection" in rule_names
        assert "viewmodels_in_presentation" in rule_names

    def test_no_custom_rules_no_error(self) -> None:
        config = RubiconConfig(
            layers={},
            layer_order=["presentation", "domain", "data"],
            rules=["orphan_detection"],
            custom_rules=[],
        )
        graph = _make_graph({"a.py": "domain"})
        violations = run_rules(graph, config)
        assert all(v.rule == "orphan_detection" for v in violations)
