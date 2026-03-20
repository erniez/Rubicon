"""Tests for the SVG export module."""

from pathlib import Path
from xml.etree import ElementTree as ET

import networkx as nx

from rubicon.export import export_svg, export_to_file
from rubicon.models import (
    LayerConfig,
    Relationship,
    RelationshipType,
    RubiconConfig,
    Severity,
    Violation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    g.add_node("app/ui/screen.py", file_path=Path("app/ui/screen.py"), language="python", layer="ui", symbols=[])
    g.add_node("app/models/user.py", file_path=Path("app/models/user.py"), language="python", layer="domain", symbols=[])
    g.add_edge(
        "app/ui/screen.py", "app/models/user.py",
        relationships=[Relationship("Screen", "User", RelationshipType.IMPORT, Path("app/ui/screen.py"), 1)],
    )
    return g


def _make_graph_with_violation() -> tuple[nx.DiGraph, list[Violation]]:
    g = _make_graph()
    g.add_edge(
        "app/models/user.py", "app/ui/screen.py",
        relationships=[Relationship("User", "Screen", RelationshipType.IMPORT, Path("app/models/user.py"), 5)],
    )
    violations = [
        Violation(
            rule="no_upward_dependency",
            severity=Severity.ERROR,
            source_node_id="app/models/user.py",
            target_node_id="app/ui/screen.py",
            message="domain imports from ui",
        ),
    ]
    return g, violations


# ---------------------------------------------------------------------------
# TestExportSvg
# ---------------------------------------------------------------------------

class TestExportSvg:
    def test_returns_valid_svg(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert result.startswith("<?xml")
        assert "<svg" in result
        assert "</svg>" in result

    def test_is_well_formed_xml(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        root = ET.fromstring(result)
        assert root.tag == "svg" or root.tag.endswith("}svg")

    def test_contains_layer_names(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "UI" in result
        assert "DOMAIN" in result

    def test_contains_file_counts(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "1 file" in result

    def test_layer_colors_from_config(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "#4A90D9" in result
        assert "#50C878" in result

    def test_violation_edges_are_red(self) -> None:
        graph, violations = _make_graph_with_violation()
        result = export_svg(graph, _make_config(), violations)
        assert "#D94A4A" in result

    def test_clean_edges_are_green(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "#50C878" in result

    def test_empty_graph(self) -> None:
        result = export_svg(nx.DiGraph(), RubiconConfig(), [])
        assert result.startswith("<?xml")
        assert "<svg" in result

    def test_contains_title(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "Architecture Overview" in result

    def test_contains_legend(self) -> None:
        result = export_svg(_make_graph(), _make_config(), [])
        assert "Clean connection" in result
        assert "Violation" in result

    def test_unclassified_layer_appears(self) -> None:
        g = nx.DiGraph()
        g.add_node("stray.py", file_path=Path("stray.py"), language="python", layer="unclassified", symbols=[])
        result = export_svg(g, RubiconConfig(), [])
        assert "UNCLASSIFIED" in result

    def test_violation_label_contains_viol(self) -> None:
        graph, violations = _make_graph_with_violation()
        result = export_svg(graph, _make_config(), violations)
        assert "viol" in result


# ---------------------------------------------------------------------------
# TestExportToFile
# ---------------------------------------------------------------------------

class TestExportToFile:
    def test_writes_svg_file(self, tmp_path: Path) -> None:
        out = tmp_path / "diagram.svg"
        export_to_file(_make_graph(), _make_config(), [], out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<?xml")
        assert "<svg" in content

    def test_svg_file_contains_all_layers(self, tmp_path: Path) -> None:
        out = tmp_path / "diagram.svg"
        export_to_file(_make_graph(), _make_config(), [], out)
        content = out.read_text(encoding="utf-8")
        assert "UI" in content
        assert "DOMAIN" in content
