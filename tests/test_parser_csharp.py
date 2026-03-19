"""Tests for the C# tree-sitter adapter."""

from pathlib import Path

import pytest
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.csharp import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "csharp"


@pytest.fixture(scope="module")
def csharp_parser() -> Parser:
    """Create a C# tree-sitter parser."""
    import tree_sitter_c_sharp as tsc
    ts_language = Language(tsc.language())
    return Parser(ts_language)


def _parse(parser: Parser, fixture: str) -> list:
    """Parse a fixture file and extract relationships."""
    fixture_path = FIXTURES / fixture
    content = fixture_path.read_text()
    content_bytes = content.encode("utf-8")
    tree = parser.parse(content_bytes)
    return extract_relationships(tree, Path(fixture), content_bytes)


class TestImports:
    def test_import_extraction(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "import_variants.cs")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "System" in targets
        assert "System.Collections.Generic" in targets

    def test_import_count(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "import_variants.cs")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "class_hierarchy.cs")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_interface(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "class_hierarchy.cs")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "IPet") in pairs

    def test_multiple_supertypes(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "class_hierarchy.cs")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "ITrainable") in pairs
        assert ("GuideDog", "ICertifiable") in pairs


class TestOwnership:
    def test_class_fields(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "ownership.cs")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self, csharp_parser: Parser) -> None:
        rels = _parse(csharp_parser, "ownership.cs")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "string" not in targets
        assert "int" not in targets
