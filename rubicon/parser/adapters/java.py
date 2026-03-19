"""Java language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "int", "long", "short", "byte", "float", "double", "boolean", "char", "void",
    "String", "Integer", "Long", "Short", "Byte", "Float", "Double", "Boolean",
    "Character", "Object", "List", "Map", "Set", "Collection", "Iterable",
    "Optional", "Array",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Java file."""
    root = tree.root_node  # type: ignore[union-attr]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract import statements."""
    for node in _walk(root):
        if node.type != "import_declaration":
            continue

        for child in node.children:
            if child.type == "scoped_identifier":
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
    """Extract superclass and implemented interfaces."""
    for child in class_node.children:
        if child.type == "superclass":
            # superclass contains an 'extends' keyword and a type_identifier
            for sub in child.children:
                if sub.type == "type_identifier":
                    base = sub.text.decode() if sub.text else ""
                    if base:
                        results.append(Relationship(
                            source=class_name,
                            target=base,
                            type=RelationshipType.INHERITANCE,
                            source_file=source_file,
                            line_number=class_node.start_point[0] + 1,
                        ))
        elif child.type == "super_interfaces":
            # super_interfaces contains 'implements' keyword and a type_list
            for sub in child.children:
                if sub.type == "type_list":
                    for item in sub.children:
                        if item.type == "type_identifier":
                            iface = item.text.decode() if item.text else ""
                            if iface:
                                results.append(Relationship(
                                    source=class_name,
                                    target=iface,
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


def _get_field_type(field_node: Node) -> str:
    """Get the type name from a field_declaration.

    Handles type_identifier, generic_type, and scoped_type_identifier.
    For generic types (e.g., List<String>), returns the outer type name.
    For scoped types (e.g., com.example.Bar), returns the last identifier.
    """
    for child in field_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
        if child.type == "generic_type":
            # generic_type -> type_identifier, type_arguments
            for sub in child.children:
                if sub.type == "type_identifier":
                    return sub.text.decode() if sub.text else ""
        if child.type == "scoped_type_identifier":
            return _get_scoped_type_name(child)
    return ""


def _get_scoped_type_name(scoped_node: Node) -> str:
    """Get the last (simple) name from a scoped_type_identifier.

    For com.example.Bar, returns 'Bar'.
    """
    # The last type_identifier child is the simple name
    last_name = ""
    for child in scoped_node.children:
        if child.type == "type_identifier":
            last_name = child.text.decode() if child.text else ""
    return last_name


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
