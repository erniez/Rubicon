"""Tests for core data models."""

from pathlib import Path

from rubicon.graph.models import (
    Edge,
    Language,
    Node,
    Relationship,
    RelationshipType,
    Severity,
    Violation,
)


class TestEnums:
    def test_relationship_types(self) -> None:
        assert RelationshipType.IMPORT.value == "import"
        assert RelationshipType.INHERITANCE.value == "inheritance"
        assert RelationshipType.OWNERSHIP.value == "ownership"
        assert RelationshipType.FUNCTION_CALL.value == "function_call"
        assert len(RelationshipType) == 4

    def test_severity_levels(self) -> None:
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"
        assert len(Severity) == 3

    def test_languages(self) -> None:
        assert Language.PYTHON.value == "python"
        assert Language.TYPESCRIPT.value == "typescript"
        assert Language.SWIFT.value == "swift"
        assert Language.KOTLIN.value == "kotlin"
        assert len(Language) == 12

    def test_enum_lookup_by_value(self) -> None:
        assert RelationshipType("import") is RelationshipType.IMPORT
        assert Severity("error") is Severity.ERROR
        assert Language("swift") is Language.SWIFT


class TestRelationship:
    def test_construction(self) -> None:
        r = Relationship(
            source="app.py:App",
            target="utils.py:helper",
            type=RelationshipType.IMPORT,
            source_file=Path("app.py"),
            line_number=1,
        )
        assert r.source == "app.py:App"
        assert r.target == "utils.py:helper"
        assert r.type is RelationshipType.IMPORT
        assert r.source_file == Path("app.py")
        assert r.line_number == 1

    def test_is_frozen(self) -> None:
        r = Relationship(
            source="a",
            target="b",
            type=RelationshipType.IMPORT,
            source_file=Path("a.py"),
            line_number=1,
        )
        try:
            r.source = "c"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestNode:
    def test_construction(self) -> None:
        n = Node(id="src/app.py", file_path=Path("src/app.py"), language="python")
        assert n.id == "src/app.py"
        assert n.symbols == []
        assert n.layer == "unclassified"

    def test_defaults(self) -> None:
        n = Node(id="x", file_path=Path("x"))
        assert n.symbols == []
        assert n.language == ""
        assert n.layer == "unclassified"

    def test_mutable_symbols(self) -> None:
        n = Node(id="x", file_path=Path("x"))
        n.symbols.append("MyClass")
        assert n.symbols == ["MyClass"]

    def test_layer_assignable(self) -> None:
        n = Node(id="x", file_path=Path("x"))
        n.layer = "presentation"
        assert n.layer == "presentation"


class TestEdge:
    def test_construction(self) -> None:
        r = Relationship(
            source="a",
            target="b",
            type=RelationshipType.IMPORT,
            source_file=Path("a.py"),
            line_number=1,
        )
        e = Edge(source_id="a.py", target_id="b.py", relationships=(r,))
        assert e.source_id == "a.py"
        assert e.target_id == "b.py"
        assert len(e.relationships) == 1

    def test_multiple_relationships(self) -> None:
        r1 = Relationship(
            source="a",
            target="b",
            type=RelationshipType.IMPORT,
            source_file=Path("a.py"),
            line_number=1,
        )
        r2 = Relationship(
            source="a:ClassA",
            target="b:ClassB",
            type=RelationshipType.INHERITANCE,
            source_file=Path("a.py"),
            line_number=5,
        )
        e = Edge(source_id="a.py", target_id="b.py", relationships=(r1, r2))
        assert len(e.relationships) == 2

    def test_empty_relationships_default(self) -> None:
        e = Edge(source_id="a", target_id="b")
        assert e.relationships == ()

    def test_is_frozen(self) -> None:
        e = Edge(source_id="a", target_id="b")
        try:
            e.source_id = "c"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestViolation:
    def test_construction(self) -> None:
        v = Violation(
            rule="no_upward_dependency",
            severity=Severity.WARNING,
            source_node_id="data/store.py",
            target_node_id="presentation/screen.py",
            message="data layer imports from presentation layer",
        )
        assert v.rule == "no_upward_dependency"
        assert v.severity is Severity.WARNING
        assert v.relationship is None

    def test_with_relationship(self) -> None:
        r = Relationship(
            source="store",
            target="screen",
            type=RelationshipType.IMPORT,
            source_file=Path("data/store.py"),
            line_number=3,
        )
        v = Violation(
            rule="no_upward_dependency",
            severity=Severity.WARNING,
            source_node_id="data/store.py",
            target_node_id="presentation/screen.py",
            message="data layer imports from presentation layer",
            relationship=r,
        )
        assert v.relationship is r

    def test_target_node_optional(self) -> None:
        v = Violation(
            rule="orphan_detection",
            severity=Severity.INFO,
            source_node_id="utils/unused.py",
            target_node_id=None,
            message="file has no connections",
        )
        assert v.target_node_id is None
