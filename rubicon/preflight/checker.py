"""Pre-flight architecture rule checking.

check_fast(): Layer-only checks (~30ms). No graph build required.
check_full(): Layer checks + cycle detection. Loads or builds graph.
get_allowed_imports(): Query which layers a file may import from.
check_batch(): Validate multiple proposed changes at once.
"""

import fnmatch
from pathlib import Path

import networkx as nx

from rubicon.models import Relationship, RelationshipType, RubiconConfig, Severity
from rubicon.preflight.models import (
    AllowedImportsResult,
    BatchPreflightResult,
    PreflightResult,
    PreflightViolation,
)
from rubicon.preflight.resolver import classify_path, resolve_import_target
from rubicon.rules.builtin import ABSTRACTION_INDICATORS, detect_cycles


def check_fast(
    source: str,
    target: str,
    rel_type: str,
    config: RubiconConfig,
    root: Path,
) -> PreflightResult:
    """Check a proposed relationship using layer indices only.

    Does not build or load the dependency graph, so cycle detection is skipped.
    Only rules listed in config.rules are evaluated, matching the behaviour of
    rubicon check/analyze. Covers: no_upward_dependency, no_layer_skipping,
    inheritance_flows_downward, dependency_inversion (path heuristic only),
    and custom forbidden_imports.

    Args:
        source: Source file path (need not exist on disk).
        target: Target import string (file path, module name, etc.).
        rel_type: "import" or "inheritance".
        config: Loaded .rubicon configuration.
        root: Project root for resolving import strings to files.

    Returns:
        PreflightResult with allowed=True if no violations detected.
    """
    violations: list[PreflightViolation] = []

    # Classify source
    source_layer = classify_path(source, config)
    if source_layer is None:
        return PreflightResult(
            allowed=False,
            source=source,
            source_layer=None,
            target=target,
            target_layer=None,
            relationship_type=rel_type,
            violations=(PreflightViolation(
                rule="unclassifiable_source",
                severity="error",
                message=f"Source '{source}' is unclassifiable — "
                        f"no layer in .rubicon matches this path.",
            ),),
            cycle_detection_run=False,
        )

    # Resolve and classify target
    _, target_layer = resolve_import_target(target, root, config)
    if target_layer is None:
        return PreflightResult(
            allowed=False,
            source=source,
            source_layer=source_layer,
            target=target,
            target_layer=None,
            relationship_type=rel_type,
            violations=(PreflightViolation(
                rule="unclassifiable_target",
                severity="error",
                message=f"Target '{target}' is unclassifiable — "
                        f"check that the import path is correct.",
            ),),
            cycle_detection_run=False,
        )

    source_idx = config.layer_index(source_layer)
    target_idx = config.layer_index(target_layer)

    # If either layer isn't in layer_order, skip structural checks
    if source_idx is not None and target_idx is not None:
        # no_upward_dependency: lower layers cannot import higher layers
        if (
            "no_upward_dependency" in config.rules
            and rel_type == "import"
            and source_idx > target_idx
        ):
            violations.append(PreflightViolation(
                rule="no_upward_dependency",
                severity="warning",
                message=f"{source_layer} (index {source_idx}) cannot import "
                        f"{target_layer} (index {target_idx}) — upward dependency",
            ))

        # no_layer_skipping: cannot skip intermediate layers
        if (
            "no_layer_skipping" in config.rules
            and source_layer != target_layer
            and abs(source_idx - target_idx) > 1
            and target_layer not in config.foundation_layers
            and source_layer not in config.orchestrator_layers
        ):
            violations.append(PreflightViolation(
                rule="no_layer_skipping",
                severity="warning",
                message=f"{source_layer} directly references {target_layer}, "
                        f"skipping intermediate layers",
            ))

        # inheritance_flows_downward: A inherits B → A must be same level or below B
        if (
            "inheritance_flows_downward" in config.rules
            and rel_type == "inheritance"
            and source_idx < target_idx
        ):
            violations.append(PreflightViolation(
                rule="inheritance_flows_downward",
                severity="error",
                message=f"{source} ({source_layer}) inherits from {target} ({target_layer}), "
                        f"but inheritance must flow downward",
            ))

        # dependency_inversion: cross-layer inheritance to a concrete-looking target
        # Path-only heuristic; symbol-level detection requires a full graph.
        if (
            "dependency_inversion" in config.rules
            and rel_type == "inheritance"
            and source_layer != target_layer
            and not _path_looks_like_abstraction(target)
        ):
            violations.append(PreflightViolation(
                rule="dependency_inversion",
                severity="info",
                message=f"{source} ({source_layer}) inherits from concrete-looking "
                        f"{target} ({target_layer}) across layers; "
                        f"consider depending on an abstraction",
            ))

    # custom forbidden_imports
    for rule in config.custom_rules:
        if rule.source_layer != source_layer or not rule.forbidden_imports:
            continue
        for pattern in rule.forbidden_imports:
            if fnmatch.fnmatch(target, pattern):
                msg = rule.message or f"Import of '{target}' is forbidden from {source_layer} layer"
                violations.append(PreflightViolation(
                    rule=rule.name or "custom_forbidden_import",
                    severity=rule.severity,
                    message=msg,
                ))
                break  # one violation per custom rule

    return PreflightResult(
        allowed=len(violations) == 0,
        source=source,
        source_layer=source_layer,
        target=target,
        target_layer=target_layer,
        relationship_type=rel_type,
        violations=tuple(violations),
        cycle_detection_run=False,
    )


