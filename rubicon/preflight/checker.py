"""Pre-flight architecture rule checking.

check_fast(): Layer-only checks (~30ms). No graph build required.
check_full(): Layer checks + cycle detection. Loads or builds graph.
get_allowed_imports(): Query which layers a file may import from.
check_batch(): Validate multiple proposed changes at once.
"""

import fnmatch
from pathlib import Path

from rubicon.models import RubiconConfig
from rubicon.preflight.models import (
    AllowedImportsResult,
    BatchPreflightResult,
    PreflightResult,
    PreflightViolation,
)
from rubicon.preflight.resolver import classify_path, resolve_import_target
from rubicon.rules.builtin import ABSTRACTION_INDICATORS


def check_fast(
    source: str,
    target: str,
    rel_type: str,
    config: RubiconConfig,
    root: Path,
) -> PreflightResult:
    """Check a proposed relationship using layer indices only.

    Does not build or load the dependency graph, so cycle detection is skipped.
    Covers: no_upward_dependency, no_layer_skipping, inheritance_flows_downward,
    dependency_inversion (path heuristic only), and custom forbidden_imports.

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
        if rel_type == "import" and source_idx > target_idx:
            violations.append(PreflightViolation(
                rule="no_upward_dependency",
                severity="warning",
                message=f"{source_layer} (index {source_idx}) cannot import "
                        f"{target_layer} (index {target_idx}) — upward dependency",
            ))

        # no_layer_skipping: cannot skip intermediate layers
        if (
            source_layer != target_layer
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
        if rel_type == "inheritance" and source_idx < target_idx:
            violations.append(PreflightViolation(
                rule="inheritance_flows_downward",
                severity="error",
                message=f"{source} ({source_layer}) inherits from {target} ({target_layer}), "
                        f"but inheritance must flow downward",
            ))

        # dependency_inversion: cross-layer inheritance to a concrete-looking target
        # Path-only heuristic; symbol-level detection requires a full graph.
        if (
            rel_type == "inheritance"
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
    # Normalise path separators and split into parts
    parts = target.replace("\\", "/").replace(".", "/").split("/")
    for part in parts:
        if part in ABSTRACTION_INDICATORS:
            return True
        for indicator in ABSTRACTION_INDICATORS:
            if len(part) > len(indicator) and (
                part.lower().startswith(indicator.lower())
                or part.lower().endswith(indicator.lower())
            ):
                return True
    return False
