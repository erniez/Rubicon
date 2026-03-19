"""C++ language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "int", "long", "short", "char", "float", "double", "void", "bool", "auto",
    "size_t", "ssize_t", "ptrdiff_t",
    "string", "wstring",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "vector", "map", "set", "unordered_map", "unordered_set",
    "list", "deque", "array",
    "shared_ptr", "unique_ptr", "weak_ptr",
    "optional", "pair", "tuple",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract includes, inheritance, and ownership from a C++ file."""
    root = tree.root_node  # type: ignore[union-attr]
    relationships: list[Relationship] = []

    _extract_includes(root, source_file, relationships)
    _extract_classes(root, source_file, relationships)

    return relationships


def _extract_includes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract #include directives."""
    for node in _walk(root):
        if node.type != "preproc_include":
            continue

        for child in node.children:
            if child.type == "system_lib_string":
                # <iostream> -> strip angle brackets
                raw = child.text.decode() if child.text else ""
                header = raw.strip("<>")
                if header:
                    results.append(Relationship(
                        source=str(source_file),
                        target=header,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))
            elif child.type == "string_literal":
                # "mylib.h" -> extract from string_content child
                header = _get_string_content(child)
                if header:
                    results.append(Relationship(
                        source=str(source_file),
                        target=header,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=node.start_point[0] + 1,
                    ))


def _extract_classes(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance and ownership from class and struct declarations."""
    for node in _walk(root):
        if node.type not in ("class_specifier", "struct_specifier"):
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
    """Extract base classes from base_class_clause.

    The base_class_clause contains interleaved access_specifier and
    type_identifier children (e.g., : public Animal, public Pet).
    """
    for child in class_node.children:
        if child.type != "base_class_clause":
            continue

        for item in child.children:
            if item.type == "type_identifier":
                base = item.text.decode() if item.text else ""
                if base:
                    results.append(Relationship(
                        source=class_name,
                        target=base,
                        type=RelationshipType.INHERITANCE,
                        source_file=source_file,
                        line_number=class_node.start_point[0] + 1,
                    ))
            elif item.type == "qualified_identifier":
                # e.g., std::Base
                base = item.text.decode() if item.text else ""
                if base:
                    results.append(Relationship(
                        source=class_name,
                        target=base,
                        type=RelationshipType.INHERITANCE,
                        source_file=source_file,
                        line_number=class_node.start_point[0] + 1,
                    ))
            elif item.type == "template_type":
                # e.g., Base<T>
                base = _get_template_base_name(item)
                if base:
                    results.append(Relationship(
                        source=class_name,
                        target=base,
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
    """Extract field types from a class or struct's field_declaration_list."""
    for child in class_node.children:
        if child.type != "field_declaration_list":
            continue

        for field_decl in child.children:
            if field_decl.type != "field_declaration":
                continue

            type_name = _get_field_type(field_decl)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=class_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=field_decl.start_point[0] + 1,
                ))


def _get_field_type(field_decl: Node) -> str:
    """Get the type name from a field_declaration node.

    Returns a type name only if the declaration is a data field
    (has a field_identifier), not a function declaration.
    """
    has_field_id = False
    type_name = ""

    for child in field_decl.children:
        if child.type == "field_identifier":
            has_field_id = True
        elif child.type == "array_declarator":
            for sub in child.children:
                if sub.type == "field_identifier":
                    has_field_id = True
                    break
        elif child.type == "function_declarator":
            # This is a method declaration, not a field
            return ""
        elif child.type == "type_identifier":
            type_name = child.text.decode() if child.text else ""
        elif child.type == "primitive_type":
            type_name = child.text.decode() if child.text else ""
        elif child.type == "template_type":
            type_name = _get_template_base_name(child)
        elif child.type == "qualified_identifier":
            type_name = child.text.decode() if child.text else ""

    if has_field_id and type_name:
        return type_name
    return ""


def _get_template_base_name(template_type: Node) -> str:
    """Get the base type name from a template_type node (e.g., vector<int> -> vector)."""
    for child in template_type.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
    return ""


def _get_string_content(string_literal: Node) -> str:
    """Extract the content from a string_literal node (without quotes)."""
    for child in string_literal.children:
        if child.type == "string_content":
            return child.text.decode() if child.text else ""
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