def _path_looks_like_abstraction(target: str) -> bool:
    """Heuristic: does this path/filename look like an abstraction?

    Checks path segments against ABSTRACTION_INDICATORS. This is weaker than
    the graph-based _looks_like_abstraction (which also checks symbol names),
    but works without loading the graph.
    """
    parts = target.replace("\\", "/").replace(".", "/").split("/")
    for part in parts:
        if part in ABSTRACTION_INDICATORS:
            return True
        for indicator in ABSTRACTION_INDICATORS:
            if len(part) > len(indicator) and (
                part.startswith(indicator) or part.endswith(indicator)
            ):
                return True
    return False


def _connected_layers(g: nx.DiGraph, node: str) -> set[str]:
    """Return the set of distinct layers connected to a node (in or out edges)."""
    layers: set[str] = set()
    for _, tgt in g.out_edges(node):
        lyr = g.nodes[tgt].get("layer", "unclassified")
        if lyr != "unclassified":
            layers.add(lyr)
    for src, _ in g.in_edges(node):
        lyr = g.nodes[src].get("layer", "unclassified")
        if lyr != "unclassified":
            layers.add(lyr)
    return layers


def _add_stub_edge(
    graph: nx.DiGraph,
    src_node: str,
    tgt_node: str,
    rel_type: str,
) -> None:
    """Add a proposed (stub) relationship edge to a graph copy."""
    stub_rel = Relationship(
        source=src_node,
        target=tgt_node,
        type=RelationshipType.IMPORT if rel_type == "import" else RelationshipType.INHERITANCE,
        source_file=Path(src_node),
        line_number=0,
    )
    if graph.has_edge(src_node, tgt_node):
        graph[src_node][tgt_node]["relationships"].append(stub_rel)
    else:
        graph.add_edge(src_node, tgt_node, relationships=[stub_rel])


def _filter_new_cycles(
    augmented: nx.DiGraph,
    baseline: nx.DiGraph,
    rel_type_enum: RelationshipType,
    rule: str,
    severity: Severity,
    label: str,
) -> list[PreflightViolation]:
    """Return cycle violations present in augmented but not in baseline."""
    new_violations = detect_cycles(augmented, rel_type_enum, rule, severity, label)
    existing_violations = detect_cycles(baseline, rel_type_enum, rule, severity, label)
    existing_messages = {v.message for v in existing_violations}
    return [
        PreflightViolation(rule=v.rule, severity=v.severity.value, message=v.message)
        for v in new_violations
        if v.message not in existing_messages
    ]


def _ensure_node(
    graph: nx.DiGraph,
    node_id: str,
    layer: str | None,
) -> None:
    """Add node to the graph if absent, with layer metadata."""
    if node_id not in graph:
        graph.add_node(node_id, layer=layer or "unclassified", symbols=[])


