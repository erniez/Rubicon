"""Go language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "string", "int", "int8", "int16", "int32", "int64",
    "uint", "uint8", "uint16", "uint32", "uint64",
    "float32", "float64", "complex64", "complex128",
    "bool", "byte", "rune", "error", "any", "comparable",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Go file."""
    root = tree.root_node  # type: ignore[attr-defined]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_structs(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract import declarations (single and grouped)."""
    for node in _walk(root):
        if node.type != "import_declaration":
            continue

        for child in node.children:
            if child.type == "import_spec":
                _add_import(child, source_file, results)
            elif child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        _add_import(spec, source_file, results)


def _add_import(
    spec_node: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract the import path from an import_spec node."""
    for child in spec_node.children:
        if child.type == "interpreted_string_literal":
            for sub in child.children:
                if sub.type == "interpreted_string_literal_content":
                    path = sub.text.decode() if sub.text else ""
                    if path:
                        results.append(Relationship(
                            source=str(source_file),
                            target=path,
                            type=RelationshipType.IMPORT,
                            source_file=source_file,
                            line_number=spec_node.start_point[0] + 1,
                        ))
                    return


def _extract_structs(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract inheritance (embedded types) and ownership from struct declarations."""
    for node in _walk(root):
        if node.type != "type_declaration":
            continue

        for child in node.children:
            if child.type != "type_spec":
                continue

            struct_name = ""
            struct_type_node: Node | None = None

            for spec_child in child.children:
                if spec_child.type == "type_identifier" and not struct_name:
                    struct_name = spec_child.text.decode() if spec_child.text else ""
                elif spec_child.type == "struct_type":
                    struct_type_node = spec_child

            if not struct_name or struct_type_node is None:
                continue

            _extract_struct_fields(
                struct_type_node, struct_name, source_file, results
            )


def _extract_struct_fields(
    struct_node: Node,
    struct_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract embedded types (inheritance) and named fields (ownership) from a struct."""
    for child in struct_node.children:
        if child.type != "field_declaration_list":
            continue

        for field in child.children:
            if field.type != "field_declaration":
                continue

            has_field_name = any(
                c.type == "field_identifier" for c in field.children
            )

            if has_field_name:
                _extract_ownership_field(
                    field, struct_name, source_file, results
                )
            else:
                _extract_embedded_type(
                    field, struct_name, source_file, results
                )


def _extract_embedded_type(
    field_node: Node,
    struct_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract an embedded (anonymous) type as an inheritance relationship."""
    type_name = _get_field_type_name(field_node)
    if type_name and type_name not in BUILTIN_TYPES:
        results.append(Relationship(
            source=struct_name,
            target=type_name,
            type=RelationshipType.INHERITANCE,
            source_file=source_file,
            line_number=field_node.start_point[0] + 1,
        ))


def _extract_ownership_field(
    field_node: Node,
    struct_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract a named field as an ownership relationship, excluding builtins."""
    type_name = _get_field_type_name(field_node)
    if type_name and type_name not in BUILTIN_TYPES:
        results.append(Relationship(
            source=struct_name,
            target=type_name,
            type=RelationshipType.OWNERSHIP,
            source_file=source_file,
            line_number=field_node.start_point[0] + 1,
        ))


def _get_field_type_name(field_node: Node) -> str:
    """Extract the type name from a field_declaration.

    Handles plain types (type_identifier), pointer types (*Type),
    qualified types (pkg.Type), and embedded pointer types (*Type without
    a field name).
    """
    for child in field_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
        if child.type == "pointer_type":
            return _resolve_pointer_type(child)
        if child.type == "qualified_type":
            return _resolve_qualified_type(child)
    return ""


def _resolve_pointer_type(pointer_node: Node) -> str:
    """Resolve the underlying type name from a pointer_type node (*Type)."""
    for child in pointer_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
        if child.type == "qualified_type":
            return _resolve_qualified_type(child)
    return ""


def _resolve_qualified_type(qualified_node: Node) -> str:
    """Resolve the type name from a qualified_type node (pkg.Type).

    Returns only the type name (e.g. 'SomeType' from 'pkg.SomeType'),
    since the package is handled as an import relationship.
    """
    for child in qualified_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
