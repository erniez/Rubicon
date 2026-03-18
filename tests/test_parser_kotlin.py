"""Tests for the Kotlin tree-sitter adapter."""

from pathlib import Path

from rubicon.models import RelationshipType
from rubicon.parser.treesitter import parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "kotlin"


class TestImports:
    def test_import_extraction(self) -> None:
        content = (FIXTURES / "import_variants.kt").read_text()
        rels = parse_file(Path("import_variants.kt"), "kotlin", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "com.example.Foo" in targets
        assert "com.example.bar.Baz" in targets

    def test_import_count(self) -> None:
        content = (FIXTURES / "import_variants.kt").read_text()
        rels = parse_file(Path("import_variants.kt"), "kotlin", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self) -> None:
        content = (FIXTURES / "class_hierarchy.kt").read_text()
        rels = parse_file(Path("class_hierarchy.kt"), "kotlin", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_interface(self) -> None:
        content = (FIXTURES / "class_hierarchy.kt").read_text()
        rels = parse_file(Path("class_hierarchy.kt"), "kotlin", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_supertypes(self) -> None:
        content = (FIXTURES / "class_hierarchy.kt").read_text()
        rels = parse_file(Path("class_hierarchy.kt"), "kotlin", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_body_properties(self) -> None:
        content = (FIXTURES / "ownership.kt").read_text()
        rels = parse_file(Path("ownership.kt"), "kotlin", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_constructor_parameters(self) -> None:
        content = (FIXTURES / "ownership.kt").read_text()
        rels = parse_file(Path("ownership.kt"), "kotlin", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("User", "UserRepository") in pairs

    def test_builtin_types_excluded(self) -> None:
        content = (FIXTURES / "ownership.kt").read_text()
        rels = parse_file(Path("ownership.kt"), "kotlin", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "String" not in targets
        assert "Int" not in targets
