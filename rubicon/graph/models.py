"""Core data models for the architecture graph."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


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
