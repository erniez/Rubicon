"""Tests for the C++ tree-sitter adapter."""

from pathlib import Path

import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.cpp import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "cpp"

_lang = Language(tscpp.language())
_parser = Parser(_lang)


def _parse(fixture: str) -> list:
    """Parse a C++ fixture file and extract relationships."""
    path = FIXTURES / fixture
    content = path.read_bytes()
    tree = _parser.parse(content)
    return extract_relationships(tree, Path(fixture), content)


class TestIncludes:
    def test_include_extraction(self) -> None:
        rels = _parse("include_variants.cpp")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "iostream" in targets
        assert "mylib.h" in targets

    def test_include_count(self) -> None:
        rels = _parse("include_variants.cpp")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self) -> None:
        rels = _parse("class_hierarchy.cpp")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_interface(self) -> None:
        rels = _parse("class_hierarchy.cpp")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_supertypes(self) -> None:
        rels = _parse("class_hierarchy.cpp")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_class_fields(self) -> None:
        rels = _parse("ownership.cpp")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self) -> None:
        rels = _parse("ownership.cpp")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "string" not in targets
        assert "int" not in targets
