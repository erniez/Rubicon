"""Pure functions that transform the in-memory graph + violations into JSON
structures for the D3.js frontend.

These functions have no FastAPI dependency. They operate on a NetworkX
DiGraph, a RubiconConfig, a list of Violations, and an optional SnapshotDiff.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from rubicon.models import RubiconConfig, Violation
from rubicon.snapshot.diff import SnapshotDiff


# ---------------------------------------------------------------------------
# Level 1 — Layer Summary
# ---------------------------------------------------------------------------

def layer_summary(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
) -> dict:
    """Level 1 data: layers with file counts, inter-layer edges, violations.

    Returns a dict with:
        layers: list of {name, file_count, color}
        edges: list of {source, target, count, relationships: {type: count}, violations: int}
        violations: total violation count
    """
    # --- Layer file counts ---
    layer_files: dict[str, int] = Counter()
    for node_id in graph.nodes:
        layer = graph.nodes[node_id].get("layer", "unclassified")
        layer_files[layer] += 1

    # Determine ordered list of layers to include
    layers_ordered = _ordered_layers(config, layer_files)

    # Build layer color lookup
    layer_colors: dict[str, str] = {}
    for name in layers_ordered:
        lc = config.layers.get(name)
        layer_colors[name] = lc.color if lc and lc.color else _default_color(name)

    layers_list = [
        {
            "name": layer,
            "file_count": layer_files.get(layer, 0),
            "color": layer_colors.get(layer, "#999999"),
        }
        for layer in layers_ordered
    ]

    # --- Inter-layer edge counts with relationship breakdowns ---
    edge_counter: dict[tuple[str, str], Counter] = {}
    for source_id, target_id, data in graph.edges(data=True):
        s_layer = graph.nodes[source_id].get("layer", "unclassified")
        t_layer = graph.nodes[target_id].get("layer", "unclassified")
        if s_layer == t_layer:
            continue
        key = (s_layer, t_layer)
        if key not in edge_counter:
            edge_counter[key] = Counter()
        for rel in data.get("relationships", []):
            edge_counter[key][rel.type.value] += 1

    # --- Inter-layer violation counts ---
    violation_counter: dict[tuple[str, str], int] = Counter()
    for v in violations:
        if v.target_node_id is None:
            continue
        s_attrs = graph.nodes.get(v.source_node_id, {})
        t_attrs = graph.nodes.get(v.target_node_id, {})
        s_layer = s_attrs.get("layer", "unclassified") if s_attrs else "unclassified"
        t_layer = t_attrs.get("layer", "unclassified") if t_attrs else "unclassified"
        if s_layer != t_layer:
            violation_counter[(s_layer, t_layer)] += 1

    # Merge into edges list
    all_layer_pairs = set(edge_counter.keys()) | set(violation_counter.keys())
    edges_list = []
    for s_layer, t_layer in sorted(all_layer_pairs):
        rel_breakdown = dict(edge_counter.get((s_layer, t_layer), {}))
        total_count = sum(rel_breakdown.values())
        edges_list.append({
            "source": s_layer,
            "target": t_layer,
            "count": total_count,
            "relationships": rel_breakdown,
            "violations": violation_counter.get((s_layer, t_layer), 0),
        })

    return {
        "layers": layers_list,
        "edges": edges_list,
        "violations": len(violations),
    }


# ---------------------------------------------------------------------------
# Level 2 — File-Level View
# ---------------------------------------------------------------------------

def file_level_view(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    layer: str | None = None,
    source_layer: str | None = None,
    target_layer: str | None = None,
) -> dict:
    """Level 2 data: files within the specified layer(s).

    If ``layer`` is given, return all files in that single layer and their
    intra-layer edges plus edges to/from neighbouring layers.

    If ``source_layer`` and ``target_layer`` are given, return files from
    both layers and only the cross-layer edges between them.

    Returns:
        nodes: list of {id, file_path, language, layer, symbols}
        edges: list of {source, target, relationships: [{type, source_symbol, target_symbol, line_number}]}
        violations: list of matching violations
    """
    # Determine which layers to include
    target_layers: set[str] = set()
    if layer is not None:
        target_layers.add(layer)
    if source_layer is not None:
        target_layers.add(source_layer)
    if target_layer is not None:
        target_layers.add(target_layer)

    # Collect nodes in the target layers
    node_ids: set[str] = set()
    for node_id in graph.nodes:
        node_layer = graph.nodes[node_id].get("layer", "unclassified")
        if node_layer in target_layers:
            node_ids.add(node_id)

    nodes_list = _serialize_nodes(graph, node_ids)

    # Collect edges between these nodes
    cross_layer_only = source_layer is not None and target_layer is not None and layer is None
    edges_list = []
    for source_id, target_id, data in graph.edges(data=True):
        if source_id not in node_ids or target_id not in node_ids:
            continue
        if cross_layer_only:
            s_layer = graph.nodes[source_id].get("layer", "unclassified")
            t_layer = graph.nodes[target_id].get("layer", "unclassified")
            if s_layer == t_layer:
                continue
        edges_list.append(_serialize_edge(data, source_id, target_id))

    # Collect violations involving these nodes
    violations_list = _filter_violations(violations, node_ids)

    # Cross-layer connections: for single-layer view, summarise edges that
    # leave this layer so the frontend can render "exit arrows" pointing to
    # adjacent layers without showing individual external files.
    cross_layer: list[dict] = []
    if layer is not None:
        # Gather outbound + inbound edges to/from external layers
        ext: dict[str, dict] = {}  # layer_name -> {outbound: {file_ids}, inbound: {file_ids}}
        for source_id, target_id, _data in graph.edges(data=True):
            s_layer = graph.nodes[source_id].get("layer", "unclassified")
            t_layer = graph.nodes[target_id].get("layer", "unclassified")
            if s_layer == layer and t_layer != layer:
                entry = ext.setdefault(t_layer, {"outbound": set(), "inbound": set()})
                entry["outbound"].add(source_id)
            elif t_layer == layer and s_layer != layer:
                entry = ext.setdefault(s_layer, {"outbound": set(), "inbound": set()})
                entry["inbound"].add(target_id)

        # Build layer color lookup
        for ext_layer, directions in sorted(ext.items()):
            lc = config.layers.get(ext_layer)
            color = lc.color if lc and lc.color else _default_color(ext_layer)
            cross_layer.append({
                "layer": ext_layer,
                "color": color,
                "outbound_files": sorted(directions["outbound"]),
                "inbound_files": sorted(directions["inbound"]),
            })

    return {
        "nodes": nodes_list,
        "edges": edges_list,
        "violations": violations_list,
        "cross_layer_connections": cross_layer,
    }


# ---------------------------------------------------------------------------
# Level 3 — Ratsnest (Single-File Focus)
# ---------------------------------------------------------------------------

def ratsnest_view(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    file_id: str,
) -> dict | None:
    """Level 3 data: the focus node plus all directly connected nodes.

    Returns None if the file_id doesn't exist in the graph.

    Returns:
        focus: {id, file_path, language, layer, symbols}
        neighbors: list of {id, file_path, language, layer, symbols, direction}
        edges: list of {source, target, relationships, direction}
        violations: list of matching violations
    """
    if file_id not in graph:
        return None

    focus_attrs = graph.nodes[file_id]
    focus = {
        "id": file_id,
        "file_path": str(focus_attrs.get("file_path", file_id)),
        "language": focus_attrs.get("language", ""),
        "layer": focus_attrs.get("layer", "unclassified"),
        "symbols": list(focus_attrs.get("symbols", [])),
    }

    neighbor_ids: set[str] = set()
    neighbor_direction: dict[str, str] = {}  # node_id -> "inbound" | "outbound" | "both"
    edges_list: list[dict] = []

    # Outbound edges
    for _, target_id, data in graph.out_edges(file_id, data=True):
        neighbor_ids.add(target_id)
        neighbor_direction[target_id] = "outbound"
        edges_list.append({
            **_serialize_edge(data, file_id, target_id),
            "direction": "outbound",
        })

    # Inbound edges
    for source_id, _, data in graph.in_edges(file_id, data=True):
        neighbor_ids.add(source_id)
        if source_id in neighbor_direction:
            neighbor_direction[source_id] = "both"
        else:
            neighbor_direction[source_id] = "inbound"
        edges_list.append({
            **_serialize_edge(data, source_id, file_id),
            "direction": "inbound",
        })

    # Neighbor node data
    neighbors_list = []
    for nid in sorted(neighbor_ids):
        attrs = graph.nodes.get(nid, {})
        neighbors_list.append({
            "id": nid,
            "file_path": str(attrs.get("file_path", nid)),
            "language": attrs.get("language", ""),
            "layer": attrs.get("layer", "unclassified"),
            "symbols": list(attrs.get("symbols", [])),
            "direction": neighbor_direction.get(nid, "outbound"),
        })

    # Violations involving the focus file
    involved = neighbor_ids | {file_id}
    violations_list = _filter_violations(violations, involved, focus_id=file_id)

    return {
        "focus": focus,
        "neighbors": neighbors_list,
        "edges": edges_list,
        "violations": violations_list,
    }


# ---------------------------------------------------------------------------
# Diff Overlay
# ---------------------------------------------------------------------------

def diff_overlay(diff: SnapshotDiff | None, graph: nx.DiGraph | None = None) -> dict:
    """Overlay data for any view level.

    Returns an empty overlay when diff is None (no diff mode).
    When graph is provided, includes a layer_map mapping node IDs to layers
    so the frontend can aggregate file-level diffs into layer-level diffs.
    """
    if diff is None:
        return {
            "enabled": False,
            "added_edges": [],
            "removed_edges": [],
            "added_nodes": [],
            "removed_nodes": [],
            "new_violations": [],
            "resolved_violations": [],
            "summary": "",
            "layer_map": {},
        }

    layer_map: dict[str, str] = {}
    if graph is not None:
        for node_id in graph.nodes:
            layer_map[node_id] = graph.nodes[node_id].get("layer", "unclassified")

    return {
        "enabled": True,
        "added_edges": diff.added_edges,
        "removed_edges": diff.removed_edges,
        "added_nodes": diff.added_nodes,
        "removed_nodes": diff.removed_nodes,
        "new_violations": diff.new_violations,
        "resolved_violations": diff.resolved_violations,
        "summary": diff.summary,
        "layer_map": layer_map,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordered_layers(config: RubiconConfig, layer_files: dict[str, int]) -> list[str]:
    """Determine the ordered list of layers to show.

    Only includes layers that have at least one file, preserving the
    order from config.layer_order first, then any extra layers
    alphabetically, and finally "unclassified" if present.
    """
    layers: list[str] = []
    for layer in config.layer_order:
        if layer_files.get(layer, 0) > 0:
            layers.append(layer)
    for layer in sorted(layer_files.keys()):
        if layer not in layers and layer != "unclassified":
            layers.append(layer)
    if layer_files.get("unclassified", 0) > 0:
        layers.append("unclassified")
    return layers


_DEFAULT_COLORS = [
    "#4A90D9", "#50C878", "#E8A838", "#D94A4A",
    "#9B59B6", "#1ABC9C", "#F39C12", "#E74C3C",
]


def _default_color(name: str) -> str:
    """Return a deterministic default color for a layer name."""
    idx = hash(name) % len(_DEFAULT_COLORS)
    return _DEFAULT_COLORS[idx]


def _serialize_nodes(graph: nx.DiGraph, node_ids: set[str]) -> list[dict]:
    """Serialize a subset of graph nodes."""
    nodes = []
    for nid in sorted(node_ids):
        attrs = graph.nodes[nid]
        nodes.append({
            "id": nid,
            "file_path": str(attrs.get("file_path", nid)),
            "language": attrs.get("language", ""),
            "layer": attrs.get("layer", "unclassified"),
            "symbols": list(attrs.get("symbols", [])),
        })
    return nodes


def _serialize_edge(data: dict, source_id: str, target_id: str) -> dict:
    """Serialize a single edge with its relationships."""
    rels = []
    for rel in data.get("relationships", []):
        rels.append({
            "type": rel.type.value,
            "source_symbol": rel.source,
            "target_symbol": rel.target,
            "line_number": rel.line_number,
        })
    return {
        "source": source_id,
        "target": target_id,
        "relationships": rels,
    }


def _serialize_violation(v: Violation) -> dict:
    """Serialize a violation for the API response."""
    result: dict = {
        "rule": v.rule,
        "severity": v.severity.value,
        "source_node_id": v.source_node_id,
        "target_node_id": v.target_node_id,
        "message": v.message,
    }
    if v.relationship is not None:
        result["relationship_type"] = v.relationship.type.value
        result["line_number"] = v.relationship.line_number
    return result


def _filter_violations(
    violations: list[Violation],
    node_ids: set[str],
    focus_id: str | None = None,
) -> list[dict]:
    """Filter and serialize violations involving the given node IDs.

    If focus_id is provided, at least one of source/target must be focus_id.
    """
    results: list[dict] = []
    for v in violations:
        involved = v.source_node_id in node_ids
        if v.target_node_id is not None:
            involved = involved or v.target_node_id in node_ids

        if focus_id is not None:
            involved = involved and (
                v.source_node_id == focus_id or v.target_node_id == focus_id
            )

        if involved:
            results.append(_serialize_violation(v))
    return results
