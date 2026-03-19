"""Tests for the Rust tree-sitter adapter."""

from pathlib import Path

import tree_sitter_rust as tsr
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.rust import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "rust"


def _parse_rust(fixture_name: str) -> list:
    """Parse a Rust fixture file and return extracted relationships."""
    path = FIXTURES / fixture_name
    content = path.read_text()
    content_bytes = content.encode("utf-8")

    lang = Language(tsr.language())
    parser = Parser(lang)
    tree = parser.parse(content_bytes)

    return extract_relationships(tree, Path(fixture_name), content_bytes)


class TestImports:
    def test_import_extraction(self) -> None:
        rels = _parse_rust("import_variants.rs")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "std::collections::HashMap" in targets
        assert "crate::models::User" in targets

    def test_import_count(self) -> None:
        rels = _parse_rust("import_variants.rs")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_trait_impl(self) -> None:
        rels = _parse_rust("struct_hierarchy.rs")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_traits(self) -> None:
        rels = _parse_rust("struct_hierarchy.rs")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_struct_fields(self) -> None:
        rels = _parse_rust("ownership.rs")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self) -> None:
        rels = _parse_rust("ownership.rs")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "String" not in targets
        assert "i32" not in targets
