"""Assembles a NetworkX directed graph from parser output."""

from pathlib import Path

import networkx as nx

from rubicon.crawler.scanner import SourceFile
from rubicon.graph.models import Relationship, RelationshipType
from rubicon.parser.treesitter import parse_file


def build_graph(files: list[SourceFile]) -> nx.DiGraph:
    """Parse all source files and assemble a dependency graph.

    Each node represents a file. Node attributes:
        - file_path: Path
        - language: str
        - symbols: list[str]
        - layer: str (defaults to "unclassified")

    Each edge carries a list of Relationship objects as the
    "relationships" attribute.

    Returns:
        A NetworkX DiGraph with file-level nodes and relationship edges.
    """
    graph = nx.DiGraph()
    all_relationships: list[Relationship] = []

    for source_file in files:
        node_id = str(source_file.path)
        graph.add_node(
            node_id,
            file_path=source_file.path,
            language=source_file.language,
            symbols=[],
            layer="unclassified",
        )

        rels = parse_file(source_file.path, source_file.language, source_file.content)
        all_relationships.extend(rels)

    _add_edges(graph, all_relationships)

    return graph


def build_graph_from_relationships(
    relationships: list[Relationship],
) -> nx.DiGraph:
    """Build a graph from a pre-computed list of relationships.

    Useful for testing. Automatically creates nodes for any
    source_file referenced in the relationships.
    """
    graph = nx.DiGraph()

    file_paths: set[str] = set()
    for rel in relationships:
        file_paths.add(str(rel.source_file))

    for fp in sorted(file_paths):
        graph.add_node(
            fp,
            file_path=Path(fp),
            language="",
            symbols=[],
            layer="unclassified",
        )

    _add_edges(graph, relationships)

    return graph


def _add_edges(graph: nx.DiGraph, relationships: list[Relationship]) -> None:
    """Add edges to the graph, consolidating relationships between the same nodes."""
    edge_map: dict[tuple[str, str], list[Relationship]] = {}

    for rel in relationships:
        source_id = str(rel.source_file)
        # For imports, the target is a module name — try to resolve to a file node
        target_id = _resolve_target(graph, rel)

        key = (source_id, target_id)
        edge_map.setdefault(key, []).append(rel)

    for (source_id, target_id), rels in edge_map.items():
        # Only add edges where both endpoints exist as nodes
        if source_id in graph and target_id in graph:
            graph.add_edge(source_id, target_id, relationships=rels)


def _resolve_target(graph: nx.DiGraph, rel: Relationship) -> str:
    """Try to resolve a relationship target to an existing graph node.

    For imports, attempts to match the module name to a file path
    in the graph. Falls back to the raw target string.
    """
    if rel.type == RelationshipType.IMPORT:
        # Try common path resolutions
        target = rel.target
        for candidate in _import_path_candidates(target):
            if candidate in graph:
                return candidate
    return rel.target


def _import_path_candidates(module: str) -> list[str]:
    """Generate possible file paths for a module import string."""
    # Convert dotted module to path: "foo.bar" -> "foo/bar"
    path_base = module.replace(".", "/")

    candidates = [
        f"{path_base}.py",
        f"{path_base}.ts",
        f"{path_base}.kt",
        f"{path_base}.swift",
        f"{path_base}/index.ts",
        f"{path_base}/__init__.py",
        path_base,
    ]

    # Handle relative imports: "./foo" -> "foo"
    if module.startswith("./") or module.startswith("../"):
        clean = module.lstrip("./")
        candidates.extend([
            f"{clean}.py",
            f"{clean}.ts",
            f"{clean}.kt",
            f"{clean}.swift",
            f"{clean}/index.ts",
            clean,
        ])

    return candidates


def graph_summary(graph: nx.DiGraph) -> str:
    """Return a human-readable summary of the graph."""
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    type_counts: dict[str, int] = {}
    for _, _, data in graph.edges(data=True):
        for rel in data.get("relationships", []):
            type_name = rel.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

    parts = [f"{node_count} nodes, {edge_count} edges"]
    if type_counts:
        detail = ", ".join(f"{count} {name}" for name, count in sorted(type_counts.items()))
        parts.append(f"({detail})")

    return " ".join(parts)
