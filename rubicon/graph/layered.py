"""Apply layer classifications to graph nodes."""

from pathlib import PurePosixPath

import networkx as nx


def apply_layers(
    graph: nx.DiGraph,
    layer_map: dict[str, list[str]],
) -> None:
    """Tag each node with its architectural layer based on directory mappings.

    Args:
        graph: The dependency graph (modified in place).
        layer_map: Mapping of layer name to list of directory prefixes.
            Example: {"presentation": ["app/ui/", "app/screens/"]}

    Nodes not matching any layer remain tagged as "unclassified".
    """
    for node_id in graph.nodes:
        node_path = str(graph.nodes[node_id].get("file_path", node_id))
        graph.nodes[node_id]["layer"] = _classify(node_path, layer_map)


def _classify(file_path: str, layer_map: dict[str, list[str]]) -> str:
    """Determine which layer a file belongs to."""
    # Normalize to forward slashes for consistent matching
    normalized = str(PurePosixPath(file_path))

    for layer_name, directories in layer_map.items():
        for directory in directories:
            # Normalize the directory prefix too
            norm_dir = str(PurePosixPath(directory))
            if normalized.startswith(norm_dir):
                return layer_name

    return "unclassified"
