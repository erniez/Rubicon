"""Tests for adjacent/grouped layers in layer_order."""

from pathlib import Path

import networkx as nx

from rubicon.models import (
    LayerConfig,
    Relationship,
    RelationshipType,
    RubiconConfig,
    Severity,
    Violation,
)
from rubicon.classifier.config import load_config
from rubicon.export import export_svg
from rubicon.mermaid import generate_mermaid
from rubicon.rules.builtin import no_upward_dependency, no_layer_skipping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grouped_config() -> RubiconConfig:
    return RubiconConfig(
        layers={
            "presentation": LayerConfig(directories=["ui/"], color="#4A90D9"),
            "domain": LayerConfig(directories=["domain/"], color="#50C878"),
            "networking": LayerConfig(directories=["net/"], color="#D94A4A"),
            "utilities": LayerConfig(directories=["util/"], color="#888888"),
            "configuration": LayerConfig(directories=["config/"], color="#AAAAAA"),
        },
        layer_order=[
            "presentation",
            "domain",
            ["networking", "utilities", "configuration"],
        ],
    )


def _make_graph(nodes: dict[str, str], edges: list[tuple[str, str]] | None = None) -> nx.DiGraph:
    g = nx.DiGraph()
    for node_id, layer in nodes.items():
        g.add_node(node_id, file_path=Path(node_id), language="python", layer=layer, symbols=[])
    for source, target in (edges or []):
        g.add_edge(source, target, relationships=[
            Relationship(source, target, RelationshipType.IMPORT, Path(source), 1),
        ])
    return g


# ---------------------------------------------------------------------------
# Model: layer_index
# ---------------------------------------------------------------------------

class TestLayerIndex:
    def test_flat_layer_has_index(self) -> None:
        config = _grouped_config()
        assert config.layer_index("presentation") == 0
        assert config.layer_index("domain") == 1

    def test_grouped_layers_share_index(self) -> None:
        config = _grouped_config()
        assert config.layer_index("networking") == 2
        assert config.layer_index("utilities") == 2
        assert config.layer_index("configuration") == 2

    def test_unknown_layer_returns_none(self) -> None:
        config = _grouped_config()
        assert config.layer_index("nonexistent") is None


class TestFlatLayerOrder:
    def test_flattens_groups(self) -> None:
        config = _grouped_config()
        assert config.flat_layer_order == [
            "presentation", "domain", "networking", "utilities", "configuration",
        ]

    def test_flat_only(self) -> None:
        config = RubiconConfig(layer_order=["a", "b", "c"])
        assert config.flat_layer_order == ["a", "b", "c"]


class TestLayerRows:
    def test_returns_rows(self) -> None:
        config = _grouped_config()
        assert config.layer_rows == [
            ["presentation"],
            ["domain"],
            ["networking", "utilities", "configuration"],
        ]

    def test_flat_layers_are_single_item_rows(self) -> None:
        config = RubiconConfig(layer_order=["a", "b"])
        assert config.layer_rows == [["a"], ["b"]]


# ---------------------------------------------------------------------------
# Rules: grouped layers treated as same level
# ---------------------------------------------------------------------------

class TestRulesWithGroups:
    def test_same_group_no_upward_violation(self) -> None:
        """Layers in the same group should not trigger upward dependency."""
        config = _grouped_config()
        graph = _make_graph(
            {"net/api.py": "networking", "util/helpers.py": "utilities"},
            [("net/api.py", "util/helpers.py")],
        )
        violations = no_upward_dependency(graph, config)
        assert len(violations) == 0

    def test_same_group_no_layer_skipping(self) -> None:
        """Layers in the same group should not trigger layer skipping."""
        config = _grouped_config()
        graph = _make_graph(
            {"net/api.py": "networking", "config/settings.py": "configuration"},
            [("net/api.py", "config/settings.py")],
        )
        violations = no_layer_skipping(graph, config)
        assert len(violations) == 0

    def test_upward_from_group_to_higher_layer(self) -> None:
        """A grouped layer importing upward should still be flagged."""
        config = _grouped_config()
        graph = _make_graph(
            {"util/helpers.py": "utilities", "ui/screen.py": "presentation"},
            [("util/helpers.py", "ui/screen.py")],
        )
        violations = no_upward_dependency(graph, config)
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

class TestConfigParsing:
    def test_loads_grouped_layer_order(self, tmp_path: Path) -> None:
        (tmp_path / ".rubicon").write_text(
            "layer_order:\n"
            "  - presentation\n"
            "  - domain\n"
            "  - [networking, utilities]\n"
        )
        config = load_config(tmp_path)
        assert config.layer_order == [
            "presentation",
            "domain",
            ["networking", "utilities"],
        ]

    def test_flat_config_still_works(self, tmp_path: Path) -> None:
        (tmp_path / ".rubicon").write_text(
            "layer_order:\n"
            "  - presentation\n"
            "  - domain\n"
        )
        config = load_config(tmp_path)
        assert config.layer_order == ["presentation", "domain"]


# ---------------------------------------------------------------------------
# Mermaid: groups in subgraph
# ---------------------------------------------------------------------------

class TestMermaidGroups:
    def test_grouped_layers_in_subgraph(self) -> None:
        config = _grouped_config()
        graph = _make_graph({
            "ui/screen.py": "presentation",
            "net/api.py": "networking",
            "util/helpers.py": "utilities",
        })
        result = generate_mermaid(graph, config, [])
        assert "subgraph" in result
        assert "direction LR" in result

    def test_flat_layers_no_subgraph(self) -> None:
        config = RubiconConfig(
            layers={"a": LayerConfig(), "b": LayerConfig()},
            layer_order=["a", "b"],
        )
        graph = _make_graph({"x.py": "a", "y.py": "b"})
        result = generate_mermaid(graph, config, [])
        assert "subgraph" not in result


# ---------------------------------------------------------------------------
# SVG export: grouped bands side-by-side
# ---------------------------------------------------------------------------

class TestSvgGroups:
    def test_grouped_layers_all_appear(self) -> None:
        config = _grouped_config()
        graph = _make_graph({
            "ui/screen.py": "presentation",
            "net/api.py": "networking",
            "util/helpers.py": "utilities",
            "config/settings.py": "configuration",
        })
        result = export_svg(graph, config, [])
        assert "PRESENTATION" in result
        assert "NETWORKING" in result
        assert "UTILITIES" in result
        assert "CONFIGURATION" in result

    def test_valid_svg_with_groups(self) -> None:
        config = _grouped_config()
        graph = _make_graph({
            "ui/screen.py": "presentation",
            "net/api.py": "networking",
        })
        result = export_svg(graph, config, [])
        assert result.startswith("<?xml")
        assert "</svg>" in result
