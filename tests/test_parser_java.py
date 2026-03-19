"""Tests for the Java tree-sitter adapter."""

from pathlib import Path

import tree_sitter_java as tsj
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.java import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "java"

_lang = Language(tsj.language())
_parser = Parser(_lang)


def _parse(fixture_name: str) -> list:
    """Parse a fixture file and extract relationships."""
    fixture_path = FIXTURES / fixture_name
    content = fixture_path.read_text()
    content_bytes = content.encode("utf-8")
    tree = _parser.parse(content_bytes)
    return extract_relationships(tree, Path(fixture_name), content_bytes)


class TestImports:
    def test_import_extraction(self) -> None:
        rels = _parse("import_variants.java")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "java.util.List" in targets
        assert "com.example.models.User" in targets

    def test_import_count(self) -> None:
        rels = _parse("import_variants.java")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self) -> None:
        rels = _parse("class_hierarchy.java")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_interface(self) -> None:
        rels = _parse("class_hierarchy.java")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_supertypes(self) -> None:
        rels = _parse("class_hierarchy.java")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_class_fields(self) -> None:
        rels = _parse("ownership.java")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self) -> None:
        rels = _parse("ownership.java")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "String" not in targets
        assert "int" not in targets
