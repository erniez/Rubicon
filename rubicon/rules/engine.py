"""Rule engine: runs all enabled rules and collects violations."""

from typing import Callable

import networkx as nx

from rubicon.models import RubiconConfig, Violation
from rubicon.rules import builtin

# Map rule names to their implementation functions
RULE_REGISTRY: dict[str, Callable[[nx.DiGraph, RubiconConfig], list[Violation]]] = {
    "no_upward_dependency": builtin.no_upward_dependency,
    "no_layer_skipping": builtin.no_layer_skipping,
    "inheritance_flows_downward": builtin.inheritance_flows_downward,
    "no_circular_ownership": builtin.no_circular_ownership,
    "no_circular_imports": builtin.no_circular_imports,
    "dependency_inversion": builtin.dependency_inversion,
    "single_responsibility": builtin.single_responsibility,
    "orphan_detection": builtin.orphan_detection,
}


def run_rules(
    graph: nx.DiGraph, config: RubiconConfig
) -> list[Violation]:
    """Run all enabled rules against the graph and return violations."""
    violations: list[Violation] = []

    for rule_name in config.rules:
        rule_fn = RULE_REGISTRY.get(rule_name)
        if rule_fn is None:
            continue
        violations.extend(rule_fn(graph, config))

    # Run custom rules from .rubicon config
    if config.custom_rules:
        from rubicon.rules.custom import run_custom_rules
        violations.extend(run_custom_rules(graph, config))

    return violations
