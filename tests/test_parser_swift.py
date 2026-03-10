"""Tests for the Swift tree-sitter adapter."""

from pathlib import Path

from rubicon.graph.models import RelationshipType
from rubicon.parser.treesitter import parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "swift"


class TestImports:
    def test_import_extraction(self) -> None:
        content = (FIXTURES / "import_variants.swift").read_text()
        rels = parse_file(Path("import_variants.swift"), "swift", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "Foundation" in targets
        assert "UIKit" in targets

    def test_import_count(self) -> None:
        content = (FIXTURES / "import_variants.swift").read_text()
        rels = parse_file(Path("import_variants.swift"), "swift", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        assert len(imports) == 2


class TestInheritance:
    def test_superclass(self) -> None:
        content = (FIXTURES / "class_hierarchy.swift").read_text()
        rels = parse_file(Path("class_hierarchy.swift"), "swift", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_protocol_conformance(self) -> None:
        content = (FIXTURES / "class_hierarchy.swift").read_text()
        rels = parse_file(Path("class_hierarchy.swift"), "swift", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Pet") in pairs

    def test_multiple_supertypes(self) -> None:
        content = (FIXTURES / "class_hierarchy.swift").read_text()
        rels = parse_file(Path("class_hierarchy.swift"), "swift", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs
        assert ("GuideDog", "Certifiable") in pairs


class TestOwnership:
    def test_class_properties(self) -> None:
        content = (FIXTURES / "ownership.swift").read_text()
        rels = parse_file(Path("ownership.swift"), "swift", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs
        assert ("Car", "Person") in pairs

    def test_struct_properties(self) -> None:
        content = (FIXTURES / "ownership.swift").read_text()
        rels = parse_file(Path("ownership.swift"), "swift", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Garage", "Car") in pairs

    def test_builtin_types_excluded(self) -> None:
        content = (FIXTURES / "ownership.swift").read_text()
        rels = parse_file(Path("ownership.swift"), "swift", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "String" not in targets
        assert "Int" not in targets


class TestStructAndEnum:
    def test_struct_ownership(self) -> None:
        content = (FIXTURES / "struct_and_enum.swift").read_text()
        rels = parse_file(Path("struct_and_enum.swift"), "swift", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Config", "DatabaseConnection") in pairs
        assert ("Config", "CacheManager") in pairs

    def test_struct_builtin_excluded(self) -> None:
        content = (FIXTURES / "struct_and_enum.swift").read_text()
        rels = parse_file(Path("struct_and_enum.swift"), "swift", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "Int" not in targets

    def test_enum_inheritance(self) -> None:
        content = (FIXTURES / "struct_and_enum.swift").read_text()
        rels = parse_file(Path("struct_and_enum.swift"), "swift", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("AppState", "Codable") in pairs