def get_allowed_imports(
    source: str,
    config: RubiconConfig,
    root: Path,
) -> AllowedImportsResult:
    """Query which layers a source file is allowed to import from.

    For each layer in config.flat_layer_order, simulates an import from the
    source to a probe path in that layer and checks whether it would be allowed.

    Layers with no directories (patterns-only) cannot be probed and are reported
    as forbidden with reason "patterns_only_layer".

    Args:
        source: Source file path (need not exist on disk).
        config: Loaded .rubicon configuration.
        root: Project root for import resolution.

    Returns:
        AllowedImportsResult with allowed_layers and forbidden_layers.
    """
    source_layer = classify_path(source, config)

    allowed: list[str] = []
    forbidden: list[dict] = []

    for layer in config.flat_layer_order:
        layer_config = config.layers.get(layer)

        # Patterns-only layers can't be probed via a directory path
        if layer_config is None or not layer_config.directories:
            forbidden.append({"layer": layer, "reason": "patterns_only_layer"})
            continue

        # Construct a synthetic probe path that will classify to this layer
        probe = layer_config.directories[0].rstrip("/") + "/__probe__.py"
        result = check_fast(source, probe, "import", config, root)

        if result.allowed:
            allowed.append(layer)
        else:
            reason = result.violations[0].rule if result.violations else "unknown"
            forbidden.append({"layer": layer, "reason": reason})

    return AllowedImportsResult(
        source=source,
        source_layer=source_layer,
        allowed_layers=tuple(allowed),
        forbidden_layers=tuple(forbidden),
    )


def check_batch(
    changes: list[dict],
    config: RubiconConfig,
    root: Path,
    full: bool = False,
) -> BatchPreflightResult:
    """Validate multiple proposed changes at once.

    Runs check_fast() on each change independently first. If full=True, also
    loads the graph once and adds ALL proposed import edges simultaneously before
    running cycle detection — this catches cycles that only appear when multiple
    changes are combined. Cycle detection only applies to import-type changes;
    inheritance-type changes are still checked by check_fast layer rules.

    Each change dict must have "from" and "to" keys; "type" is optional
    (defaults to "import").

    Args:
        changes: List of {"from": str, "to": str, "type": str} dicts.
        config: Loaded .rubicon configuration.
        root: Project root.
        full: Whether to run cycle detection on the combined change set.

    Returns:
        BatchPreflightResult with per-change results and top-level all_allowed.
    """
    # Extract fields once; reuse in both the fast loop and the graph loop
    extracted = [
        (c.get("from", ""), c.get("to", ""), c.get("type", "import"))
        for c in changes
    ]

    results: list[PreflightResult] = [
        check_fast(src, tgt, rtype, config, root)
        for src, tgt, rtype in extracted
    ]

    if full and changes and "no_circular_imports" in config.rules:
        graph = _load_or_build_graph(config, root)
        augmented = graph.copy()

        change_nodes: list[tuple[str | None, str | None]] = []
        for src, tgt, rtype in extracted:
            resolved_tgt, tgt_layer = resolve_import_target(tgt, root, config)
            src_layer = classify_path(src, config)

            # Add stub nodes for files not yet in the graph
            _ensure_node(augmented, src, src_layer)
            tgt_node_id = resolved_tgt or tgt
            if tgt_layer is not None:
                _ensure_node(augmented, tgt_node_id, tgt_layer)
                tgt_node: str | None = tgt_node_id
            else:
                tgt_node = None

            change_nodes.append((src, tgt_node))

            # Only add import edges to the augmented graph for cycle detection
            if tgt_node and rtype == "import":
                _add_stub_edge(augmented, src, tgt_node, rtype)

        truly_new = _filter_new_cycles(
            augmented, graph,
            RelationshipType.IMPORT, "no_circular_imports", Severity.WARNING, "Circular import",
        )

        # Attach new cycle violations to the first change whose nodes appear in the cycle
        for cycle_v in truly_new:
            attached = False
            for i, (src_node, tgt_node) in enumerate(change_nodes):
                if src_node and (
                    src_node in cycle_v.message
                    or (tgt_node and tgt_node in cycle_v.message)
                ):
                    old = results[i]
                    results[i] = PreflightResult(
                        allowed=False,
                        source=old.source,
                        source_layer=old.source_layer,
                        target=old.target,
                        target_layer=old.target_layer,
                        relationship_type=old.relationship_type,
                        violations=old.violations + (cycle_v,),
                        cycle_detection_run=True,
                    )
                    attached = True
                    break
            if not attached and results:
                old = results[-1]
                results[-1] = PreflightResult(
                    allowed=False,
                    source=old.source,
                    source_layer=old.source_layer,
                    target=old.target,
                    target_layer=old.target_layer,
                    relationship_type=old.relationship_type,
                    violations=old.violations + (cycle_v,),
                    cycle_detection_run=True,
                )

    return BatchPreflightResult(
        all_allowed=all(r.allowed for r in results),
        results=tuple(results),
    )


