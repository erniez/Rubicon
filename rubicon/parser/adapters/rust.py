"""Rust language adapter for tree-sitter relationship extraction."""

import logging
from pathlib import Path

from tree_sitter import Node

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

BUILTIN_TYPES = frozenset({
    "i8", "i16", "i32", "i64", "i128", "isize",
    "u8", "u16", "u32", "u64", "u128", "usize",
    "f32", "f64", "bool", "char", "str",
    "String", "Vec", "Box", "Option", "Result",
    "Rc", "Arc", "Cell", "RefCell",
    "HashMap", "HashSet", "BTreeMap", "BTreeSet",
})


def extract_relationships(
    tree: object, source_file: Path, content: bytes
) -> list[Relationship]:
    """Extract imports, inheritance, and ownership from a Rust file."""
    root = tree.root_node  # type: ignore[union-attr]
    relationships: list[Relationship] = []

    _extract_imports(root, source_file, relationships)
    _extract_structs(root, source_file, relationships)
    _extract_inheritance(root, source_file, relationships)

    return relationships


def _extract_imports(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract use declarations as import relationships.

    Handles simple paths (use std::collections::HashMap;) as well as
    use_list, scoped_use_list, and use_wildcard forms.
    """
    for node in _walk(root):
        if node.type != "use_declaration":
            continue

        # The path is in the child after the `use` keyword.
        # It can be a scoped_identifier, use_wildcard, use_list, or
        # scoped_use_list.  For simple paths the entire text of the
        # scoped_identifier is the import target.
        for child in node.children:
            if child.type in (
                "scoped_identifier",
                "identifier",
                "use_wildcard",
                "scoped_use_list",
                "use_list",
            ):
                _collect_use_paths(child, "", source_file, node, results)


def _collect_use_paths(
    node: Node,
    prefix: str,
    source_file: Path,
    decl_node: Node,
    results: list[Relationship],
) -> None:
    """Recursively collect import paths from a use tree.

    For a plain scoped_identifier or identifier, emit a single import.
    For scoped_use_list and use_list, recurse into the list items and
    prepend the accumulated prefix so each leaf produces a full path.
    """
    if node.type in ("scoped_identifier", "identifier", "use_wildcard"):
        raw = node.text.decode() if node.text else ""
        target = f"{prefix}{raw}" if prefix else raw
        if target:
            results.append(Relationship(
                source=str(source_file),
                target=target,
                type=RelationshipType.IMPORT,
                source_file=source_file,
                line_number=decl_node.start_point[0] + 1,
            ))
        return

    if node.type == "scoped_use_list":
        # Structure: path :: { use_list }
        # Build the prefix from everything before the use_list child.
        scope_parts: list[str] = []
        for child in node.children:
            if child.type == "use_list":
                scope_prefix = "::".join(scope_parts)
                if scope_prefix:
                    scope_prefix += "::"
                full_prefix = f"{prefix}{scope_prefix}"
                _collect_use_paths(child, full_prefix, source_file, decl_node, results)
            elif child.type in ("identifier", "scoped_identifier", "crate", "self", "super"):
                scope_parts.append(child.text.decode() if child.text else "")
        return

    if node.type == "use_list":
        for child in node.children:
            if child.type in (
                "scoped_identifier", "identifier", "use_wildcard",
                "scoped_use_list", "use_list", "use_as_clause",
            ):
                _collect_use_paths(child, prefix, source_file, decl_node, results)
        return

    if node.type == "use_as_clause":
        # `use foo::bar as baz;` — the import target is the original path.
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                raw = child.text.decode() if child.text else ""
                target = f"{prefix}{raw}" if prefix else raw
                if target:
                    results.append(Relationship(
                        source=str(source_file),
                        target=target,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=decl_node.start_point[0] + 1,
                    ))
                return
        return


def _extract_structs(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract ownership relationships from struct field declarations."""
    for node in _walk(root):
        if node.type != "struct_item":
            continue

        struct_name = _get_struct_name(node)
        if not struct_name:
            continue

        _extract_ownership(node, struct_name, source_file, results)


def _extract_inheritance(
    root: Node, source_file: Path, results: list[Relationship]
) -> None:
    """Extract trait implementation relationships from impl blocks.

    Pattern: `impl TraitName for StructName` — the first type_identifier
    before the `for` keyword is the trait, the first after is the struct.
    """
    for node in _walk(root):
        if node.type != "impl_item":
            continue

        # Only consider impl blocks with a `for` keyword (trait impls).
        has_for = False
        for child in node.children:
            if child.type == "for":
                has_for = True
                break

        if not has_for:
            continue

        trait_name = ""
        struct_name = ""
        seen_for = False

        for child in node.children:
            if child.type == "for":
                seen_for = True
                continue

            if child.type == "type_identifier":
                if not seen_for:
                    trait_name = child.text.decode() if child.text else ""
                else:
                    struct_name = child.text.decode() if child.text else ""
                    break
            elif child.type == "scoped_type_identifier":
                # e.g., impl module::Trait for Struct
                name = _get_scoped_type_name(child)
                if not seen_for:
                    trait_name = name
                else:
                    struct_name = name
                    break
            elif child.type == "generic_type":
                name = _get_generic_type_name(child)
                if not seen_for:
                    trait_name = name
                else:
                    struct_name = name
                    break

        if trait_name and struct_name:
            results.append(Relationship(
                source=struct_name,
                target=trait_name,
                type=RelationshipType.INHERITANCE,
                source_file=source_file,
                line_number=node.start_point[0] + 1,
            ))


def _extract_ownership(
    struct_node: Node,
    struct_name: str,
    source_file: Path,
    results: list[Relationship],
) -> None:
    """Extract ownership from field declarations within a struct."""
    for child in struct_node.children:
        if child.type != "field_declaration_list":
            continue

        for field in child.children:
            if field.type != "field_declaration":
                continue

            type_name = _get_field_type(field)
            if type_name and type_name not in BUILTIN_TYPES:
                results.append(Relationship(
                    source=struct_name,
                    target=type_name,
                    type=RelationshipType.OWNERSHIP,
                    source_file=source_file,
                    line_number=field.start_point[0] + 1,
                ))


def _get_struct_name(struct_node: Node) -> str:
    """Get the name from a struct_item node."""
    for child in struct_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
    return ""


def _get_field_type(field_node: Node) -> str:
    """Extract the outermost type name from a field_declaration.

    Handles type_identifier, primitive_type, generic_type (returns the
    outer type e.g. Vec from Vec<Bar>), reference_type (unwraps the &),
    and scoped_type_identifier (returns the final type segment).
    """
    for child in field_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
        if child.type == "primitive_type":
            return child.text.decode() if child.text else ""
        if child.type == "generic_type":
            return _get_generic_type_name(child)
        if child.type == "reference_type":
            return _get_reference_type_name(child)
        if child.type == "scoped_type_identifier":
            return _get_scoped_type_name(child)
    return ""


def _get_generic_type_name(generic_node: Node) -> str:
    """Get the outer type name from a generic_type (e.g. Vec from Vec<T>)."""
    for child in generic_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
    return ""


def _get_reference_type_name(ref_node: Node) -> str:
    """Unwrap a reference_type (&T) and return the inner type name."""
    for child in ref_node.children:
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
        if child.type == "primitive_type":
            return child.text.decode() if child.text else ""
        if child.type == "generic_type":
            return _get_generic_type_name(child)
        if child.type == "scoped_type_identifier":
            return _get_scoped_type_name(child)
    return ""


def _get_scoped_type_name(scoped_node: Node) -> str:
    """Get the final type segment from a scoped_type_identifier.

    For crate::repos::UserRepository returns 'UserRepository'.
    """
    for child in reversed(scoped_node.children):
        if child.type == "type_identifier":
            return child.text.decode() if child.text else ""
    return ""


def _walk(node: Node) -> list[Node]:
    """Recursively walk all nodes in the tree."""
    result: list[Node] = [node]
    for child in node.children:
        result.extend(_walk(child))
    return result
