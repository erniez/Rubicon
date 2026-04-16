"""Python language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

# Built-in types that should not be treated as ownership relationships
BUILTIN_TYPES = frozenset({
    "str", "int", "float", "bool", "bytes", "list", "dict", "set", "tuple",
    "None", "Any", "Optional", "Union", "List", "Dict", "Set", "Tuple",
    "Sequence", "Mapping", "Iterable", "Iterator", "Callable", "Type",
    "ClassVar", "Final",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Python file."""
    root = tree.root_node  # type: ignore[attr-defined]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract import relationships from import statements."""
    for node in _walk(root):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    module = child.text.decode() if child.text else ""
                    results.append(Relationship(
                        source=str(source_file),
                        target=module,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))

        elif node.type == "import_from_statement":
            module = _get_import_from_module(node)
            if module:
                results.append(Relationship(
                    source=str(source_file),
                    target=module,
                    type=RelationshipType.IMPORT,
                    source_file=source_file,
                    line_number=node.start_point[0] + 1,
                ))


def _get_import_from_module(node: Node) -> str:
    """Extract the module path from a 'from X import Y' statement."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "dotted_name" and not parts:
            return child.text.decode() if child.text else ""
        if child.type == "relative_import":
            prefix = ""
            for sub in child.children:
                if sub.type == "import_prefix":
                    prefix = sub.text.decode() if sub.text else ""
                elif sub.type == "dotted_name":
                    return prefix + (sub.text.decode() if sub.text else "")
            return prefix
    return ""


def _extract_classes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class definitions."""
    for node in _walk(root):
        if node.type != "class_definition":
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
    """Extract base classes from a class definition."""
    for child in class_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "identifier":
                    base_name = arg.text.decode() if arg.text else ""
                    if base_name:
                        results.append(Relationship(
                            source=class_name,
                            target=base_name,
                            type=RelationshipType.INHERITANCE,
                            source_file=source_file,
                            line_number=class_node.start_point[0] + 1,
                        ))
                elif arg.type == "attribute":
                    base_name = arg.text.decode() if arg.text else ""
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
    """Extract typed field declarations that indicate ownership."""
    body = class_node.child_by_field_name("body")
    if body is None:
        return

    for node in _walk(body):
        if node.type != "assignment":
            continue

        type_node = _get_type_annotation(node)
        if type_node is None:
            continue

        type_name = type_node.text.decode() if type_node.text else ""
        if type_name and type_name not in BUILTIN_TYPES:
            results.append(Relationship(
                source=class_name,
                target=type_name,
                type=RelationshipType.OWNERSHIP,
                source_file=source_file,
                line_number=node.start_point[0] + 1,
            ))


def _get_type_annotation(assignment_node: Node) -> Node | None:
    """Get the type annotation node from a typed assignment."""
    for child in assignment_node.children:
        if child.type == "type":
            for sub in child.children:
                if sub.type == "identifier":
                    return sub
    return None


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
