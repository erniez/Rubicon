"""Generate Mermaid layer diagrams from the architecture graph."""

from __future__ import annotations

from collections import Counter

import networkx as nx

from rubicon.models import RubiconConfig, Severity, Violation
from rubicon.snapshot.diff import SnapshotDiff


def generate_mermaid(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    diff: SnapshotDiff | None = None,
) -> str:
    """Generate a Mermaid graph showing layers, connections, and violations."""
    lines: list[str] = []

    # Diff summary comment at the top
    if diff is not None:
        lines.append(f"    %% Diff: {diff.summary}")
        lines.append("")

    lines.append("graph TD")

    # Collect layer stats
    layer_files: dict[str, int] = Counter()
    for node_id in graph.nodes:
        layer = graph.nodes[node_id].get("layer", "unclassified")
        layer_files[layer] += 1

    # Determine rows to show (use layer_rows, then any extras)
    rows = [list(row) for row in config.layer_rows]
    known = set(config.flat_layer_order)
    extras = sorted(l for l in layer_files if l not in known and l != "unclassified")
    if extras:
        rows.append(extras)
    if layer_files.get("unclassified", 0) > 0:
        rows.append(["unclassified"])

    # Flat list of all layers for edge/style iteration
    layers_to_show = [layer for row in rows for layer in row]

    # Emit layer nodes — wide band labels to mimic strata
    for row in rows:
        if len(row) > 1:
            group_id = _sanitize_id("_".join(row))
            lines.append(f"    subgraph {group_id}[ ]")
            lines.append(f"        direction LR")
        for layer in row:
            count = layer_files.get(layer, 0)
            name_upper = layer.replace("_", " ").upper()
            file_label = f"{count} file{'s' if count != 1 else ''}"
            pad = "\u2003" * 4
            node_id = _sanitize_id(layer)
            indent = "        " if len(row) > 1 else "    "
            lines.append(f'{indent}{node_id}["{pad}{name_upper}{pad}{pad}{file_label}{pad}"]')
        if len(row) > 1:
            lines.append("    end")

    # Invisible edges to enforce top-to-bottom row ordering
    if len(rows) > 1:
        for i in range(len(rows) - 1):
            s_id = _sanitize_id(rows[i][0])
            t_id = _sanitize_id(rows[i + 1][0])
            lines.append(f"    {s_id} ~~~ {t_id}")

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

    # Compute layer-level diff aggregations
    diff_added: dict[tuple[str, str], int] = Counter()
    diff_removed: dict[tuple[str, str], int] = Counter()
    if diff is not None:
        node_layer: dict[str, str] = {}
        for node_id in graph.nodes:
            node_layer[node_id] = graph.nodes[node_id].get("layer", "unclassified")

        for e in diff.added_edges:
            sl = node_layer.get(e["source"], "unclassified")
            tl = node_layer.get(e["target"], "unclassified")
            if sl != tl:
                diff_added[(sl, tl)] += 1

        for e in diff.removed_edges:
            sl = node_layer.get(e["source"], "unclassified")
            tl = node_layer.get(e["target"], "unclassified")
            if sl != tl:
                diff_removed[(sl, tl)] += 1

    # Emit edges
    emitted: set[tuple[str, str]] = set()

    for (s_layer, t_layer), count in sorted(layer_edges.items()):
        s_id = _sanitize_id(s_layer)
        t_id = _sanitize_id(t_layer)
        v_count = violation_edges.get((s_layer, t_layer), 0)
        added = diff_added.get((s_layer, t_layer), 0)

        label_parts: list[str] = [f"{count}"]
        if v_count > 0:
            label_parts.append(f"{v_count} viol")
        if added > 0:
            label_parts.append(f"+{added} NEW")

        label = " / ".join(label_parts)
        if v_count > 0:
            lines.append(f"    {s_id} -.->|{label}| {t_id}")
        else:
            lines.append(f"    {s_id} -->|{label}| {t_id}")

        emitted.add((s_layer, t_layer))

    # Emit violation-only edges (no normal connections)
    for (s_layer, t_layer), v_count in sorted(violation_edges.items()):
        if (s_layer, t_layer) in emitted:
            continue
        s_id = _sanitize_id(s_layer)
        t_id = _sanitize_id(t_layer)
        lines.append(f"    {s_id} -.->|{v_count} viol| {t_id}")
        emitted.add((s_layer, t_layer))

    # Emit removed edges (only in diff mode, for layer pairs not already shown)
    for (s_layer, t_layer), removed in sorted(diff_removed.items()):
        s_id = _sanitize_id(s_layer)
        t_id = _sanitize_id(t_layer)
        if (s_layer, t_layer) in emitted:
            # Append a removed annotation to the existing edge comment
            lines.append(f"    %% {s_id} -> {t_id}: -{removed} REMOVED")
        else:
            lines.append(f"    {s_id} -.->|-{removed} REMOVED| {t_id}")
            emitted.add((s_layer, t_layer))

    # Style — band-like strata appearance
    lines.append("")
    lines.append("    %% Styles")
    for layer in layers_to_show:
        layer_config = config.layers.get(layer)
        color = layer_config.color if layer_config and layer_config.color else "#888888"
        node_id = _sanitize_id(layer)
        lines.append(
            f"    style {node_id} fill:{color}18,stroke:{color},stroke-width:2px,"
            f"color:#fff,text-align:left"
        )

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
