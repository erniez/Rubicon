"""TypeScript language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "string", "number", "boolean", "void", "null", "undefined",
    "any", "never", "unknown", "object", "symbol", "bigint",
    "Array", "Map", "Set", "Promise", "Record", "Partial", "Required",
    "Readonly", "Pick", "Omit",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a TypeScript file."""
    root = tree.root_node  # type: ignore[attr-defined]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract import statements."""
    for node in _walk(root):
        if node.type != "import_statement":
            continue

        source_str = _get_import_source(node)
        if source_str:
            results.append(Relationship(
                source=str(source_file),
                target=source_str,
                type=RelationshipType.IMPORT,
                source_file=source_file,
                line_number=node.start_point[0] + 1,
            ))


def _get_import_source(node: Node) -> str:
    """Extract the module path string from an import statement."""
    for child in node.children:
        if child.type == "string":
            for sub in child.children:
                if sub.type == "string_fragment":
                    return sub.text.decode() if sub.text else ""
    return ""


def _extract_classes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class declarations."""
    for node in _walk(root):
        if node.type != "class_declaration":
            continue

        class_name = ""
        for child in node.children:
            if child.type == "type_identifier":
                class_name = child.text.decode() if child.text else ""
                break

        if not class_name:
            continue

        _extract_inheritance(node, class_name, source_file, results)
        _extract_ownership(node, class_name, source_file, results)


def _extract_inheritance(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract extends and implements clauses."""
    for child in class_node.children:
        if child.type != "class_heritage":
            continue
        for clause in child.children:
            if clause.type in ("extends_clause", "implements_clause"):
                for item in clause.children:
                    if item.type in ("identifier", "type_identifier"):
                        base_name = item.text.decode() if item.text else ""
                        if base_name:
                            results.append(Relationship(
                                source=class_name,
                                target=base_name,
                                type=RelationshipType.INHERITANCE,
                                source_file=source_file,
                                line_number=class_node.start_point[0] + 1,
                            ))


def _extract_ownership(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract typed field declarations from the class body."""
    for child in class_node.children:
        if child.type != "class_body":
            continue
        for member in child.children:
            if member.type != "public_field_definition":
                continue
            type_name = _get_field_type(member)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=class_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=member.start_point[0] + 1,
                ))


def _get_field_type(field_node: Node) -> str:
    """Get the type name from a field's type annotation."""
    for child in field_node.children:
        if child.type == "type_annotation":
            for sub in child.children:
                if sub.type == "type_identifier":
                    return sub.text.decode() if sub.text else ""
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
