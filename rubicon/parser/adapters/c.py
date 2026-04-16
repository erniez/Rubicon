"""C language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "int", "long", "short", "char", "float", "double", "void",
    "size_t", "ssize_t", "ptrdiff_t", "intptr_t", "uintptr_t",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "bool", "FILE", "unsigned", "signed",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract includes and ownership from a C file."""
    root = tree.root_node  # type: ignore[attr-defined]
    relationships: list[Relationship] = []

    _extract_includes(root, source_file, relationships)
    _extract_structs(root, source_file, relationships)

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
                # <stdio.h> -> strip angle brackets
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


def _extract_structs(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract ownership from struct declarations."""
    for node in _walk(root):
        if node.type != "struct_specifier":
            continue

        struct_name = ""
        for child in node.children:
            if child.type == "type_identifier":
                struct_name = child.text.decode() if child.text else ""
                break

        if not struct_name:
            continue

        _extract_ownership(node, struct_name, source_file, results)


def _extract_ownership(
    struct_node: Node,
    struct_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract field types from a struct's field_declaration_list."""
    for child in struct_node.children:
        if child.type != "field_declaration_list":
            continue

        for field_decl in child.children:
            if field_decl.type != "field_declaration":
                continue

            type_name = _get_field_type(field_decl)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=struct_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=field_decl.start_point[0] + 1,
                ))


def _get_field_type(field_decl: Node) -> str:
    """Get the type name from a field_declaration node.

    Returns the type identifier for non-primitive types, or the
    primitive_type text. Only returns a value if the field has a
    field_identifier (i.e., it is a data field, not a function).
    """
    has_field_id = False
    type_name = ""

    for child in field_decl.children:
        if child.type == "field_identifier":
            has_field_id = True
        elif child.type == "array_declarator":
            # e.g., char name[32] -- the field_identifier is inside the array_declarator
            for sub in child.children:
                if sub.type == "field_identifier":
                    has_field_id = True
                    break
        elif child.type == "type_identifier":
            type_name = child.text.decode() if child.text else ""
        elif child.type == "primitive_type":
            type_name = child.text.decode() if child.text else ""

    if has_field_id and type_name:
        return type_name
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
