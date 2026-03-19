"""Tests for the C tree-sitter adapter."""

from pathlib import Path

import tree_sitter_c as tsc
from tree_sitter import Language, Parser

from rubicon.models import RelationshipType
from rubicon.parser.adapters.c import extract_relationships

FIXTURES = Path(__file__).parent / "fixtures" / "c"

_lang = Language(tsc.language())
_parser = Parser(_lang)


def _parse(fixture: str) -> list:
    """Parse a C fixture file and extract relationships."""
    path = FIXTURES / fixture
    content = path.read_bytes()
    tree = _parser.parse(content)
    return extract_relationships(tree, Path(fixture), content)


class TestIncludes:
    def test_include_extraction(self) -> None:
        rels = _parse("include_variants.c")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "stdio.h" in targets
        assert "mylib.h" in targets

    def test_include_count(self) -> None:
        rels = _parse("include_variants.c")
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestOwnership:
    def test_struct_fields(self) -> None:
        rels = _parse("ownership.c")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self) -> None:
        rels = _parse("ownership.c")
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "char" not in targets
        assert "int" not in targets
