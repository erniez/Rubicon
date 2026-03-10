"""Tests for the Python tree-sitter adapter."""

from pathlib import Path

from rubicon.graph.models import RelationshipType
from rubicon.parser.treesitter import parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "python"


class TestImports:
    def test_simple_import(self) -> None:
        content = (FIXTURES / "simple_import.py").read_text()
        rels = parse_file(Path("simple_import.py"), "python", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "os" in targets
        assert "os.path" in targets
        assert "pathlib" in targets
        assert "collections.abc" in targets

    def test_relative_imports(self) -> None:
        content = (FIXTURES / "simple_import.py").read_text()
        rels = parse_file(Path("simple_import.py"), "python", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "." in targets
        assert "..parent" in targets

    def test_import_line_numbers(self) -> None:
        content = (FIXTURES / "simple_import.py").read_text()
        rels = parse_file(Path("simple_import.py"), "python", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        by_target = {r.target: r for r in imports}
        assert by_target["os"].line_number == 1
        assert by_target["pathlib"].line_number == 3

    def test_import_source_is_file_path(self) -> None:
        content = (FIXTURES / "simple_import.py").read_text()
        rels = parse_file(Path("simple_import.py"), "python", content)
        for r in rels:
            if r.type == RelationshipType.IMPORT:
                assert r.source == "simple_import.py"


class TestInheritance:
    def test_single_base_class(self) -> None:
        content = (FIXTURES / "class_inheritance.py").read_text()
        rels = parse_file(Path("class_inheritance.py"), "python", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs

    def test_multiple_base_classes(self) -> None:
        content = (FIXTURES / "class_inheritance.py").read_text()
        rels = parse_file(Path("class_inheritance.py"), "python", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        pairs = {(r.source, r.target) for r in inheritance}
        assert ("GuideDog", "Dog") in pairs
        assert ("GuideDog", "Trainable") in pairs

    def test_base_class_without_parents_has_no_inheritance(self) -> None:
        content = (FIXTURES / "class_inheritance.py").read_text()
        rels = parse_file(Path("class_inheritance.py"), "python", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        sources = {r.source for r in inheritance}
        assert "Animal" not in sources


class TestOwnership:
    def test_typed_fields(self) -> None:
        content = (FIXTURES / "ownership.py").read_text()
        rels = parse_file(Path("ownership.py"), "python", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("Car", "Engine") in pairs
        assert ("Car", "Person") in pairs
        assert ("Garage", "Car") in pairs

    def test_builtin_types_excluded(self) -> None:
        content = (FIXTURES / "ownership.py").read_text()
        rels = parse_file(Path("ownership.py"), "python", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        targets = {r.target for r in ownership}
        assert "str" not in targets
        assert "int" not in targets


class TestMixed:
    def test_all_relationship_types(self) -> None:
        content = (FIXTURES / "mixed.py").read_text()
        rels = parse_file(Path("mixed.py"), "python", content)

        types = {r.type for r in rels}
        assert RelationshipType.IMPORT in types
        assert RelationshipType.INHERITANCE in types
        assert RelationshipType.OWNERSHIP in types

    def test_mixed_imports(self) -> None:
        content = (FIXTURES / "mixed.py").read_text()
        rels = parse_file(Path("mixed.py"), "python", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]

        targets = {r.target for r in imports}
        assert "logging" in targets
        assert "models" in targets

    def test_mixed_inheritance(self) -> None:
        content = (FIXTURES / "mixed.py").read_text()
        rels = parse_file(Path("mixed.py"), "python", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]

        assert any(r.source == "UserService" and r.target == "BaseModel" for r in inheritance)

    def test_mixed_ownership(self) -> None:
        content = (FIXTURES / "mixed.py").read_text()
        rels = parse_file(Path("mixed.py"), "python", content)
        ownership = [r for r in rels if r.type == RelationshipType.OWNERSHIP]

        pairs = {(r.source, r.target) for r in ownership}
        assert ("UserService", "UserRepository") in pairs
        assert ("UserService", "CacheManager") in pairs


class TestParseErrors:
    def test_broken_file_does_not_crash(self) -> None:
        content = (FIXTURES / "parse_error.py").read_text()
        rels = parse_file(Path("parse_error.py"), "python", content)
        # Should return whatever it can extract, not crash
        assert isinstance(rels, list)

    def test_broken_file_still_extracts_valid_parts(self) -> None:
        content = (FIXTURES / "parse_error.py").read_text()
        rels = parse_file(Path("parse_error.py"), "python", content)
        imports = [r for r in rels if r.type == RelationshipType.IMPORT]
        # The 'import os' at the top should still be extracted
        assert any(r.target == "os" for r in imports)


class TestUnsupportedLanguage:
    def test_returns_empty_list(self) -> None:
        rels = parse_file(Path("file.xyz"), "unknown_lang", "some content")
        assert rels == []
