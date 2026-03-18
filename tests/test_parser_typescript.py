"""Tests for the TypeScript tree-sitter adapter."""

from pathlib import Path

from rubicon.models import RelationshipType
from rubicon.parser.treesitter import parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "typescript"


class TestImports:
    def test_named_import(self) -> None:
        content = (FIXTURES / "import_variants.ts").read_text()
        rels = parse_file(Path("import_variants.ts"), "typescript", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "./foo" in targets

    def test_namespace_import(self) -> None:
        content = (FIXTURES / "import_variants.ts").read_text()
        rels = parse_file(Path("import_variants.ts"), "typescript", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "bar" in targets

    def test_default_import(self) -> None:
        content = (FIXTURES / "import_variants.ts").read_text()
        rels = parse_file(Path("import_variants.ts"), "typescript", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "baz" in targets

    def test_import_count(self) -> None:
        content = (FIXTURES / "import_variants.ts").read_text()
        rels = parse_file(Path("import_variants.ts"), "typescript", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 3


class TestInheritance:
    def test_extends(self) -> None:
        content = (FIXTURES / "class_extends.ts").read_text()
        rels = parse_file(Path("class_extends.ts"), "typescript", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_implements(self) -> None:
        content = (FIXTURES / "class_extends.ts").read_text()
        rels = parse_file(Path("class_extends.ts"), "typescript", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_implements(self) -> None:
        content = (FIXTURES / "class_extends.ts").read_text()
        rels = parse_file(Path("class_extends.ts"), "typescript", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_custom_type_fields(self) -> None:
        content = (FIXTURES / "ownership.ts").read_text()
        rels = parse_file(Path("ownership.ts"), "typescript", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs
        assert ("Car", "Person") in pairs

    def test_builtin_types_excluded(self) -> None:
        content = (FIXTURES / "ownership.ts").read_text()
        rels = parse_file(Path("ownership.ts"), "typescript", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "string" not in targets
        assert "number" not in targets
