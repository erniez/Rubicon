"""Tests for the Ruby tree-sitter adapter."""

from pathlib import Path

from rubicon.models import RelationshipType
from rubicon.parser.treesitter import parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "ruby"


class TestImports:
    def test_import_extraction(self) -> None:
        content = (FIXTURES / "import_variants.rb").read_text()
        rels = parse_file(Path("import_variants.rb"), "ruby", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "json" in targets
        assert "models/user" in targets

    def test_import_count(self) -> None:
        content = (FIXTURES / "import_variants.rb").read_text()
        rels = parse_file(Path("import_variants.rb"), "ruby", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self) -> None:
        content = (FIXTURES / "class_hierarchy.rb").read_text()
        rels = parse_file(Path("class_hierarchy.rb"), "ruby", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_module_include(self) -> None:
        content = (FIXTURES / "class_hierarchy.rb").read_text()
        rels = parse_file(Path("class_hierarchy.rb"), "ruby", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_supertypes(self) -> None:
        content = (FIXTURES / "class_hierarchy.rb").read_text()
        rels = parse_file(Path("class_hierarchy.rb"), "ruby", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_constructor_fields(self) -> None:
        content = (FIXTURES / "ownership.rb").read_text()
        rels = parse_file(Path("ownership.rb"), "ruby", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs

    def test_builtin_types_excluded(self) -> None:
        content = (FIXTURES / "ownership.rb").read_text()
        rels = parse_file(Path("ownership.rb"), "ruby", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "String" not in targets
