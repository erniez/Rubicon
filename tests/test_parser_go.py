"""Tests for the Go tree-sitter adapter."""

from pathlib import Path

import pytest
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.go import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "go"


@pytest.fixture()
def go_parser() -> Parser:
    """Create a tree-sitter Go parser."""
    import tree_sitter_go as tsg

    lang = Language(tsg.language())
    return Parser(lang)


def _parse(go_parser: Parser, fixture: str) -> list:
    """Parse a fixture file and extract relationships."""
    path = FIXTURES / fixture
    content = path.read_text()
    content_bytes = content.encode("utf-8")
    tree = go_parser.parse(content_bytes)
    return extract_relationships(tree, Path(fixture), content_bytes)


class TestImports:
    def test_import_extraction(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "import_variants.go")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "fmt" in targets
        assert "github.com/example/repo" in targets

    def test_import_count(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "import_variants.go")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 4


class TestInheritance:
    def test_embedded_struct(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "struct_hierarchy.go")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_embedded_interface(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "struct_hierarchy.go")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_embeds(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "struct_hierarchy.go")
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_struct_fields(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "ownership.go")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self, go_parser: Parser) -> None:
        rels = _parse(go_parser, "ownership.go")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "string" not in targets
        assert "int" not in targets
