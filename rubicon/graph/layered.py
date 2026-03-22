"""Apply layer classifications to graph nodes."""

import fnmatch
from pathlib import PurePosixPath

import networkx as nx


def apply_layers(
    graph: nx.DiGraph,
    layer_map: dict[str, list[str]],
    layer_patterns: dict[str, list[str]] | None = None,
) -> None:
    """Tag each node with its architectural layer.

    Classification priority:
        1. File name patterns (glob matching) — if layer_patterns is provided
        2. Directory prefix matching — from layer_map

    Args:
        graph: The dependency graph (modified in place).
        layer_map: Mapping of layer name to list of directory prefixes.
        layer_patterns: Mapping of layer name to list of file glob patterns.
            Example: {"domain": ["*Interactor*", "*UseCase*"]}

    Nodes not matching any layer remain tagged as "unclassified".
    """
    for node_id in graph.nodes:
        node_path = str(graph.nodes[node_id].get("file_path", node_id))
        graph.nodes[node_id]["layer"] = _classify(node_path, layer_map, layer_patterns)


def _classify(
    file_path: str,
    layer_map: dict[str, list[str]],
    layer_patterns: dict[str, list[str]] | None = None,
) -> str:
    """Determine which layer a file belongs to."""
    normalized = str(PurePosixPath(file_path))

    # Patterns take priority over directories
    if layer_patterns:
        file_name = PurePosixPath(file_path).name
        for layer_name, patterns in layer_patterns.items():
            for pattern in patterns:
                if fnmatch.fnmatch(file_name, pattern):
                    return layer_name

    # Fall back to directory prefix matching
    for layer_name, directories in layer_map.items():
        for directory in directories:
            norm_dir = str(PurePosixPath(directory))
            if normalized.startswith(norm_dir):
                return layer_name

    return "unclassified"
