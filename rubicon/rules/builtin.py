"""Built-in architectural rules."""

from pathlib import Path

import networkx as nx

from rubicon.models import Relationship, RelationshipType, RubiconConfig, Severity, Violation


def no_upward_dependency(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Imports should not go from lower layers to higher layers.

    "Lower" means a higher index in layer_order (e.g. data is below domain).
    """
    violations: list[Violation] = []

    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")

        source_idx = config.layer_index(source_layer)
        target_idx = config.layer_index(target_layer)

        if source_idx is None or target_idx is None:
            continue

        # source_idx > target_idx means source is lower, target is higher
        if source_idx > target_idx:
            for rel in data.get("relationships", []):
                if rel.type == RelationshipType.IMPORT:
                    violations.append(Violation(
                        rule="no_upward_dependency",
                        severity=Severity.WARNING,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        message=f"{source_layer} layer imports from {target_layer} layer",
                        relationship=rel,
                    ))

    return violations


def no_layer_skipping(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Layers should not skip intermediate layers (e.g. presentation → data)."""
    violations: list[Violation] = []

    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")

        source_idx = config.layer_index(source_layer)
        target_idx = config.layer_index(target_layer)

        if source_idx is None or target_idx is None:
            continue
        if source_layer == target_layer:
            continue
        if target_layer in config.foundation_layers:
            continue
        if source_layer in config.orchestrator_layers:
            continue

        distance = abs(source_idx - target_idx)
        if distance > 1:
            for rel in data.get("relationships", []):
                violations.append(Violation(
                    rule="no_layer_skipping",
                    severity=Severity.WARNING,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    message=f"{source_layer} directly references {target_layer}, skipping intermediate layers",
                    relationship=rel,
                ))

    return violations


def inheritance_flows_downward(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """If A inherits from B, A's layer must be same or below B's layer.

    "Below" means a higher index in layer_order.
    """
    violations: list[Violation] = []

    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")

        source_idx = config.layer_index(source_layer)
        target_idx = config.layer_index(target_layer)

        if source_idx is None or target_idx is None:
            continue

        for rel in data.get("relationships", []):
            if rel.type != RelationshipType.INHERITANCE:
                continue
            # A (source_id) inherits from B (target_id)
            # A's layer index must be >= B's layer index (same or below)
            if source_idx < target_idx:
                violations.append(Violation(
                    rule="inheritance_flows_downward",
                    severity=Severity.ERROR,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    message=f"{source_id} ({source_layer}) inherits from {target_id} ({target_layer}), but inheritance must flow downward",
                    relationship=rel,
                ))

    return violations


def no_circular_ownership(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Detect cycles in ownership edges using DFS cycle detection."""
    return _detect_cycles(graph, RelationshipType.OWNERSHIP, "no_circular_ownership", Severity.ERROR, "Circular ownership")


def no_circular_imports(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Detect cycles in import edges using DFS cycle detection."""
    return _detect_cycles(graph, RelationshipType.IMPORT, "no_circular_imports", Severity.WARNING, "Circular import")


def _detect_cycles(
    graph: nx.DiGraph,
    rel_type: RelationshipType,
    rule_name: str,
    severity: Severity,
    label: str,
) -> list[Violation]:
    """Generic cycle detection on a subgraph filtered by relationship type."""
    subgraph = nx.DiGraph()

    for source_id, target_id, data in graph.edges(data=True):
        for rel in data.get("relationships", []):
            if rel.type == rel_type:
                subgraph.add_edge(source_id, target_id, relationship=rel)

    violations: list[Violation] = []

    try:
        cycles = list(nx.simple_cycles(subgraph))
    except nx.NetworkXError:
        return violations

    for cycle in cycles:
        cycle_str = " → ".join(cycle + [cycle[0]])
        first = cycle[0]
        second = cycle[1] if len(cycle) > 1 else cycle[0]
        edge_data = subgraph.get_edge_data(first, second)
        rel = edge_data.get("relationship") if edge_data else None

        violations.append(Violation(
            rule=rule_name,
            severity=severity,
            source_node_id=first,
            target_node_id=second,
            message=f"{label} detected: {cycle_str}",
            relationship=rel,
        ))

    return violations


def single_responsibility(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Flag files with edges to 4+ different layers."""
    violations: list[Violation] = []

    for node_id in graph.nodes:
        connected_layers: set[str] = set()

        for _, target_id in graph.out_edges(node_id):
            layer = graph.nodes[target_id].get("layer", "unclassified")
            if layer != "unclassified":
                connected_layers.add(layer)

        for source_id, _ in graph.in_edges(node_id):
            layer = graph.nodes[source_id].get("layer", "unclassified")
            if layer != "unclassified":
                connected_layers.add(layer)

        if len(connected_layers) >= 4:
            violations.append(Violation(
                rule="single_responsibility",
                severity=Severity.INFO,
                source_node_id=node_id,
                target_node_id=None,
                message=f"{node_id} has connections to {len(connected_layers)} layers: {', '.join(sorted(connected_layers))}",
            ))

    return violations


_ABSTRACTION_INDICATORS = frozenset({
    "abstract", "base", "protocol", "interface", "contract", "mixin",
    "Abstract", "Base", "Protocol", "Interface", "Contract", "Mixin",
    "I",  # Common C#/Java convention: IRepository, IService
})


def _looks_like_abstraction(node_id: str, graph: nx.DiGraph) -> bool:
    """Heuristic: does this node look like an abstraction?"""
    symbols = graph.nodes[node_id].get("symbols", [])
    names_to_check = [node_id] + symbols

    for name in names_to_check:
        parts = name.replace("/", ".").replace("\\", ".").split(".")
        for part in parts:
            # Split CamelCase: "AbstractUserRepo" -> ["Abstract", "User", "Repo"]
            # Also check if the whole part matches
            if part in _ABSTRACTION_INDICATORS:
                return True
            # Check if the name starts or ends with an indicator
            for indicator in _ABSTRACTION_INDICATORS:
                if len(part) > len(indicator) and (
                    part.startswith(indicator) or part.endswith(indicator)
                ):
                    return True

    return False


def dependency_inversion(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Flag cross-layer inheritance where the target doesn't look like an abstraction.

    If A inherits from B across layer boundaries and B's name doesn't
    suggest it's an abstraction (Abstract*, Base*, *Protocol, *Interface),
    flag it as a potential DI violation.
    """
    violations: list[Violation] = []

    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")

        if source_layer == target_layer:
            continue
        if source_layer == "unclassified" or target_layer == "unclassified":
            continue

        for rel in data.get("relationships", []):
            if rel.type != RelationshipType.INHERITANCE:
                continue

            if not _looks_like_abstraction(target_id, graph):
                violations.append(Violation(
                    rule="dependency_inversion",
                    severity=Severity.INFO,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    message=f"{source_id} ({source_layer}) inherits from concrete {target_id} ({target_layer}) across layers; consider depending on an abstraction",
                    relationship=rel,
                ))

    return violations


def orphan_detection(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Flag files with zero incoming or outgoing edges."""
    violations: list[Violation] = []

    for node_id in graph.nodes:
        if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0:
            violations.append(Violation(
                rule="orphan_detection",
                severity=Severity.INFO,
                source_node_id=node_id,
                target_node_id=None,
                message=f"{node_id} has no connections",
            ))

    return violations
