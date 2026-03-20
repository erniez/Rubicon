"""Custom user-defined architecture rules from .rubicon config."""

import fnmatch
import logging

import networkx as nx

from rubicon.models import (
    CustomRuleConfig,
    RelationshipType,
    RubiconConfig,
    Severity,
    Violation,
)

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
}


def run_custom_rules(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Run all custom rules defined in .rubicon config."""
    violations: list[Violation] = []

    for rule in config.custom_rules:
        if rule.pattern and rule.layer:
            violations.extend(_check_file_layer(graph, rule))
        elif rule.source_layer and rule.forbidden_imports:
            violations.extend(_check_forbidden_imports(graph, rule))
        else:
            logger.warning("Custom rule %r has incomplete config, skipping", rule.name)

    return violations


def _check_file_layer(
    graph: nx.DiGraph, rule: CustomRuleConfig
) -> list[Violation]:
    """Files matching a glob pattern must be in the specified layer."""
    violations: list[Violation] = []
    severity = _SEVERITY_MAP.get(rule.severity, Severity.WARNING)

    for node_id in graph.nodes:
        if not fnmatch.fnmatch(node_id, rule.pattern):
            continue

        actual_layer = graph.nodes[node_id].get("layer", "unclassified")
        if actual_layer == rule.layer or actual_layer == "unclassified":
            continue

        message = rule.message or f"{node_id} matches {rule.pattern} but is in {actual_layer}, not {rule.layer}"
        violations.append(Violation(
            rule=rule.name or "custom_file_layer",
            severity=severity,
            source_node_id=node_id,
            target_node_id=None,
            message=message,
        ))

    return violations


def _check_forbidden_imports(
    graph: nx.DiGraph, rule: CustomRuleConfig
) -> list[Violation]:
    """Files in a layer must not import from forbidden packages."""
    violations: list[Violation] = []
    severity = _SEVERITY_MAP.get(rule.severity, Severity.WARNING)

    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        if source_layer != rule.source_layer:
            continue

        for rel in data.get("relationships", []):
            if rel.type != RelationshipType.IMPORT:
                continue

            for forbidden in rule.forbidden_imports:
                if forbidden in rel.target:
                    message = rule.message or f"{source_id} in {rule.source_layer} imports {rel.target} (forbidden: {forbidden})"
                    violations.append(Violation(
                        rule=rule.name or "custom_forbidden_import",
                        severity=severity,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        message=message,
                        relationship=rel,
                    ))

    return violations
