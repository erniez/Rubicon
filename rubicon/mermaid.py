"""Generate Mermaid layer diagrams from the architecture graph."""

from collections import Counter

import networkx as nx

from rubicon.classifier.config import RubiconConfig
from rubicon.graph.models import Severity, Violation


def generate_mermaid(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
) -> str:
    """Generate a Mermaid graph showing layers, connections, and violations."""
    lines: list[str] = ["graph TD"]

    # Collect layer stats
    layer_files: dict[str, int] = Counter()
    for node_id in graph.nodes:
        layer = graph.nodes[node_id].get("layer", "unclassified")
        layer_files[layer] += 1

    # Determine which layers to show (use layer_order, then any extras)
    layers_to_show = list(config.layer_order)
    for layer in sorted(layer_files.keys()):
        if layer not in layers_to_show and layer != "unclassified":
            layers_to_show.append(layer)
    if layer_files.get("unclassified", 0) > 0:
        layers_to_show.append("unclassified")

    # Emit layer nodes
    for layer in layers_to_show:
        count = layer_files.get(layer, 0)
        label = layer.replace("_", " ").title()
        node_id = _sanitize_id(layer)
        lines.append(f'    {node_id}["{label} ({count} files)"]')

    # Collect inter-layer edge counts
    layer_edges: dict[tuple[str, str], int] = Counter()
    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")
        if source_layer != target_layer:
            rel_count = len(data.get("relationships", []))
            layer_edges[(source_layer, target_layer)] += rel_count

    # Collect inter-layer violation counts
    violation_edges: dict[tuple[str, str], int] = Counter()
    for v in violations:
        if v.target_node_id is None:
            continue
        s_layer = graph.nodes.get(v.source_node_id, {}).get("layer", "unclassified")
        t_layer = graph.nodes.get(v.target_node_id, {}).get("layer", "unclassified")
        if s_layer != t_layer:
            violation_edges[(s_layer, t_layer)] += 1

    # Emit edges
    emitted: set[tuple[str, str]] = set()

    for (s_layer, t_layer), count in sorted(layer_edges.items()):
        s_id = _sanitize_id(s_layer)
        t_id = _sanitize_id(t_layer)
        v_count = violation_edges.get((s_layer, t_layer), 0)

        if v_count > 0:
            lines.append(f"    {s_id} -.->|{count} conn / {v_count} viol| {t_id}")
        else:
            lines.append(f"    {s_id} -->|{count}| {t_id}")

        emitted.add((s_layer, t_layer))

    # Emit violation-only edges (no normal connections)
    for (s_layer, t_layer), v_count in sorted(violation_edges.items()):
        if (s_layer, t_layer) in emitted:
            continue
        s_id = _sanitize_id(s_layer)
        t_id = _sanitize_id(t_layer)
        lines.append(f"    {s_id} -.->|{v_count} viol| {t_id}")

    # Style violation edges
    lines.append("")
    lines.append("    %% Styles")
    for layer in layers_to_show:
        layer_config = config.layers.get(layer)
        if layer_config and layer_config.color:
            node_id = _sanitize_id(layer)
            lines.append(f"    style {node_id} fill:{layer_config.color}")

    return "\n".join(lines) + "\n"


# Mermaid reserved words that can't be used as node IDs
_RESERVED = frozenset({
    "graph", "subgraph", "end", "style", "class", "click",
    "linkstyle", "classDef", "default", "direction",
})


def _sanitize_id(name: str) -> str:
    """Convert a layer name to a valid Mermaid node ID."""
    node_id = name.replace(" ", "_").replace("-", "_")
    if node_id.lower() in {r.lower() for r in _RESERVED}:
        node_id = f"layer_{node_id}"
    return node_id
