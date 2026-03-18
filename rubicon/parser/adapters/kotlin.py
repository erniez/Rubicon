"""Kotlin language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "String", "Int", "Long", "Short", "Byte", "Float", "Double",
    "Boolean", "Char", "Unit", "Nothing", "Any",
    "List", "MutableList", "Map", "MutableMap", "Set", "MutableSet",
    "Array", "Sequence", "Pair", "Triple",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Kotlin file."""
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
        if node.type != "import":
            continue

        for child in node.children:
            if child.type == "qualified_identifier":
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
        _extract_ownership_body(node, class_name, source_file, results)
        _extract_ownership_constructor(node, class_name, source_file, results)


def _extract_inheritance(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract supertypes from delegation_specifiers."""
    for child in class_node.children:
        if child.type != "delegation_specifiers":
            continue
        for spec in child.children:
            if spec.type != "delegation_specifier":
                continue
            for item in spec.children:
                if item.type == "constructor_invocation":
                    # class Dog : Animal()
                    for sub in item.children:
                        if sub.type == "user_type":
                            base = _get_user_type_name(sub)
                            if base:
                                results.append(Relationship(
                                    source=class_name,
                                    target=base,
                                    type=RelationshipType.INHERITANCE,
                                    source_file=source_file,
                                    line_number=class_node.start_point[0] + 1,
                                ))
                elif item.type == "user_type":
                    # interface implementation: class Dog : Pet
                    base = _get_user_type_name(item)
                    if base:
                        results.append(Relationship(
                            source=class_name,
                            target=base,
                            type=RelationshipType.INHERITANCE,
                            source_file=source_file,
                            line_number=class_node.start_point[0] + 1,
                        ))


def _extract_ownership_body(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract typed property declarations from the class body."""
    for child in class_node.children:
        if child.type != "class_body":
            continue
        for member in child.children:
            if member.type != "property_declaration":
                continue
            type_name = _get_property_type(member)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=class_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=member.start_point[0] + 1,
                ))


def _extract_ownership_constructor(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract typed parameters from primary constructor (data classes, etc.)."""
    for child in class_node.children:
        if child.type != "primary_constructor":
            continue
        for params in child.children:
            if params.type != "class_parameters":
                continue
            for param in params.children:
                if param.type != "class_parameter":
                    continue
                type_name = _get_param_type(param)
                if type_name and type_name not in BUILTIN_TYPES:
                    results.append(Relationship(
                        source=class_name,
                        target=type_name,
                        type=RelationshipType.OWNERSHIP,
                        source_file=source_file,
                        line_number=param.start_point[0] + 1,
                    ))


def _get_user_type_name(user_type_node: Node) -> str:
    """Get the simple name from a user_type node."""
    for child in user_type_node.children:
        if child.type == "identifier":
            return child.text.decode() if child.text else ""
    return ""


def _get_property_type(prop_node: Node) -> str:
    """Get type name from a property_declaration's variable_declaration."""
    for child in prop_node.children:
        if child.type == "variable_declaration":
            for sub in child.children:
                if sub.type == "user_type":
                    return _get_user_type_name(sub)
    return ""


def _get_param_type(param_node: Node) -> str:
    """Get type name from a class_parameter."""
    for child in param_node.children:
        if child.type == "user_type":
            return _get_user_type_name(child)
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
