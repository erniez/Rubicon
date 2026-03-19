"""Ruby language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "String", "Integer", "Float", "Symbol", "Array", "Hash",
    "NilClass", "TrueClass", "FalseClass", "Regexp", "Range",
    "Proc", "Lambda", "IO", "File", "Dir", "Time", "Date",
    "Numeric", "Comparable", "Enumerable", "Kernel", "Object",
    "BasicObject", "Module", "Class",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Ruby file."""
    root = tree.root_node  # type: ignore[union-attr]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract require and require_relative statements."""
    for node in _walk(root):
        if node.type != "call":
            continue

        method_name = ""
        for child in node.children:
            if child.type == "identifier":
                method_name = child.text.decode() if child.text else ""
                break

        if method_name not in ("require", "require_relative"):
            continue

        # The argument is in an argument_list containing a string node
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "string":
                        module = _get_string_content(arg)
                        if module:
                            results.append(Relationship(
                                source=str(source_file),
                                target=module,
                                type=RelationshipType.IMPORT,
                                source_file=source_file,
                                line_number=node.start_point[0] + 1,
                            ))
                break
            # require 'json' without parens — argument is a direct string child
            if child.type == "string":
                module = _get_string_content(child)
                if module:
                    results.append(Relationship(
                        source=str(source_file),
                        target=module,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))
                break


def _extract_classes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class declarations."""
    for node in _walk(root):
        if node.type != "class":
            continue

        class_name = _get_class_name(node)
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
    """Extract superclass and included/extended modules."""
    for child in class_node.children:
        # Superclass: class Dog < Animal
        if child.type == "superclass":
            base = _get_constant_name(child)
            if base and base not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=class_name,
                    target=base,
                    type=RelationshipType.INHERITANCE,
                    source_file=source_file,
                    line_number=class_node.start_point[0] + 1,
                ))

    # Include/extend inside class body
    body = _get_class_body(class_node)
    if body is None:
        return

    for node in _walk(body):
        if node.type != "call":
            continue

        method_name = ""
        for child in node.children:
            if child.type == "identifier":
                method_name = child.text.decode() if child.text else ""
                break

        if method_name not in ("include", "extend"):
            continue

        # Get the constant argument
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "constant":
                        mod_name = arg.text.decode() if arg.text else ""
                        if mod_name and mod_name not in BUILTIN_TYPES:
                            results.append(Relationship(
                                source=class_name,
                                target=mod_name,
                                type=RelationshipType.INHERITANCE,
                                source_file=source_file,
                                line_number=node.start_point[0] + 1,
                            ))
                    elif arg.type == "scope_resolution":
                        mod_name = arg.text.decode() if arg.text else ""
                        if mod_name and mod_name not in BUILTIN_TYPES:
                            results.append(Relationship(
                                source=class_name,
                                target=mod_name,
                                type=RelationshipType.INHERITANCE,
                                source_file=source_file,
                                line_number=node.start_point[0] + 1,
                            ))
                break
            # Without parens: include Pet
            if child.type == "constant":
                mod_name = child.text.decode() if child.text else ""
                if mod_name and mod_name not in BUILTIN_TYPES:
                    results.append(Relationship(
                        source=class_name,
                        target=mod_name,
                        type=RelationshipType.INHERITANCE,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))
                break


def _extract_ownership(
    class_node: Node,
    class_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract ownership from constructor assignments like @engine = Engine.new."""
    body = _get_class_body(class_node)
    if body is None:
        return

    # Find initialize method
    for node in _walk(body):
        if node.type != "method":
            continue

        method_name = ""
        for child in node.children:
            if child.type == "identifier":
                method_name = child.text.decode() if child.text else ""
                break

        if method_name != "initialize":
            continue

        # Look for assignments: @var = Type.new
        for assign_node in _walk(node):
            if assign_node.type != "assignment":
                continue

            # Check left side is an instance variable
            left = assign_node.children[0] if assign_node.children else None
            if left is None or left.type != "instance_variable":
                continue

            # Check right side is a call like Type.new
            right = assign_node.children[-1] if len(assign_node.children) > 1 else None
            if right is None or right.type != "call":
                continue

            type_name = _get_constructor_type(right)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=class_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=assign_node.start_point[0] + 1,
                ))


def _get_class_name(class_node: Node) -> str:
    """Get the name from a class node."""
    for child in class_node.children:
        if child.type == "constant":
            return child.text.decode() if child.text else ""
        if child.type == "scope_resolution":
            return child.text.decode() if child.text else ""
    return ""


def _get_class_body(class_node: Node) -> Node | None:
    """Get the body node of a class."""
    for child in class_node.children:
        if child.type == "body_statement":
            return child
    return None


def _get_constant_name(node: Node) -> str:
    """Get the constant name from a superclass or similar node."""
    for child in node.children:
        if child.type == "constant":
            return child.text.decode() if child.text else ""
        if child.type == "scope_resolution":
            return child.text.decode() if child.text else ""
    return ""


def _get_string_content(string_node: Node) -> str:
    """Extract the content from a string node, stripping quotes."""
    for child in string_node.children:
        if child.type == "string_content":
            return child.text.decode() if child.text else ""
    # Fallback: decode the whole text and strip quotes
    text = string_node.text.decode() if string_node.text else ""
    return text.strip("'\"")


def _get_constructor_type(call_node: Node) -> str:
    """Extract type name from a Type.new call node.

    Looks for a call where the receiver is a constant and the method is 'new'.
    """
    receiver = None
    method = ""

    for child in call_node.children:
        if child.type == "constant":
            receiver = child.text.decode() if child.text else ""
        if child.type == "identifier":
            method = child.text.decode() if child.text else ""
        if child.type == ".":
            continue

    if receiver and method == "new":
        return receiver
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