def _load_or_build_graph(config: RubiconConfig, root: Path) -> nx.DiGraph:
    """Return the dependency graph, loading from cache when valid."""
    from rubicon.crawler.scanner import scan
    from rubicon.graph.builder import build_graph
    from rubicon.graph.cache import is_cache_valid, load_graph_cache, save_graph_cache
    from rubicon.graph.layered import apply_layers

    files = scan(root, ignore=config.ignore)
    if is_cache_valid(root, files):
        cached = load_graph_cache(root)
        if cached is not None:
            return cached

    graph = build_graph(files)
    apply_layers(graph, config.layer_map, config.layer_patterns)
    save_graph_cache(graph, root)
    return graph


def check_full(
    source: str,
    target: str,
    rel_type: str,
    config: RubiconConfig,
    root: Path,
) -> PreflightResult:
    """Check a proposed relationship including cycle detection.

    Runs check_fast() first; if already violated, returns immediately without
    loading the graph. Otherwise loads or builds the dependency graph, adds the
    proposed edge (inserting stub nodes for files not yet in the graph), and
    checks for new import cycles and single_responsibility threshold crossings.
    Cycle detection only applies when rel_type is "import" and the
    no_circular_imports rule is enabled.

    Args:
        source: Source file path (need not exist on disk).
        target: Target import string (file path, module name, etc.).
        rel_type: "import" or "inheritance".
        config: Loaded .rubicon configuration.
        root: Project root for graph loading and import resolution.

    Returns:
        PreflightResult with cycle_detection_run=True only when the graph was loaded.
    """
    fast_result = check_fast(source, target, rel_type, config, root)
    if not fast_result.allowed:
        return fast_result

    # Load / build graph
    graph = _load_or_build_graph(config, root)
    augmented = graph.copy()

    # Resolve target; add stub nodes for files not yet in the graph
    resolved_target, _ = resolve_import_target(target, root, config)
    _ensure_node(augmented, source, fast_result.source_layer)
    target_node_id = resolved_target or target
    if fast_result.target_layer is not None:
        _ensure_node(augmented, target_node_id, fast_result.target_layer)
        target_node: str | None = target_node_id
    else:
        target_node = None

    violations: list[PreflightViolation] = list(fast_result.violations)

    if target_node:
        _add_stub_edge(augmented, source, target_node, rel_type)

        # Cycle detection only for import edges; no_circular_ownership uses
        # RelationshipType.OWNERSHIP (not INHERITANCE) so skip it here.
        if rel_type == "import" and "no_circular_imports" in config.rules:
            violations.extend(_filter_new_cycles(
                augmented, graph,
                RelationshipType.IMPORT, "no_circular_imports", Severity.WARNING, "Circular import",
            ))

        if "single_responsibility" in config.rules:
            original_layers = _connected_layers(graph, source) if source in graph else set()
            augmented_layers = _connected_layers(augmented, source)
            if len(augmented_layers) >= 4 and len(original_layers) < 4:
                violations.append(PreflightViolation(
                    rule="single_responsibility",
                    severity="info",
                    message=f"{source} would be connected to {len(augmented_layers)} layers "
                            f"({', '.join(sorted(augmented_layers))}); "
                            f"consider splitting responsibilities",
                ))

    return PreflightResult(
        allowed=len(violations) == 0,
        source=source,
        source_layer=fast_result.source_layer,
        target=target,
        target_layer=fast_result.target_layer,
        relationship_type=rel_type,
        violations=tuple(violations),
        cycle_detection_run=True,
    )
