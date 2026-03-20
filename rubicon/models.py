"""Shared data models used across all architectural layers.

This module is the foundation of the Rubicon type system. Every layer
may import from here without creating cross-layer dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RelationshipType(Enum):
    """Type of relationship between two code symbols."""

    IMPORT = "import"
    INHERITANCE = "inheritance"
    OWNERSHIP = "ownership"
    FUNCTION_CALL = "function_call"


class Severity(Enum):
    """Severity level for rule violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Language(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    C = "c"
    CPP = "cpp"
    RUBY = "ruby"


# ---------------------------------------------------------------------------
# Graph data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Relationship:
    """A single relationship between two code symbols."""

    source: str
    target: str
    type: RelationshipType
    source_file: Path
    line_number: int


@dataclass
class Node:
    """A node in the architecture graph, representing a file."""

    id: str
    file_path: Path
    symbols: list[str] = field(default_factory=list)
    language: str = ""
    layer: str = "unclassified"


@dataclass(frozen=True)
class Edge:
    """A directed edge between two nodes, carrying one or more relationships."""

    source_id: str
    target_id: str
    relationships: tuple[Relationship, ...] = ()


@dataclass(frozen=True)
class Violation:
    """A rule violation detected in the architecture graph."""

    rule: str
    severity: Severity
    source_node_id: str
    target_node_id: str | None
    message: str
    relationship: Relationship | None = None


# ---------------------------------------------------------------------------
# Crawler data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceFile:
    """A discovered source file with language and content."""

    path: Path
    language: str
    content: str
    hash: str


# ---------------------------------------------------------------------------
# Configuration data models
# ---------------------------------------------------------------------------

ALL_BUILTIN_RULES: list[str] = [
    "no_upward_dependency",
    "no_layer_skipping",
    "inheritance_flows_downward",
    "no_circular_ownership",
    "no_circular_imports",
    "dependency_inversion",
    "single_responsibility",
    "orphan_detection",
]


@dataclass
class LayerConfig:
    """Configuration for a single architectural layer."""

    directories: list[str] = field(default_factory=list)
    color: str = ""


@dataclass
class CustomRuleConfig:
    """A user-defined architecture rule from .rubicon config."""

    name: str = ""
    pattern: str = ""
    layer: str = ""
    source_layer: str = ""
    forbidden_imports: list[str] = field(default_factory=list)
    message: str = ""
    severity: str = "warning"


@dataclass
class RubiconConfig:
    """Parsed .rubicon configuration."""

    layers: dict[str, LayerConfig] = field(default_factory=dict)
    layer_order: list[str] = field(default_factory=list)
    foundation_layers: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=lambda: list(ALL_BUILTIN_RULES))
    custom_rules: list[CustomRuleConfig] = field(default_factory=list)

    @property
    def layer_map(self) -> dict[str, list[str]]:
        """Return layer name -> directory list mapping for use with apply_layers."""
        return {name: lc.directories for name, lc in self.layers.items()}

    def layer_index(self, layer_name: str) -> int | None:
        """Return the position of a layer in the layer order, or None if absent."""
        try:
            return self.layer_order.index(layer_name)
        except ValueError:
            return None
