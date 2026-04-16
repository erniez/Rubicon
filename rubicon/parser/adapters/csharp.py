"""C# language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "int", "long", "short", "byte", "float", "double", "decimal",
    "bool", "char", "string", "void", "object", "dynamic", "var",
    "Int32", "Int64", "Int16", "Byte", "Single", "Double", "Decimal",
    "Boolean", "Char", "String", "Object",
    "List", "Dictionary", "HashSet",
    "IEnumerable", "IList", "IDictionary",
    "Task", "Action", "Func",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a C# file."""
    root = tree.root_node  # type: ignore[attr-defined]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract using directives."""
    for node in _walk(root):
        if node.type != "using_directive":
            continue

        for child in node.children:
            if child.type in ("qualified_name", "identifier"):
                module = child.text.decode() if child.text else ""
                if module:
                    results.append(Relationship(
                        source=str(source_file),
                        target=module,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))


def _extract_classes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class declarations."""
    for node in _walk(root):
        if node.type != "class_declaration":
            continue

        class_name = ""
        for child in node.children:
            if child.type == "identifier":
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
    """Extract supertypes from base_list."""
    for child in class_node.children:
        if child.type != "base_list":
            continue
        for item in child.children:
            type_name = _get_type_name(item)
            if type_name:
                results.append(Relationship(
                    source=class_name,
                    target=type_name,
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
        if child.type != "declaration_list":
            continue
        for member in child.children:
            if member.type != "field_declaration":
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


def _get_type_name(node: Node) -> str:
    """Extract a type name from an identifier, qualified_name, or generic_name node.

    Handles base_list entries which may be wrapped in various node types.
    Recurses into children to find the actual type identifier.
    """
    if node.type == "identifier":
        return node.text.decode() if node.text else ""
    if node.type == "qualified_name":
        # Return the last identifier segment (e.g., Generic.IComparable -> IComparable)
        for child in reversed(node.children):
            if child.type == "identifier":
                return child.text.decode() if child.text else ""
        return ""
    if node.type == "generic_name":
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode() if child.text else ""
        return ""
    # Recurse into children for wrapper nodes
    for child in node.children:
        name = _get_type_name(child)
        if name:
            return name
    return ""


def _get_field_type(field_node: Node) -> str:
    """Extract the type name from a field_declaration's variable_declaration."""
    for child in field_node.children:
        if child.type == "variable_declaration":
            for sub in child.children:
                name = _get_type_name(sub)
                if name:
                    return name
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
