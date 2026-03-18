"""Swift language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "String", "Int", "Int8", "Int16", "Int32", "Int64",
    "UInt", "UInt8", "UInt16", "UInt32", "UInt64",
    "Float", "Double", "Bool", "Void", "Never",
    "Any", "AnyObject", "AnyClass",
    "Array", "Dictionary", "Set", "Optional",
    "Character", "Data", "URL", "Date", "UUID",
    "CGFloat", "CGPoint", "CGSize", "CGRect",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Swift file."""
    root = tree.root_node  # type: ignore[union-attr]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_types(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract import declarations."""
    for node in _walk(root):
        if node.type != "import_declaration":
            continue

        for child in node.children:
            if child.type == "identifier":
                module = child.text.decode() if child.text else ""
                if module:
                    results.append(Relationship(
                        source=str(source_file),
                        target=module,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))


def _extract_types(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class/struct/enum declarations."""
    for node in _walk(root):
        if node.type != "class_declaration":
            continue

        # Determine what kind of type (class, struct, enum)
        type_name = ""
        for child in node.children:
            if child.type == "type_identifier":
                type_name = child.text.decode() if child.text else ""
                break

        if not type_name:
            continue

        _extract_inheritance(node, type_name, source_file, results)
        _extract_ownership(node, type_name, source_file, results)


def _extract_inheritance(
    type_node: Node,
    type_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract superclass and protocol conformance from inheritance specifiers."""
    for child in type_node.children:
        if child.type != "inheritance_specifier":
            continue
        for sub in child.children:
            if sub.type == "user_type":
                for item in sub.children:
                    if item.type == "type_identifier":
                        base = item.text.decode() if item.text else ""
                        if base:
                            results.append(Relationship(
                                source=type_name,
                                target=base,
                                type=RelationshipType.INHERITANCE,
                                source_file=source_file,
                                line_number=type_node.start_point[0] + 1,
                            ))


def _extract_ownership(
    type_node: Node,
    type_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract typed property declarations from class/struct body."""
    for child in type_node.children:
        if child.type not in ("class_body", "enum_class_body"):
            continue
        for member in child.children:
            if member.type != "property_declaration":
                continue
            field_type = _get_property_type(member)
            if field_type and field_type not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=type_name,
                    target=field_type,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=member.start_point[0] + 1,
                ))


def _get_property_type(prop_node: Node) -> str:
    """Get the type name from a property declaration's type annotation."""
    for child in prop_node.children:
        if child.type == "type_annotation":
            for sub in child.children:
                if sub.type == "user_type":
                    for item in sub.children:
                        if item.type == "type_identifier":
                            return item.text.decode() if item.text else ""
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
